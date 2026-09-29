"""
agent/graph.py
───────────────
Wires the routing nodes into the LangGraph state machine described in
docs/technical_architecture.md §4.4 and architecture123.md §3 (agent/graph.py).

Public API (matches architecture123.md):
  build_graph() -> compiled graph, ready to .invoke(initial_state)

Usage::

    from backend.app.agent.graph import build_graph

    graph = build_graph()
    final_state = graph.invoke({
        "hypothesis": hypothesis_text,
        "collection": collection,      # chromadb.Collection, already populated
        "embedder": embedder,          # Embedder, already .load()-ed
        "llm_client": llm_client,      # OllamaClient
        "threshold": 0.95,             # frozen on dev, see experiment_runner.FROZEN_THRESHOLD
        "skip_triage": False,          # True = Config A (pure LLM baseline)
    })
    print(final_state["final_label"], final_state["source_engine"])
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from backend.app.agent.state import AgentState
from backend.app.agent.nodes import (
    retrieve_node,
    triage_node,
    confidence_check_node,
    accept_node,
    call_llm_node,
)
from backend.app.logging_config import get_logger

logger = get_logger(__name__)


def _route(state: AgentState) -> str:
    """Conditional edge: reads the decision written by confidence_check_node."""
    return state["routing_decision"]


def _after_retrieve(state: AgentState) -> str:
    """Config A bypasses triage entirely: no classifier inference, no hint in the prompt."""
    return "call_llm" if state.get("skip_triage") else "triage"


def build_graph():
    """
    Build and compile the confidence-routed triage graph:

        retrieve -> triage -> confidence_check --accept----> accept    -> END
            |                                  \--escalate--> call_llm -> END
            \--skip_triage (Config A) -----------------------> call_llm -> END

    Returns:
        A compiled graph exposing .invoke(initial_state) -> AgentState.
    """
    graph = StateGraph(AgentState)

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("triage", triage_node)
    graph.add_node("confidence_check", confidence_check_node)
    graph.add_node("accept", accept_node)
    graph.add_node("call_llm", call_llm_node)

    graph.set_entry_point("retrieve")
    graph.add_conditional_edges(
        "retrieve",
        _after_retrieve,
        {"triage": "triage", "call_llm": "call_llm"},
    )
    graph.add_edge("triage", "confidence_check")
    graph.add_conditional_edges(
        "confidence_check",
        _route,
        {"accept": "accept", "escalate": "call_llm"},
    )
    graph.add_edge("accept", END)
    graph.add_edge("call_llm", END)

    compiled = graph.compile()
    logger.debug("Confidence-routed triage graph compiled "
                "(nodes: retrieve, triage, confidence_check, accept, call_llm)")
    return compiled
