import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import UploadResponse, AnalyzeRequest, ReportResult
from app.document_processor import process_pdf
from app.rag_engine import store_document_chunks, analyze_hypothesis

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

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    doc_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")
    
    # Save the file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Process and chunk PDF
        chunks = process_pdf(file_path)
        
        # Store in ChromaDB
        store_document_chunks(doc_id, chunks)
        
        return UploadResponse(doc_id=doc_id, message=f"Successfully processed {len(chunks)} chunks.")
    except Exception as e:
        # Cleanup on failure
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze", response_model=ReportResult)
async def analyze_document(request: AnalyzeRequest):
    try:
        result = analyze_hypothesis(request.doc_id, request.hypothesis)
        return ReportResult(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
