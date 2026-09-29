"""
agent/live_service.py
──────────────────────
Wires the LangGraph triage agent (agent/graph.py) into the live FastAPI app.

This is a separate, additive path. It does not touch rag_engine.py,
document_processor.py, or the "legal_documents" ChromaDB collection those
use, nor experiment_runner.py's ephemeral "experiment_doc_*" collections —
the actual Config A/B/C measurement pipeline. Isolation from that pipeline
is deliberate: a bug in the live app must never be able to change a
thesis number. main.py no longer imports rag_engine.py at all; agent/
nodes.py, agent/state.py, and agent/graph.py are used exactly as they
already existed for the research pipeline — nothing in this file changes
their behavior or return shapes.

Public API:
  index_document(doc_id: str, pdf_path: str) -> int   # clauses indexed
  run_agent(doc_id: str, hypothesis: str) -> dict      # -> ReportResult shape
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Optional

# agent/nodes.py and triage_model/*.py import as `backend.app.X` (written to
# be run via `python -m backend.app.X` from the project root). The live app
# runs as `app.X` via `uvicorn app.main:app` with cwd=backend/. Putting the
# project root on sys.path lets both import conventions resolve in the same
# process without changing either existing convention.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.app.agent.graph import build_graph  # noqa: E402
from backend.app.embeddings.embedder import Embedder  # noqa: E402
from backend.app.parsing.clause_parser import Clause, PageBlock, segment_clauses  # noqa: E402
from backend.app.vectorstore.chroma_client import (  # noqa: E402
    add_clauses,
    get_persistent_client,
    init_collection,
)
from app.logging_config import get_logger, log_exception, log_step  # noqa: E402

logger = get_logger(__name__)

# Kept in sync with backend/app/experiment_runner.py's FROZEN_THRESHOLD —
# duplicated as a plain constant rather than imported, since that module is
# a CLI script for offline experiments, not meant to be imported by a
# long-running web server process.
FROZEN_THRESHOLD = 0.95

LIVE_CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "live_chroma_db")

_setup_lock = threading.Lock()
_embedder: Optional[Embedder] = None
_graph = None
_chroma_client = None
_llm_client = None


def _get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        with _setup_lock:
            if _embedder is None:
                e = Embedder()
                e.load()
                _embedder = e
    return _embedder


def _get_graph():
    global _graph
    if _graph is None:
        with _setup_lock:
            if _graph is None:
                _graph = build_graph()
    return _graph


def _get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        with _setup_lock:
            if _chroma_client is None:
                _chroma_client = get_persistent_client(LIVE_CHROMA_DIR)
    return _chroma_client


def _get_llm_client() -> "GroqAgentClient":
    global _llm_client
    if _llm_client is None:
        with _setup_lock:
            if _llm_client is None:
                _llm_client = GroqAgentClient()
    return _llm_client


class GroqAgentClient:
    """
    Adapts the project's Groq client to the `.query_llm(clauses, hypothesis,
    triage_label="") -> LLMResult` interface call_llm_node expects — the
    same interface OllamaClient exposes. Reuses the exact same prompt
    builder and response parser as the Ollama path (llm/prompts.py,
    llm/ollama_client.py's _parse_llm_response) so only the HTTP transport
    differs; only the Ollama path is used for the paper's own local/private
    evaluation numbers.
    """

    def query_llm(self, clauses: list, hypothesis: str, triage_label: str = ""):
        from app.llm.groq_client import groq_client
        from backend.app.llm.ollama_client import _parse_llm_response
        from backend.app.llm.prompts import build_reasoning_prompt

        if not groq_client.has_keys:
            raise RuntimeError("No Groq API keys configured in backend/.env (GROQ_API_KEYS).")

        prompt = build_reasoning_prompt(clauses, hypothesis, triage_label)
        raw = groq_client.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        return _parse_llm_response(raw)


def _collection_for(doc_id: str):
    return init_collection(f"live_{doc_id}", client=_get_chroma_client())


def index_document(doc_id: str, pdf_path: str) -> int:
    """
    Parse a PDF into clause-level units (parsing/clause_parser.py — the
    same structure-aware segmentation the research pipeline uses, not
    document_processor.py's naive block chunking) and index them for the
    live agent. Returns the number of clauses indexed (0 if the PDF had no
    extractable text, e.g. a scanned image with no text layer).
    """
    import fitz  # PyMuPDF — already a hard dependency (document_processor.py)

    log_step(logger, "index_document.start", doc_id=doc_id, pdf_path=pdf_path)

    try:
        pages: list[PageBlock] = []
        with fitz.open(pdf_path) as pdf:
            for i, page in enumerate(pdf):
                pages.append(PageBlock(text=page.get_text(), page_num=i + 1))
    except Exception:
        log_exception(logger, "PDF parsing failed", doc_id=doc_id, pdf_path=pdf_path)
        raise

    clauses = segment_clauses(pages)
    if not clauses:
        logger.warning("index_document: 0 clauses for doc_id=%s (%d pages) - "
                       "likely a scanned/image-only PDF.", doc_id, len(pages))
        return 0

    try:
        embedder = _get_embedder()
        collection = _collection_for(doc_id)
        add_clauses(collection, clauses, embedder.embed([c.text for c in clauses]))
    except Exception:
        log_exception(logger, "Indexing (embed/add_clauses) failed", doc_id=doc_id,
                      n_clauses=len(clauses))
        raise

    log_step(logger, "index_document.done", doc_id=doc_id, n_pages=len(pages),
             n_clauses=len(clauses))
    return len(clauses)


def _clause_citations(retrieved: list[Clause], excerpts: Optional[list] = None) -> list[dict]:
    """
    Build ReportCitation-shaped dicts {id, text, page, bbox} from the
    agent's retrieved clauses.

    - excerpts is None (classifier-accept path): cite the single rank-1
      clause the classifier actually saw, matching accept_node's own
      behavior of assembling the result from that clause.
    - excerpts is a list[str] (LLM path): the LLM's own verbatim-quoted
      excerpts (per the prompt's instructions) are more precise than "every
      retrieved clause", so match each back to its source clause for a page
      number. A paraphrased (non-verbatim) excerpt still gets shown, best-
      effort attributed to the rank-1 clause's page.

    bbox is always None — Clause (parsing/clause_parser.py) carries
    page_num but not a pixel bounding box, unlike document_processor.py's
    naive chunks. The frontend already treats bbox as optional: citations
    still jump to the correct page, just without the highlighted box.
    """
    if not retrieved:
        return []

    if excerpts is None:
        top = retrieved[0]
        return [{"id": top.id, "text": top.text, "page": top.page_num, "bbox": None}]

    def _norm(s: str) -> str:
        return " ".join(s.split())

    citations, seen_ids = [], set()
    for excerpt in excerpts:
        excerpt = (excerpt or "").strip()
        if not excerpt:
            continue
        norm_excerpt = _norm(excerpt)
        match = next(
            (c for c in retrieved if norm_excerpt in _norm(c.text) or _norm(c.text) in norm_excerpt),
            None,
        )
        if match is not None:
            if match.id in seen_ids:
                continue
            seen_ids.add(match.id)
            citations.append({"id": match.id, "text": excerpt, "page": match.page_num, "bbox": None})
        else:
            citations.append({
                "id": f"excerpt_{len(citations)}",
                "text": excerpt,
                "page": retrieved[0].page_num,
                "bbox": None,
            })
    return citations


def run_agent(doc_id: str, hypothesis: str) -> dict:
    """
    Run the confidence-routed triage agent for one hypothesis against an
    already-indexed document. Returns a dict matching schemas.ReportResult.
    """
    log_step(logger, "run_agent.start", doc_id=doc_id, hypothesis=hypothesis[:80])

    collection = _collection_for(doc_id)
    if collection.count() == 0:
        logger.warning("run_agent: doc_id=%s has an empty collection - "
                       "returning NotMentioned without invoking the agent.", doc_id)
        return {
            "label": "NotMentioned",
            "reasoning": "This document has no extractable clauses to check against.",
            "cited_clauses": [],
            "source": None,
            "confidence": None,
            "triage": None,
        }

    try:
        final_state = _get_graph().invoke({
            "document_id": doc_id,
            "hypothesis": hypothesis,
            "collection": collection,
            "embedder": _get_embedder(),
            "llm_client": _get_llm_client(),
            "threshold": FROZEN_THRESHOLD,
            "skip_triage": False,
        })
    except Exception:
        log_exception(logger, "Agent graph invoke() failed", doc_id=doc_id,
                      hypothesis=hypothesis[:80])
        raise

    retrieved = final_state.get("retrieved_clauses") or []
    source = final_state.get("source_engine")
    label = final_state.get("final_label") or "NotMentioned"
    triage_confidence = final_state.get("triage_confidence")
    routing_decision = final_state.get("routing_decision")

    if source == "classifier":
        pct = f"{triage_confidence * 100:.0f}%" if triage_confidence is not None else "high"
        reasoning = (
            f"Resolved directly by the triage classifier ({pct} confidence, at or "
            f"above the {FROZEN_THRESHOLD * 100:.0f}% threshold) — no LLM call needed."
        )
        citations = _clause_citations(retrieved)
    else:
        reasoning = final_state.get("reasoning_text") or "No reasoning returned."
        citations = _clause_citations(retrieved, final_state.get("cited_clauses"))

    triage_detail = None
    if routing_decision is not None:
        triage_detail = {
            "label": final_state.get("triage_label"),
            "confidence": triage_confidence,
            "threshold": FROZEN_THRESHOLD,
            "decision": routing_decision,
        }

    log_step(logger, "run_agent.done", doc_id=doc_id, label=label, source=source)
    return {
        "label": label,
        "reasoning": reasoning,
        "cited_clauses": citations,
        "source": source,
        # Only meaningful on the classifier path — None here (rather than the
        # sub-threshold triage score) matches ReportResult's documented
        # contract and what the frontend's confidence bar expects to gate on.
        # The pre-routing triage score is still available either way, via
        # `triage`, for the "how this was decided" panel.
        "confidence": triage_confidence if source == "classifier" else None,
        "triage": triage_detail,
    }
