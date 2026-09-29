"""
agent/nodes.py
───────────────
LangGraph nodes for the confidence-routed triage pipeline described in
docs/technical_architecture.md §4.4 and architecture123.md §3.

Public API (matches architecture123.md):
  retrieve_node(state) -> state
  triage_node(state) -> state
  confidence_check_node(state) -> state
  call_llm_node(state) -> state

Each node takes the AgentState dict and returns only the keys it updates —
standard LangGraph convention; the compiled graph merges the returned dict
into the running state. `accept_node` is the direct-accept counterpart to
call_llm_node (both are the two possible terminal branches after
confidence_check_node) and isn't a separate item in the architecture doc's
node list, but is the natural home for "assemble the accepted result"
rather than inlining it into confidence_check_node, keeping each node's job
singular per Section 2's component table.
"""

from __future__ import annotations

from backend.app.agent.state import AgentState
from backend.app.triage_model.infer import predict as triage_predict
from backend.app.vectorstore.chroma_client import query, gap_filter
from backend.app.logging_config import get_logger, log_exception, log_step

logger = get_logger(__name__)


def retrieve_node(state: AgentState) -> dict:
    """
    Semantic retrieval + adaptive gap filter for the active hypothesis.

    Reads:  collection, embedder, hypothesis
    Writes: retrieved_clauses (list[Clause], gap-filtered, best-first)
    """
    collection = state["collection"]
    embedder = state["embedder"]
    hypothesis = state["hypothesis"]
    doc_id = state.get("document_id", "?")

    n_clauses = collection.count()
    log_step(logger, "retrieve.start", doc_id=doc_id, hypothesis=hypothesis[:80],
             n_indexed_clauses=n_clauses)

    if n_clauses == 0:
        # Real failure mode, not hypothetical: an empty collection (e.g.
        # clause_parser produced 0 clauses for a scanned PDF — see its own
        # warning) reaches here silently otherwise, and every hypothesis
        # for this doc quietly becomes NotMentioned with zero clauses cited.
        logger.warning("retrieve_node: collection is empty (doc_id=%s) - "
                       "triage_node will short-circuit to NotMentioned.", doc_id)
        return {"retrieved_clauses": []}

    try:
        candidates = query(
            collection, hypothesis, k=n_clauses, embedder=embedder, with_scores=True
        )
        selected = gap_filter(candidates)
    except Exception:
        log_exception(logger, "retrieve_node failed", doc_id=doc_id,
                      hypothesis=hypothesis[:80], n_indexed_clauses=n_clauses)
        raise
    clauses = [clause for clause, _ in selected]

    log_step(logger, "retrieve.done", doc_id=doc_id, n_candidates=len(candidates),
             n_kept=len(clauses))
    return {"retrieved_clauses": clauses}


def triage_node(state: AgentState) -> dict:
    """
    Runs the triage classifier on the single most relevant (Rank-1) retrieved
    clause against the hypothesis. The triage classifier is a pairwise
    (premise, hypothesis) model, not a multi-clause reasoner — synthesizing
    across several clauses together is exactly what escalation to the LLM is
    for, per Section 2's component table ("Triage Classifier: fast label +
    confidence" / "Does NOT: explain why" or reason over multiple clauses).

    Reads:  retrieved_clauses, hypothesis
    Writes: triage_label, triage_confidence
    """
    clauses = state["retrieved_clauses"]
    hypothesis = state["hypothesis"]
    doc_id = state.get("document_id", "?")

    if not clauses:
        # Nothing survived retrieval — confidently NotMentioned, no LLM call needed.
        log_step(logger, "triage.skip", doc_id=doc_id, reason="no retrieved clauses")
        return {"triage_label": "NotMentioned", "triage_confidence": 1.0}

    top_clause = clauses[0]
    try:
        label, confidence = triage_predict(top_clause.text, hypothesis)
    except Exception:
        log_exception(logger, "triage_node failed", doc_id=doc_id,
                      hypothesis=hypothesis[:80], clause_id=getattr(top_clause, "id", "?"))
        raise
    log_step(logger, "triage.done", doc_id=doc_id, label=label,
             confidence=round(confidence, 4))
    return {"triage_label": label, "triage_confidence": confidence}


def confidence_check_node(state: AgentState) -> dict:
    """
    Compares triage confidence against the frozen threshold and decides
    whether to accept the classifier's label directly or escalate to the LLM.

    Reads:  triage_confidence, threshold
    Writes: routing_decision ("accept" | "escalate")
    """
    confidence = state["triage_confidence"]
    threshold = state["threshold"]
    decision = "accept" if confidence >= threshold else "escalate"
    log_step(logger, "route.decision", doc_id=state.get("document_id", "?"),
             confidence=round(confidence, 4), threshold=threshold, decision=decision)
    return {"routing_decision": decision}


def accept_node(state: AgentState) -> dict:
    """
    Direct-accept terminal branch — reached when routing_decision == "accept".
    No LLM call; assembles the final result straight from the triage label.

    Reads:  triage_label, retrieved_clauses
    Writes: final_label, reasoning_text, source_engine, cited_clauses
    """
    clauses = state["retrieved_clauses"]
    log_step(logger, "accept.done", doc_id=state.get("document_id", "?"),
             label=state["triage_label"])
    return {
        "final_label": state["triage_label"],
        "reasoning_text": None,
        "source_engine": "classifier",
        "cited_clauses": [c.text for c in clauses[:1]],
    }


def call_llm_node(state: AgentState) -> dict:
    """
    Terminal branch reached two ways: routing_decision == "escalate" (Configs
    B/C), or directly from retrieve when skip_triage is set (Config A). Sends
    all gap-filtered clauses to the LLM in a single call, plus the triage
    pre-label via prompts.build_reasoning_prompt's triage_label hook — which
    is absent on the Config A path, since triage never ran.

    Reads:  retrieved_clauses, hypothesis, triage_label, llm_client
    Writes: final_label, reasoning_text, source_engine, cited_clauses
    """
    llm_client = state["llm_client"]
    clauses = state["retrieved_clauses"]
    hypothesis = state["hypothesis"]
    triage_label = state.get("triage_label") or ""
    doc_id = state.get("document_id", "?")

    log_step(logger, "call_llm.start", doc_id=doc_id, n_clauses=len(clauses),
             triage_label=triage_label or "(none, Config A)")
    clause_texts = [c.text for c in clauses]
    try:
        result = llm_client.query_llm(clause_texts, hypothesis, triage_label=triage_label)
    except Exception:
        log_exception(logger, "call_llm_node failed", doc_id=doc_id,
                      n_clauses=len(clauses), hypothesis=hypothesis[:80])
        raise
    log_step(logger, "call_llm.done", doc_id=doc_id, label=result.label)

    return {
        "final_label": result.label,
        "reasoning_text": result.reasoning,
        "source_engine": "llm",
        "cited_clauses": result.cited_clauses,
    }
