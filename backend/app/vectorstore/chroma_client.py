"""
vectorstore/chroma_client.py
────────────────────────────
ChromaDB wrapper: init, add, and semantic query.

Public API (matches architecture123.md):
  init_collection(name: str) -> Collection
  add_clauses(collection, clauses: list[Clause], embeddings: np.ndarray) -> None
  query(collection, query_text: str, k: int = 5, *, with_scores: bool = False,
        embedder=None, query_embedding=None) -> list
      with_scores=False  → list[Clause]  (existing behaviour)
      with_scores=True   → list[tuple[Clause, float]]  (Clause, cosine_distance)
  gap_filter(candidates, gap_threshold=GAP_THRESHOLD) -> list[tuple[Clause, float]]
      Adaptive cutoff: always keeps Rank-1; drops subsequent candidates the
      moment a relative gap > GAP_THRESHOLD appears between consecutive scores.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np

try:
    # This file previously had only a TYPE_CHECKING-guarded backend.app
    # reference (never executed at runtime) — no real dependency. Falling
    # back to a plain logger (rather than letting this import fail)
    # preserves that if it's ever imported from a context without the repo
    # root on sys.path.
    from backend.app.logging_config import get_logger, log_exception, log_step
except ImportError:
    import logging as _logging

    def get_logger(name):
        return _logging.getLogger(name)

    def log_step(logger, step, **context):
        logger.info("STEP %s | %s", step, context)

    def log_exception(logger, msg, **context):
        logger.error("FAILED %s | %s", msg, context, exc_info=True)

logger = get_logger(__name__)

if TYPE_CHECKING:
    from chromadb import Collection
    from backend.app.parsing.clause_parser import Clause
    from backend.app.embeddings.embedder import Embedder


# ─────────────────────────────────────────────────────────────────────────────
# Client singleton (in-memory by default; swap path for persistence)
# ─────────────────────────────────────────────────────────────────────────────

_client = None


def _get_client():
    """Return (and lazily create) the module-level ChromaDB client."""
    global _client
    if _client is None:
        try:
            import chromadb  # type: ignore
        except ImportError:
            logger.error("chromadb is not installed - cannot create client.")
            raise ImportError(
                "chromadb is not installed.\nRun: pip install chromadb"
            )
        # EphemeralClient is the non-deprecated in-memory client (chromadb >= 0.4)
        try:
            _client = chromadb.EphemeralClient()
            logger.debug("Created ephemeral (in-memory) ChromaDB client.")
        except AttributeError:
            # Fallback for older chromadb versions
            _client = chromadb.Client()  # type: ignore
            logger.debug("chromadb.EphemeralClient unavailable - used legacy Client().")
    return _client


def get_persistent_client(path: str):
    """
    Return a persistent ChromaDB client writing to `path`.
    Call this instead of the implicit in-memory client when you need
    data to survive restarts.
    """
    try:
        import chromadb  # type: ignore
    except ImportError:
        logger.error("chromadb is not installed - cannot create persistent client.")
        raise ImportError("chromadb is not installed.\nRun: pip install chromadb")
    try:
        client = chromadb.PersistentClient(path=path)
    except Exception:
        log_exception(logger, "PersistentClient creation failed", path=path)
        raise
    logger.info("Opened persistent ChromaDB client at %s", path)
    return client


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def init_collection(name: str, client=None):
    """
    Get or create a ChromaDB collection with cosine distance.

    Args:
        name:   Collection name (e.g. "doc_42_clauses").
        client: Optional ChromaDB client. If None, uses the module-level
                in-memory client.

    Returns:
        chromadb.Collection
    """
    if client is None:
        client = _get_client()

    import chromadb  # type: ignore

    collection = client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


# ─────────────────────────────────────────────────────────────────────────────
# Adaptive gap filter
# ─────────────────────────────────────────────────────────────────────────────

# Relative gap threshold: keep a candidate if its score is within this
# fraction of the previous candidate's score.  0.15 means "within 15%".
# BGE-small-en cosine distances for genuinely similar NDA clauses typically
# differ by ≪0.10; a large semantic jump (relevant→off-topic) is ~0.15–0.30,
# making 15% a robust natural breakpoint.
GAP_THRESHOLD: float = 0.15


def gap_filter(
    candidates: list,
    gap_threshold: float = GAP_THRESHOLD,
) -> list:
    """
    Adaptive similarity-gap cutoff on a ranked list of (Clause, distance) pairs.

    Always keeps the top-ranked candidate.  For each subsequent candidate,
    keeps it only if its cosine distance is within `gap_threshold` (relative)
    of candidates[0]'s distance — the fixed Rank-1 anchor, never updated.
    Stops the moment a candidate exceeds the ceiling.

    Using Rank-1 as the fixed anchor prevents gradual drift: with a chained
    comparison (each vs previous), a long sequence of small increments can
    accumulate into a large total deviation that still passes.  The anchored
    comparison enforces a hard relevance band relative to the best match.

    Args:
        candidates:    Ordered list of (Clause, float) from query(with_scores=True).
                       Must be sorted best-first (lowest distance first).
        gap_threshold: Maximum allowed relative deviation from the Rank-1 score.
                       Default is GAP_THRESHOLD = 0.15 (15%).
                       Ceiling = candidates[0][1] * (1 + gap_threshold).

    Returns:
        Filtered list of (Clause, float) — 1 to len(candidates) items.

    Example (anchored, GAP_THRESHOLD=0.15):
        scores  = [0.178, 0.186, 0.202, 0.205, 0.279]
        ceiling = 0.178 * 1.15 = 0.2047
        kept    = [0.178, 0.186, 0.202, 0.205]   # 0.279 > ceiling → stop
    """
    if not candidates:
        logger.debug("gap_filter() called with 0 candidates.")
        return []

    kept       = [candidates[0]]
    best_score = candidates[0][1]   # fixed anchor — never updates
    ceiling    = best_score * (1.0 + gap_threshold)

    for clause, score in candidates[1:]:
        if score <= ceiling:
            kept.append((clause, score))
        else:
            break  # outside the relevance band of Rank-1 — stop

    logger.debug(
        "gap_filter: kept %d/%d candidates (rank1=%.4f, ceiling=%.4f)",
        len(kept), len(candidates), best_score, ceiling,
    )
    return kept


def add_clauses(
    collection,
    clauses: list,
    embeddings: np.ndarray,
) -> None:
    """
    Upsert clauses + their embeddings into the collection.

    Args:
        collection: chromadb.Collection from init_collection().
        clauses:    list[Clause] — must be the same length as embeddings.
        embeddings: np.ndarray of shape (N, D), one row per clause.

    Raises:
        ValueError: if lengths don't match.
    """
    if len(clauses) != len(embeddings):
        logger.error(
            "add_clauses() length mismatch: %d clauses vs %d embeddings",
            len(clauses), len(embeddings),
        )
        raise ValueError(
            f"clauses ({len(clauses)}) and embeddings ({len(embeddings)}) "
            "must have the same length."
        )

    ids        = [c.id for c in clauses]
    documents  = [c.text for c in clauses]
    metadatas  = [
        {
            "page_num":        c.page_num,
            "section_heading": c.section_heading,
            "char_len":        len(c.text),
        }
        for c in clauses
    ]
    embedding_list = embeddings.tolist()

    try:
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embedding_list,
            metadatas=metadatas,
        )
    except Exception:
        log_exception(logger, "collection.upsert() failed",
                      collection=getattr(collection, "name", "?"),
                      n_clauses=len(clauses))
        raise
    logger.debug("add_clauses: upserted %d clauses into collection=%s",
                len(clauses), getattr(collection, "name", "?"))


def query(
    collection,
    query_text: str,
    k: int = 5,
    *,
    embedder=None,
    query_embedding: Optional[np.ndarray] = None,
    with_scores: bool = False,
) -> list:
    """
    Semantic retrieval: return the top-k clauses most similar to query_text.

    Exactly one of `embedder` or `query_embedding` must be provided:
      - embedder:        An Embedder instance (embeds query_text on the fly).
      - query_embedding: Pre-computed 1-D np.ndarray for query_text.

    Args:
        collection:      chromadb.Collection.
        query_text:      The hypothesis / search string.
        k:               Number of results to return from ChromaDB.
        embedder:        Optional Embedder to embed query_text.
        query_embedding: Optional pre-computed embedding vector.
        with_scores:     If False (default) return list[Clause] — backward-
                         compatible.  If True, return list[tuple[Clause, float]]
                         where the float is the cosine distance (lower = better).

    Returns:
        list[Clause] when with_scores=False (default).
        list[tuple[Clause, float]] when with_scores=True, ordered best-first.
    """
    # ── Resolve query vector ──────────────────────────────────────────────────
    if query_embedding is not None:
        vec = np.asarray(query_embedding, dtype=np.float32)
    elif embedder is not None:
        vec = embedder.embed([query_text])[0]
    else:
        logger.error("query() called with neither 'embedder' nor 'query_embedding'.")
        raise ValueError(
            "Provide either 'embedder' or 'query_embedding' to query()."
        )

    # ── ChromaDB query ──────────────────────────────────────────────────────
    n_results = min(k, collection.count())
    try:
        results = collection.query(
            query_embeddings=[vec.tolist()],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        log_exception(logger, "collection.query() failed",
                      collection=getattr(collection, "name", "?"),
                      k=k, n_results=n_results, query_text=query_text[:80])
        raise
    logger.debug("query: collection=%s k=%d -> %d results (top_dist=%s)",
                getattr(collection, "name", "?"), k, n_results,
                results["distances"][0][0] if results["distances"][0] else "n/a")

    # ── Reconstruct Clause objects ────────────────────────────────────────────
    # Import here to avoid circular imports at module level.
    from backend.app.parsing.clause_parser import Clause  # type: ignore

    pairs: list = []
    for doc_id, doc_text, meta, dist in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        clause = Clause(
            id=doc_id,
            text=doc_text,
            page_num=int(meta.get("page_num", 0)),
            section_heading=str(meta.get("section_heading", "")),
        )
        pairs.append((clause, float(dist)))

    if with_scores:
        return pairs
    return [clause for clause, _ in pairs]
