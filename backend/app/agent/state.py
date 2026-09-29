"""
agent/state.py
───────────────
Shared state schema for the LangGraph routing agent — matches the Graph
State Schema in docs/technical_architecture.md §4.4.
"""

from __future__ import annotations

from typing import Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # ── Set by the caller before graph.invoke() ────────────────────────────
    document_id: str
    hypothesis: str
    collection: Any        # chromadb.Collection for this document
    embedder: Any           # embeddings.embedder.Embedder, already .load()-ed
    llm_client: Any          # llm.ollama_client.OllamaClient
    threshold: float         # frozen confidence threshold (unused when skip_triage)
    skip_triage: bool        # Config A: retrieve -> LLM directly, no triage run, no hint

    # ── Written by retrieve_node ────────────────────────────────────────────
    retrieved_clauses: list   # list[parsing.clause_parser.Clause]

    # ── Written by triage_node ──────────────────────────────────────────────
    triage_label: Optional[str]
    triage_confidence: Optional[float]

    # ── Written by confidence_check_node ────────────────────────────────────
    routing_decision: Optional[str]   # "accept" | "escalate"

    # ── Written by accept_node / call_llm_node (the two terminal branches) ──
    final_label: Optional[str]
    reasoning_text: Optional[str]     # None on the accept path (no LLM call made)
    source_engine: Optional[str]      # "classifier" | "llm"
    cited_clauses: list                # list[str] excerpts
