"""
backend/app/retrieval_accuracy_check.py
────────────────────────────────────────
Retrieval-only accuracy check across the full test.json dataset (123 docs).

For every Entailment / Contradiction hypothesis:
  1. Map gold evidence spans (char-offset pairs from doc["spans"]) to the
     parsed Clause(s) that contain them via substring matching.
  2. Run retrieval + gap_filter (same logic as the main pipeline).
  3. Record INCLUDED / MISSING / UNMATCHED.

Statuses:
  INCLUDED  -- at least one gold-evidence clause survived gap_filter.
  MISSING   -- gold clause(s) were mapped successfully but none survived
               gap_filter (true retrieval failure).
  UNMATCHED -- no parsed clause contains the gold span text (parsing gap,
               not a retrieval failure; tracked separately).

Zero LLM calls -- only embedding + ChromaDB queries.

Usage:
    python backend/app/retrieval_accuracy_check.py

Dependencies:
    pip install sentence-transformers chromadb
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Reconfigure stdout to UTF-8 with replacement on unencodable characters.
# os.environ.setdefault() above only affects child processes; it does NOT
# change the already-open stdout stream.  Some PDFs contain private-use
# Unicode characters (e.g. U+F0B7, a bullet glyph) that cp1252 cannot encode,
# causing a UnicodeEncodeError when printing gold span text on Windows.
# errors='replace' substitutes '?' for any unencodable character.
if hasattr(sys.stdout, "reconfigure"):          # Python 3.7+
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ── Repo root on sys.path so package imports resolve ─────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent      # backend/app/
REPO_ROOT   = SCRIPT_DIR.parent.parent             # edgelegal/
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.parsing.clause_parser import PageBlock, segment_clauses
from backend.app.embeddings.embedder import Embedder
from backend.app.vectorstore.chroma_client import (
    init_collection, add_clauses, query, gap_filter, GAP_THRESHOLD,
)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

TEST_JSON = REPO_ROOT / "backend" / "data" / "contractnli" / "test.json"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sep(char: str = "=", width: int = 68) -> str:
    """ASCII separator line."""
    return char * width


def _preview(text: str, max_chars: int = 80) -> str:
    text = text.replace("\n", " ")
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def load_test_data() -> tuple[list[dict], dict[str, str]]:
    """
    Load test.json.

    Returns:
        (documents, hyp_texts) where hyp_texts is {hyp_id: hypothesis_string}.
    """
    if not TEST_JSON.exists():
        print(f"[ERROR] test.json not found at {TEST_JSON}")
        print("  Run: python backend/app/data_setup.py first.")
        sys.exit(1)

    with TEST_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    documents = data["documents"]
    hyp_texts = {hid: v["hypothesis"] for hid, v in data["labels"].items()}
    return documents, hyp_texts


def gold_span_texts(doc: dict, span_indices: list[int]) -> list[str]:
    """
    Resolve annotation span indices to their gold evidence text strings.

    doc["spans"]  : list of [start_char, end_char] pairs (sentence-level)
    span_indices  : list of int indices into doc["spans"]
    """
    doc_spans = doc["spans"]
    doc_text  = doc["text"]
    texts = []
    for si in span_indices:
        start, end = doc_spans[si]
        texts.append(doc_text[start:end])
    return texts


def map_gold_to_clauses(gold_texts: list[str], clauses: list) -> list[str]:
    """
    Return the IDs of clauses whose text contains at least one gold span
    as a substring.  Uses exact substring matching after stripping leading /
    trailing whitespace from the gold span (same approach as doc-408 diagnostic).

    Returns an empty list if no clause contains any gold span (UNMATCHED --
    a parsing gap, not a retrieval failure).
    """
    matched_ids: list[str] = []
    for clause in clauses:
        for gt in gold_texts:
            if gt.strip() and gt.strip() in clause.text:
                matched_ids.append(clause.id)
                break  # one gold-span match per clause is sufficient
    return matched_ids


# ─────────────────────────────────────────────────────────────────────────────
# Main check loop
# ─────────────────────────────────────────────────────────────────────────────

def run_retrieval_check() -> None:
    print()
    print(_sep())
    print("  EdgeLegal -- Retrieval-Only Accuracy Check (test.json)")
    print(_sep())
    print(f"  Test JSON  : {TEST_JSON}")
    print(f"  Gap filter : threshold = {GAP_THRESHOLD:.0%} (relative, anchored at Rank-1)")
    print()

    # -- Load data ------------------------------------------------------------
    documents, hyp_texts = load_test_data()
    print(f"  Loaded {len(documents)} documents, {len(hyp_texts)} hypotheses")
    print()

    # -- Load embedder once (downloaded on first run, cached afterward) -------
    print("  Loading embedder (BAAI/bge-small-en) ...")
    embedder = Embedder()
    embedder.load()
    print(f"  Loaded: {embedder}")
    print()
    print(_sep("-"))

    results: list[dict] = []

    # -- Per-document loop ----------------------------------------------------
    for doc_idx, doc in enumerate(documents, start=1):
        doc_id      = doc["id"]
        fname       = doc.get("file_name", "unknown")
        fname_short = fname[:50]

        # Parse clauses from the raw contract text
        pages   = [PageBlock(text=doc["text"], page_num=0, bbox=None)]
        clauses = segment_clauses(pages)

        # Namespace clause IDs to avoid ChromaDB collisions across documents
        for c in clauses:
            c.id = f"doc{doc_id}_{c.id}"

        n_clauses = len(clauses)

        if n_clauses == 0:
            print(
                f"  [{doc_idx:3d}/123] id={doc_id:<6} SKIP -- 0 clauses parsed"
                f"  ({fname_short})"
            )
            continue

        # Embed clause texts and store in a fresh in-memory ChromaDB collection
        texts      = [c.text for c in clauses]
        embeddings = embedder.embed(texts)
        coll_name  = f"rc_{doc_id}"   # rc = retrieval_check
        collection = init_collection(coll_name)
        add_clauses(collection, clauses, embeddings)

        # Gather annotations
        ann_sets = doc.get("annotation_sets", [])
        if not ann_sets:
            print(
                f"  [{doc_idx:3d}/123] id={doc_id:<6} SKIP -- no annotation_sets"
                f"  ({fname_short})"
            )
            continue

        annotations = ann_sets[0].get("annotations", {})
        ec_count = 0   # E/C hypotheses processed for this document

        for hyp_id, ann in annotations.items():
            choice = ann.get("choice", "")

            # NotMentioned: no gold evidence clause exists -- skip per spec
            if choice == "NotMentioned":
                continue

            ec_count     += 1
            span_indices  = ann.get("spans", [])
            hyp_text      = hyp_texts.get(hyp_id, "")

            # -- Resolve gold span char-offsets to text strings ---------------
            g_texts = gold_span_texts(doc, span_indices)

            # -- Map gold span texts to parsed clause IDs ---------------------
            gold_ids = map_gold_to_clauses(g_texts, clauses)

            if not gold_ids:
                # Gold span text not substring of any parsed clause -- parsing gap
                results.append({
                    "doc_id":        doc_id,
                    "file_name":     fname,
                    "hyp_id":        hyp_id,
                    "choice":        choice,
                    "status":        "UNMATCHED",
                    "gold_texts":    g_texts,
                    "gold_ids":      [],
                    "filtered_ids":  [],
                    "n_candidates":  0,
                    "n_filtered":    0,
                    "rank1_id":      "",
                    "rank1_score":   0.0,
                    "rank1_preview": "",
                })
                continue

            # -- Retrieve + gap-filter (identical to main pipeline) -----------
            candidates = query(
                collection,
                hyp_text,
                k=n_clauses,          # retrieve ALL clauses, let gap_filter decide
                embedder=embedder,
                with_scores=True,
            )
            filtered     = gap_filter(candidates)
            filtered_ids = {c.id for c, _ in filtered}

            rank1_clause, rank1_score = candidates[0] if candidates else (None, 0.0)
            rank1_id      = rank1_clause.id       if rank1_clause else ""
            rank1_preview = _preview(rank1_clause.text) if rank1_clause else ""

            # INCLUDED = at least one gold clause ID is in the gap-filtered set
            included = bool(set(gold_ids) & filtered_ids)
            status   = "INCLUDED" if included else "MISSING"

            results.append({
                "doc_id":        doc_id,
                "file_name":     fname,
                "hyp_id":        hyp_id,
                "choice":        choice,
                "status":        status,
                "gold_texts":    g_texts,
                "gold_ids":      gold_ids,
                "filtered_ids":  sorted(filtered_ids),
                "n_candidates":  len(candidates),
                "n_filtered":    len(filtered),
                "rank1_id":      rank1_id,
                "rank1_score":   rank1_score,
                "rank1_preview": rank1_preview,
            })

        print(
            f"  [{doc_idx:3d}/123] id={doc_id:<6}  {n_clauses:3d} clauses  "
            f"{ec_count:2d} E/C hyps  ({fname_short})"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────

    print()
    print(_sep())
    print("  RESULTS SUMMARY")
    print(_sep())

    n_total     = len(results)
    n_included  = sum(1 for r in results if r["status"] == "INCLUDED")
    n_missing   = sum(1 for r in results if r["status"] == "MISSING")
    n_unmatched = sum(1 for r in results if r["status"] == "UNMATCHED")

    # Retrieval accuracy is computed only over cases where we could map the
    # gold span to a parsed clause (i.e., excluding UNMATCHED).
    n_checkable  = n_total - n_unmatched
    pct_included = (n_included / n_checkable * 100) if n_checkable else 0.0
    pct_missing  = (n_missing  / n_checkable * 100) if n_checkable else 0.0
    pct_unmatched = (n_unmatched / n_total * 100) if n_total else 0.0

    print()
    print(f"  Total E/C cases checked     : {n_total:4d}")
    print(f"  Checkable (span mapped OK)  : {n_checkable:4d}")
    print(f"  Gold clause INCLUDED        : {n_included:4d}  ({pct_included:.1f}%)")
    print(f"  Gold clause MISSING         : {n_missing:4d}  ({pct_missing:.1f}%)")
    print(
        f"  Gold span UNMATCHED         : {n_unmatched:4d}  ({pct_unmatched:.1f}% of total"
        f" -- parsing gap, not retrieval failure)"
    )
    print()

    # -- Per-label breakdown --------------------------------------------------
    for label in ("Entailment", "Contradiction"):
        subset    = [r for r in results if r["choice"] == label and r["status"] != "UNMATCHED"]
        sub_incl  = sum(1 for r in subset if r["status"] == "INCLUDED")
        sub_total = len(subset)
        sub_pct   = (sub_incl / sub_total * 100) if sub_total else 0.0
        print(
            f"    {label:<15s} checkable={sub_total:3d}  "
            f"included={sub_incl:3d}  ({sub_pct:.1f}%)"
        )
    print()

    # ── MISSING detail block ─────────────────────────────────────────────────
    missing_results = [r for r in results if r["status"] == "MISSING"]
    if missing_results:
        print(_sep("-"))
        print(f"  MISSING cases ({n_missing}) -- retrieval failures:")
        print(_sep("-"))
        for r in missing_results:
            print()
            print(f"  doc_id={r['doc_id']}  hyp={r['hyp_id']}  choice={r['choice']}")
            print(f"  File : {r['file_name'][:70]}")
            print(f"  Gold clause ID(s) : {r['gold_ids']}")
            print(f"  Gold span text(s) :")
            for gt in r["gold_texts"]:
                print(f"    \"{_preview(gt, 100)}\"")
            print(
                f"  Gap-filter : {r['n_candidates']} candidates -> "
                f"{r['n_filtered']} kept  (threshold={GAP_THRESHOLD:.0%})"
            )
            print(f"  Rank-1 retrieved  : id={r['rank1_id']}  dist={r['rank1_score']:.4f}")
            print(f"  Rank-1 preview    : \"{r['rank1_preview']}\"")
            print(f"  Filtered IDs      : {r['filtered_ids']}")
    else:
        print("  No MISSING cases -- all gold clauses were retrieved and passed gap_filter!")

    # ── UNMATCHED detail block ───────────────────────────────────────────────
    unmatched_results = [r for r in results if r["status"] == "UNMATCHED"]
    if unmatched_results:
        print()
        print(_sep("-"))
        print(f"  UNMATCHED cases ({n_unmatched}) -- gold span not found in any parsed clause:")
        print(_sep("-"))
        for r in unmatched_results:
            print()
            print(f"  doc_id={r['doc_id']}  hyp={r['hyp_id']}  choice={r['choice']}")
            print(f"  File : {r['file_name'][:70]}")
            print(f"  Gold span text(s) :")
            for gt in r["gold_texts"]:
                print(f"    \"{_preview(gt, 100)}\"")

    print()
    print(_sep())
    print("  Done.")
    print(_sep())


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_retrieval_check()
