import os
import shutil
import time
import uuid
from typing import List, Literal, Optional

import fitz  # PyMuPDF
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app import history_db
from app import research
from app.schemas import (
    UploadResponse,
    AnalyzeRequest,
    ReportResult,
    HistoryPage,
    HistoryDocument,
    Analytics,
    ResearchMetrics,
)
from app.agent import live_service
from app.logging_config import configure_logging, get_logger, log_exception, log_step

# Configuring logging here (rather than relying only on get_logger()'s
# implicit first-call setup) makes main.py's own import order the anchor:
# it's the first thing uvicorn imports, so the console level is locked in
# from EDGELEGAL_LOG_LEVEL before any other module's get_logger() call could.
configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="EdgeLegal Backend",
    description="Local-first legal document intelligence system API",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

history_db.init_db()
logger.info("=== EdgeLegal backend starting up (upload_dir=%s) ===", UPLOAD_DIR)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log every request's outcome, and — critically — catch and fully log any
    exception that escapes a route handler instead of letting FastAPI's
    default handler swallow it into a bare 500 with no server-side trace.
    Route handlers below still catch their own known failure points and
    return a specific HTTPException; this is the backstop for anything they
    don't (a bug in schemas.py validation, an unexpected history_db error,
    etc.) — see research.py/history_db.py, which have no try/except of
    their own and rely on this to make their failures traceable at all.
    """
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = time.perf_counter() - started
        log_exception(logger, "Unhandled exception in request",
                      method=request.method, path=request.url.path,
                      elapsed_s=round(elapsed, 3))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    elapsed = time.perf_counter() - started
    level = logger.warning if response.status_code >= 400 else logger.debug
    level("%s %s -> %d (%.3fs)", request.method, request.url.path,
          response.status_code, elapsed)
    return response


@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        logger.warning("Rejected upload: filename=%r is not a .pdf", file.filename)
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    doc_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")
    log_step(logger, "upload.start", doc_id=doc_id, filename=file.filename)

    # Save the file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Structure-aware clause parsing + indexing for the live triage agent.
        clause_count = live_service.index_document(doc_id, file_path)
    except Exception as e:
        log_exception(logger, "index_document() failed - cleaning up upload",
                      doc_id=doc_id, filename=file.filename)
        # Cleanup on failure
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

    try:
        with fitz.open(file_path) as pdf:
            page_count = pdf.page_count
        history_db.record_document(doc_id, file.filename, page_count)
    except Exception:
        log_exception(logger, "Failed to record document in history", doc_id=doc_id)

    log_step(logger, "upload.done", doc_id=doc_id, n_clauses=clause_count)
    return UploadResponse(doc_id=doc_id, message=f"Successfully processed {clause_count} clauses.")

@app.post("/analyze", response_model=ReportResult)
async def analyze_document(request: AnalyzeRequest):
    log_step(logger, "analyze.start", doc_id=request.doc_id,
             hypothesis=request.hypothesis[:80])
    try:
        result = live_service.run_agent(request.doc_id, request.hypothesis)
        report = ReportResult(**result)
    except Exception as e:
        log_exception(logger, "run_agent() failed", doc_id=request.doc_id,
                      hypothesis=request.hypothesis[:80])
        raise HTTPException(status_code=500, detail=str(e))

    # History is best-effort: a DB failure must never cost the user their result.
    try:
        history_db.record_analysis(request.doc_id, request.hypothesis, report.model_dump())
    except Exception:
        log_exception(logger, "Failed to record analysis in history",
                      doc_id=request.doc_id)

    log_step(logger, "analyze.done", doc_id=request.doc_id, label=report.label)

    return report

@app.get("/history", response_model=HistoryPage)
async def get_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    label: Optional[Literal["Entailment", "Contradiction", "NotMentioned"]] = None,
    document_id: Optional[str] = None,
    q: Optional[str] = Query(None, max_length=200),
    since: Optional[str] = Query(None, description="ISO-8601 timestamp; only analyses at or after it"),
):
    try:
        items, total = history_db.list_analyses(limit, offset, label, document_id, q, since)
    except ValueError:
        raise HTTPException(status_code=422, detail="'since' must be an ISO-8601 timestamp")
    return HistoryPage(items=items, total=total, limit=limit, offset=offset)

@app.get("/history/documents", response_model=List[HistoryDocument])
async def get_history_documents():
    return history_db.list_documents()

@app.get("/analytics", response_model=Analytics)
async def get_analytics():
    return history_db.get_analytics()

@app.get("/research/metrics", response_model=ResearchMetrics)
async def get_research_metrics():
    return research.get_research_metrics()

@app.get("/history/{analysis_id}", response_model=ReportResult)
async def get_history_item(analysis_id: int):
    report = history_db.get_analysis(analysis_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return ReportResult(**report)

@app.get("/documents/{doc_id}/file")
async def get_document_file(doc_id: str):
    try:
        uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(file_path, media_type="application/pdf")
