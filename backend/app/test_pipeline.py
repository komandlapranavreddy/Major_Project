"""
backend/app/test_pipeline.py
No-triage pipeline smoke test (Configuration A).

Phase 1: Clause quality audit
  - Loads 6 varied documents from backend/data/contractnli/train.json
  - Segments each into clauses using clause_parser.segment_clauses()
  - Prints every clause with its index and character length
  - Flags clauses that are abnormally short (<20 chars) or long (>2000 chars)

Phase 2: End-to-end retrieval + LLM evaluation (all 17 hypotheses)
  - Embeds Phase-1 clauses for doc id=34 (UNHCR NDA) → stores in ChromaDB
  - For each of the 17 NDA hypotheses:
      • Retrieves top 3 clauses semantically closest to the hypothesis
      • Sends the top clause + hypothesis to Ollama (llama3.1:8b, Config A:
        no triage pre-label)
      • Records predicted label vs. gold label from train.json annotations
  - Prints a per-hypothesis summary table and final accuracy score
  - If Ollama is not running, prints [SKIP] and exits cleanly.

Phase 3: Multi-document held-out evaluation on test.json
  - Samples 6 documents from backend/data/contractnli/test.json
  - For each document: parse → embed → store in ChromaDB → run all 17
    hypotheses through retrieve + LLM (Config A: no triage)
  - Prints live progress per hypothesis, per document
  - After each document: prints that document's accuracy
  - After all documents: prints pooled overall accuracy
  - Prints an error-type breakdown:
      • Missed detection  (Predicted NotMentioned, Gold = Entailment/Contradiction)
      • False positive    (Predicted Entailment/Contradiction, Gold = NotMentioned)
      • Label confusion   (Entailment ↔ Contradiction swap)

Phase 4: Diagnostic deep-dive — doc id=408 (worst performer in Phase 3)
  - Re-processes only doc id=408 (817516_…exh99_4sept2005.txt, 29.4%)
  - For every MISMATCH prints full diagnostic detail:
      • Full hypothesis text
      • All 3 retrieved clauses (complete text, untruncated)
      • Which clause was sent to the LLM
      • LLM predicted label + full reasoning
      • LLM cited clauses (if returned) + gold label
  - MATCH hypotheses get a compact one-liner
  - Ends with a mini accuracy + error-type summary for this document

Usage:
    python backend/app/test_pipeline.py

Dependencies:
    pip install sentence-transformers chromadb
    (Ollama optional for Phase 2 and Phase 3)
"""

from __future__ import annotations

import json
import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
import sys
import textwrap
from pathlib import Path

# ── Ensure the repo root is on sys.path so relative imports resolve ──────────
SCRIPT_DIR = Path(__file__).resolve().parent       # backend/app/
REPO_ROOT   = SCRIPT_DIR.parent.parent             # edgelegal/
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.logging_config import get_logger, log_exception

logger = get_logger(__name__)

from backend.app.parsing.clause_parser import PageBlock, segment_clauses
from backend.app.embeddings.embedder import Embedder
from backend.app.vectorstore.chroma_client import (
    init_collection, add_clauses, query, gap_filter, GAP_THRESHOLD,
)
from backend.app.llm.ollama_client import OllamaClient, OllamaConnectionError

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

TRAIN_JSON = REPO_ROOT / "backend" / "data" / "contractnli" / "train.json"
TEST_JSON  = REPO_ROOT / "backend" / "data" / "contractnli" / "test.json"

# 6 indices spread across the 423-document training set for variety.
# Not sequential — picks from the start, middle, and end.
SAMPLE_INDICES = [0, 70, 140, 210, 280, 350]

# 6 indices spread across the 123-document test set for Phase 3.
# Indices 80 and 100 are skipped — both parse to only 1 clause,
# making k=3 retrieval meaningless.  82 (21 clauses) and 96 (17 clauses)
# are used as replacements.
TEST_SAMPLE_INDICES = [0, 20, 40, 60, 82, 96]

# doc id for the Phase 4 diagnostic (worst-performing doc in Phase 3)
# index 82 in test.json — 817516_0001014909-05-000102_exh99_4sept2005.txt
DIAG_DOC_ID = 408

# Thresholds for flagging (not for splitting)
MIN_CLAUSE_CHARS = 20
MAX_CLAUSE_CHARS = 2000

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_train_documents() -> list[dict]:
    """Load all documents from train.json."""
    with TRAIN_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data["documents"]


def doc_to_page_block(doc: dict) -> list[PageBlock]:
    """Wrap a JSON document's text as a single synthetic PageBlock."""
    return [PageBlock(text=doc["text"], page_num=0, bbox=None)]


def gold_label(doc: dict, hyp_id: str) -> str:
    """Return the gold NLI label for a given hypothesis in a document."""
    ann_sets = doc.get("annotation_sets", [])
    if ann_sets:
        return ann_sets[0]["annotations"].get(hyp_id, {}).get("choice", "?")
    return "?"


def load_hypothesis_texts() -> dict:
    """Return {hyp_id: hypothesis_text} from train.json top-level 'labels' dict."""
    with TRAIN_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {hid: v["hypothesis"] for hid, v in data["labels"].items()}


def load_test_documents() -> list[dict]:
    """Load all documents from the held-out test.json."""
    with TEST_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data["documents"]


def _sep(char: str = "=", width: int = 68) -> str:
    # Use only ASCII chars to avoid cp1252 encode errors on Windows terminals.
    safe = char if ord(char) < 128 else "-"
    return safe * width


def _preview(text: str, max_chars: int = 80) -> str:
    text = text.replace("\n", " ")
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Clause quality audit
# ─────────────────────────────────────────────────────────────────────────────

def phase1_clause_audit(docs: list[dict]) -> dict[int, list]:
    """
    For each sampled document, segment into clauses and print a quality report.
    Returns {doc_index: list[Clause]} for use in Phase 2.
    """
    print(_sep())
    print("  PHASE 1 — Clause Quality Audit")
    print(_sep())

    results: dict[int, list] = {}

    for sample_idx, doc_idx in enumerate(SAMPLE_INDICES):
        doc = docs[doc_idx]
        doc_id   = doc["id"]
        filename = doc.get("file_name", "unknown")[:60]
        text_len = len(doc["text"])
        gold_span_count = len(doc.get("spans", []))

        pages   = doc_to_page_block(doc)
        clauses = segment_clauses(pages)

        # Assign namespaced IDs so ChromaDB keys are unique across docs
        for c in clauses:
            c.id = f"doc{doc_id}_{c.id}"

        results[doc_idx] = clauses

        short_count = sum(1 for c in clauses if len(c.text) < MIN_CLAUSE_CHARS)
        long_count  = sum(1 for c in clauses if len(c.text) > MAX_CLAUSE_CHARS)

        print()
        print(_sep("-"))
        print(f"  Doc [{sample_idx+1}/6]  id={doc_id}  idx={doc_idx}")
        print(f"  File    : {filename}")
        print(f"  Text    : {text_len:,} chars")
        print(f"  Gold spans (annotator): {gold_span_count}")
        print(f"  Parsed clauses: {len(clauses)}  "
              f"  SHORT(<{MIN_CLAUSE_CHARS}): {short_count}  "
              f"  LONG(>{MAX_CLAUSE_CHARS}): {long_count}")
        print(_sep("-"))

        for i, clause in enumerate(clauses, start=1):
            clen = len(clause.text)
            warn = ""
            if clen < MIN_CLAUSE_CHARS:
                warn = "  *** WARNING: SHORT ***"
            elif clen > MAX_CLAUSE_CHARS:
                warn = "  *** WARNING: LONG  ***"

            heading_tag = f"[{clause.section_heading}] " if clause.section_heading else ""
            print(
                f"  [{i:3d}] ({clen:5d} chars)  "
                f"{heading_tag}{_preview(clause.text)}"
                f"{warn}"
            )

    print()
    print(_sep())
    print("  Phase 1 complete.")
    print(_sep())
    return results


# -----------------------------------------------------------------------------
# Phase 2: End-to-end retrieval + LLM evaluation (all 17 hypotheses)
# -----------------------------------------------------------------------------

def phase2_e2e_all_hypotheses(docs: list[dict], phase1_results: dict[int, list]) -> None:
    """
    Embed clauses for doc id=34, store in ChromaDB, then for each of the 17
    NDA hypotheses: retrieve top-3 clauses, call Ollama (Config A: no triage),
    record predicted vs. gold label.  Prints a summary table + accuracy score.
    """
    print()
    print(_sep())
    print("  PHASE 2 - End-to-End: Embed -> Store -> Retrieve -> LLM (all 17 hyps)")
    print(_sep())

    # Use the first sampled document (doc id=34, the UNHCR NDA)
    first_idx = SAMPLE_INDICES[0]
    doc       = docs[first_idx]
    doc_id    = doc["id"]
    clauses   = phase1_results[first_idx]

    if not clauses:
        print("  [ERROR] No clauses to embed — skipping Phase 2.")
        return

    # Load all hypothesis texts from the top-level labels dict
    hyp_texts   = load_hypothesis_texts()
    # Collect only the hypothesis IDs present in this document's annotations
    doc_hyp_ids = sorted(
        doc["annotation_sets"][0]["annotations"].keys()
    ) if doc.get("annotation_sets") else []

    print(f"\n  Document : id={doc_id}  ({doc.get('file_name', 'unknown')[:60]})")
    print(f"  Clauses  : {len(clauses)}")
    print(f"  Hypotheses to evaluate: {len(doc_hyp_ids)}")
    print()

    # -- Step 1: Embed --------------------------------------------------------
    print("  [1/4] Loading embedder (BAAI/bge-small-en) ...")
    embedder = Embedder()
    embedder.load()
    print(f"        Loaded: {embedder}")

    print(f"  [2/4] Embedding {len(clauses)} clauses ...")
    texts      = [c.text for c in clauses]
    embeddings = embedder.embed(texts)
    print(f"        Embedding shape: {embeddings.shape}")

    # -- Step 2: Store in ChromaDB --------------------------------------------
    coll_name  = f"doc_{doc_id}_clauses"
    print(f"  [3/4] Storing in ChromaDB collection '{coll_name}' ...")
    collection = init_collection(coll_name)
    add_clauses(collection, clauses, embeddings)
    print(f"        Stored {collection.count()} clauses.")

    # -- Step 3: Ollama reachability check (once, before the loop) ------------
    print()
    print(_sep("-"))
    print("  LLM Inference (Ollama - Config A: no triage pre-label)")
    print(_sep("-"))

    client = OllamaClient(model="llama3.1:8b")

    if not client.is_reachable():
        print(
            "\n  [SKIP] Ollama is not reachable at http://localhost:11434.\n"
            "         To run Phase 2 fully:\n"
            "           1. Start the server:  ollama serve\n"
            "           2. Pull the model:    ollama pull llama3.1:8b\n"
            "           3. Re-run this script."
        )
        print()
        print(_sep())
        print("  Phase 2 skipped (Ollama unavailable) — Phase 1 results are valid.")
        print(_sep())
        return

    print(f"\n  Model: {client.model}")
    print(f"  Evaluating {len(doc_hyp_ids)} hypothesis/clause pairs ...\n")

    # -- Step 4: Loop over all 17 hypotheses ----------------------------------
    # Each row: (hyp_id, predicted_label, gold_lbl, match_flag)
    rows: list[tuple[str, str, str, str]] = []

    for i, hyp_id in enumerate(doc_hyp_ids, start=1):
        hyp_text = hyp_texts.get(hyp_id, "")
        gold_lbl = gold_label(doc, hyp_id)

        # Retrieve full candidate pool (all clauses in doc), apply gap filter
        n_clauses  = collection.count()
        candidates = query(collection, hyp_text, k=n_clauses,
                          embedder=embedder, with_scores=True)
        selected   = gap_filter(candidates)

        if not selected:
            predicted = "NO_CLAUSES"
            match_flag = "MISMATCH"
            rows.append((hyp_id, predicted, gold_lbl, match_flag))
            print(
                f"  [{i:2d}/{len(doc_hyp_ids)}] {hyp_id:<10s}  "
                f"[NO_CLAUSES retrieved — skipping LLM]"
            )
            continue

        clause_texts = [c.text for c, _ in selected]

        try:
            result = client.query_llm(
                clauses=clause_texts,
                hypothesis=hyp_text,
                triage_label="",  # Config A: no triage
            )
            predicted = result.label
        except OllamaConnectionError as exc:
            predicted  = "ERROR"
            match_flag = "ERROR"
            rows.append((hyp_id, predicted, gold_lbl, match_flag))
            print(f"  [{i:2d}/{len(doc_hyp_ids)}] {hyp_id:<10s}  [ERROR] {exc}")
            continue
        except Exception as exc:  # last-resort guard: log and skip this hypothesis
            predicted  = "SKIP"
            match_flag = "SKIP"
            rows.append((hyp_id, predicted, gold_lbl, match_flag))
            print(
                f"  [{i:2d}/{len(doc_hyp_ids)}] {hyp_id:<10s}  "
                f"[SKIP] {type(exc).__name__}: {exc}"
            )
            continue

        match_flag = "MATCH" if predicted == gold_lbl else "MISMATCH"
        rows.append((hyp_id, predicted, gold_lbl, match_flag))

        print(
            f"  [{i:2d}/{len(doc_hyp_ids)}] {hyp_id:<10s}  "
            f"Predicted: {predicted:<15s}  "
            f"Gold: {gold_lbl:<15s}  "
            f"{match_flag}  [clauses sent: {len(selected)}]"
        )

    # -- Step 5: Summary table ------------------------------------------------
    print()
    print(_sep())
    print("  PHASE 2 SUMMARY — All-Hypothesis LLM Accuracy (doc id={})".
          format(doc_id))
    print(_sep())

    col_hyp  = 10
    col_pred = 15
    col_gold = 15
    col_res  = 8
    header = (
        f"  {'#':<4}{'Hyp ID':<{col_hyp}}  "
        f"{'Predicted':<{col_pred}}  "
        f"{'Gold':<{col_gold}}  "
        f"{'Result':<{col_res}}"
    )
    print(header)
    print("  " + "-" * (4 + col_hyp + 2 + col_pred + 2 + col_gold + 2 + col_res))

    correct = 0
    for idx, (hyp_id, predicted, gold_lbl, match_flag) in enumerate(rows, start=1):
        if match_flag == "MATCH":
            correct += 1
        print(
            f"  {idx:<4}{hyp_id:<{col_hyp}}  "
            f"{predicted:<{col_pred}}  "
            f"{gold_lbl:<{col_gold}}  "
            f"{match_flag:<{col_res}}"
        )

    total    = len(rows)
    pct      = (correct / total * 100) if total else 0.0
    print()
    print(_sep("-"))
    print(f"  Accuracy: {correct} / {total} correct  ({pct:.1f}%)")
    print(_sep("-"))
    print()
    print(_sep())
    print("  Phase 2 complete.")
    print(_sep())


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: Multi-document evaluation on held-out test.json
# ─────────────────────────────────────────────────────────────────────────────

def _classify_error(predicted: str, gold: str) -> str:
    """
    Classify a single mismatch into one of three error buckets.

    Missed detection : model said NotMentioned, truth was Entailment/Contradiction
    False positive   : model said Entailment/Contradiction, truth was NotMentioned
    Label confusion  : model confused Entailment <-> Contradiction
    """
    real_labels = {"Entailment", "Contradiction"}
    if predicted == "NotMentioned" and gold in real_labels:
        return "Missed detection"
    if predicted in real_labels and gold == "NotMentioned":
        return "False positive"
    if predicted in real_labels and gold in real_labels and predicted != gold:
        return "Label confusion"
    return "Other"  # e.g. ERROR or NO_CLAUSES rows


def phase3_multi_doc_eval() -> None:
    """
    Multi-document LLM evaluation on the held-out test.json split.

    For each of 6 sampled documents:
      - Parse clauses, embed, store in a fresh ChromaDB collection.
      - For all 17 hypotheses: retrieve top-3, call Ollama, compare to gold.
    Prints per-document accuracy, pooled overall accuracy, and a three-bucket
    error-type breakdown.
    """
    print()
    print(_sep("="))
    print("  PHASE 3 — Multi-Document Held-Out Evaluation (test.json)")
    print(_sep("="))
    print(f"  Test JSON : {TEST_JSON}")
    print(f"  Sampling  : indices {TEST_SAMPLE_INDICES}")
    print()

    if not TEST_JSON.exists():
        print(f"  [ERROR] {TEST_JSON} not found — skipping Phase 3.")
        return

    test_docs   = load_test_documents()
    hyp_texts   = load_hypothesis_texts()   # same label set as test split

    max_test_idx = max(TEST_SAMPLE_INDICES)
    if max_test_idx >= len(test_docs):
        print(
            f"  [ERROR] Requested index {max_test_idx} but test.json "
            f"only has {len(test_docs)} documents — skipping Phase 3."
        )
        return

    print(f"  Loaded {len(test_docs)} documents from test.json")

    # -- Load embedder once (reused across all 6 documents) -------------------
    print()
    print("  Loading embedder (BAAI/bge-small-en) — shared across all documents ...")
    embedder = Embedder()
    embedder.load()
    print(f"  Loaded: {embedder}")

    # -- Ollama reachability (once) -------------------------------------------
    client = OllamaClient(model="llama3.1:8b")
    if not client.is_reachable():
        print(
            "\n  [SKIP] Ollama is not reachable at http://localhost:11434.\n"
            "         To run Phase 3 fully:\n"
            "           1. Start the server:  ollama serve\n"
            "           2. Pull the model:    ollama pull llama3.1:8b\n"
            "           3. Re-run this script."
        )
        print()
        print(_sep())
        print("  Phase 3 skipped (Ollama unavailable).")
        print(_sep())
        return

    print(f"  Model: {client.model}")
    print()

    # -- Per-document loop ----------------------------------------------------
    # all_rows accumulates every (hyp_id, predicted, gold, match_flag) tuple
    # across all documents, for the pooled summary.
    all_rows:     list[tuple[str, str, str, str]] = []
    # doc_summaries: list of (doc_id, file_name, correct, total) per document
    doc_summaries: list[tuple[int, str, int, int]] = []

    for doc_num, doc_idx in enumerate(TEST_SAMPLE_INDICES, start=1):
        doc    = test_docs[doc_idx]
        doc_id = doc["id"]
        fname  = doc.get("file_name", "unknown")[:55]

        print(_sep("-"))
        print(
            f"  Document [{doc_num}/{len(TEST_SAMPLE_INDICES)}]  "
            f"id={doc_id}  idx={doc_idx}"
        )
        print(f"  File : {fname}")
        print(_sep("-"))

        # Parse clauses
        pages   = [PageBlock(text=doc["text"], page_num=0, bbox=None)]
        clauses = segment_clauses(pages)
        # Namespace clause IDs so ChromaDB keys are unique across documents
        for c in clauses:
            c.id = f"doc{doc_id}_{c.id}"

        if not clauses:
            print("  [WARN] No clauses parsed — skipping this document.")
            print()
            continue

        print(f"  Clauses parsed: {len(clauses)}")

        # Embed
        texts      = [c.text for c in clauses]
        embeddings = embedder.embed(texts)

        # Store in a fresh ChromaDB collection
        coll_name  = f"test_doc_{doc_id}_clauses"
        collection = init_collection(coll_name)
        add_clauses(collection, clauses, embeddings)
        print(f"  Stored {collection.count()} clauses in '{coll_name}'.")
        print()

        # Collect hypothesis IDs for this document
        doc_hyp_ids = sorted(
            doc["annotation_sets"][0]["annotations"].keys()
        ) if doc.get("annotation_sets") else []

        # Hypothesis loop
        doc_rows: list[tuple[str, str, str, str]] = []

        for i, hyp_id in enumerate(doc_hyp_ids, start=1):
            hyp_text = hyp_texts.get(hyp_id, "")
            gold_lbl = gold_label(doc, hyp_id)

            # Retrieve full candidate pool, apply gap filter
            n_clauses  = collection.count()
            candidates = query(collection, hyp_text, k=n_clauses,
                              embedder=embedder, with_scores=True)
            selected   = gap_filter(candidates)

            if not selected:
                predicted  = "NO_CLAUSES"
                match_flag = "MISMATCH"
                doc_rows.append((hyp_id, predicted, gold_lbl, match_flag))
                print(
                    f"  [{i:2d}/{len(doc_hyp_ids)}] {hyp_id:<10s}  "
                    "[NO_CLAUSES retrieved — skipping LLM]"
                )
                continue

            clause_texts = [c.text for c, _ in selected]

            try:
                result    = client.query_llm(
                    clauses=clause_texts,
                    hypothesis=hyp_text,
                    triage_label="",  # Config A: no triage
                )
                predicted = result.label
            except OllamaConnectionError as exc:
                predicted  = "ERROR"
                match_flag = "ERROR"
                doc_rows.append((hyp_id, predicted, gold_lbl, match_flag))
                print(
                    f"  [{i:2d}/{len(doc_hyp_ids)}] {hyp_id:<10s}  "
                    f"[ERROR] {exc}"
                )
                continue
            except Exception as exc:  # last-resort guard: log and skip this hypothesis
                predicted  = "SKIP"
                match_flag = "SKIP"
                doc_rows.append((hyp_id, predicted, gold_lbl, match_flag))
                print(
                    f"  [{i:2d}/{len(doc_hyp_ids)}] {hyp_id:<10s}  "
                    f"[SKIP] {type(exc).__name__}: {exc}"
                )
                continue

            match_flag = "MATCH" if predicted == gold_lbl else "MISMATCH"
            doc_rows.append((hyp_id, predicted, gold_lbl, match_flag))

            print(
                f"  [{i:2d}/{len(doc_hyp_ids)}] {hyp_id:<10s}  "
                f"Predicted: {predicted:<15s}  "
                f"Gold: {gold_lbl:<15s}  "
                f"{match_flag}  [clauses sent: {len(selected)}]"
            )

        # Per-document accuracy banner
        doc_correct = sum(1 for _, _, _, flag in doc_rows if flag == "MATCH")
        doc_total   = len(doc_rows)
        doc_pct     = (doc_correct / doc_total * 100) if doc_total else 0.0
        print()
        print(
            f"  Doc id={doc_id} ({fname}): "
            f"{doc_correct} / {doc_total} correct  ({doc_pct:.1f}%)"
        )
        print()

        doc_summaries.append((doc_id, fname, doc_correct, doc_total))
        all_rows.extend(doc_rows)

    # -- Pooled summary -------------------------------------------------------
    print(_sep())
    print("  PHASE 3 SUMMARY — Multi-Document LLM Accuracy (test.json)")
    print(_sep())

    # Per-document results table
    print(f"  {'Doc ID':<8}  {'Correct':>7}  {'Total':>5}  {'Acc':>7}  File")
    print("  " + "-" * 64)
    for doc_id, fname, correct, total in doc_summaries:
        pct = (correct / total * 100) if total else 0.0
        print(
            f"  {doc_id:<8}  {correct:>7}  {total:>5}  {pct:>6.1f}%  {fname}"
        )

    print()
    total_correct = sum(1 for _, _, _, flag in all_rows if flag == "MATCH")
    total_pairs   = len(all_rows)
    overall_pct   = (total_correct / total_pairs * 100) if total_pairs else 0.0
    print(_sep("-"))
    print(
        f"  Overall: {total_correct} / {total_pairs} correct  "
        f"({overall_pct:.1f}%)"
    )
    print(_sep("-"))

    # -- Error-type breakdown -------------------------------------------------
    mismatches = [
        (pred, gold)
        for _, pred, gold, flag in all_rows
        if flag == "MISMATCH"
    ]
    total_mm = len(mismatches)

    buckets: dict[str, int] = {
        "Missed detection": 0,
        "False positive"  : 0,
        "Label confusion" : 0,
        "Other"           : 0,
    }
    for pred, gold in mismatches:
        buckets[_classify_error(pred, gold)] += 1

    print()
    print(f"  Error breakdown ({total_mm} mismatch{'es' if total_mm != 1 else ''}):")
    for bucket, count in buckets.items():
        if count == 0 and bucket == "Other":
            continue  # suppress empty Other bucket
        pct_mm = (count / total_mm * 100) if total_mm else 0.0
        print(f"    {bucket:<20s}: {count:>3}  ({pct_mm:.1f}%)")

    print()
    print(_sep())
    print("  Phase 3 complete.")
    print(_sep())


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Diagnostic deep-dive — doc id=408
# ─────────────────────────────────────────────────────────────────────────────

def _wrap(text: str, indent: str = "    ", width: int = 72) -> str:
    """Word-wrap text for terminal display, preserving indent on each line."""
    return textwrap.fill(
        text,
        width=width,
        initial_indent=indent,
        subsequent_indent=indent,
    )


def phase4_diag_doc408() -> None:
    """
    Diagnostic re-run of doc id=DIAG_DOC_ID (worst performer in Phase 3).

    For every MISMATCH prints a full evidence block:
      - Full hypothesis text
      - Top 3 retrieved clauses (complete, untruncated)
      - Which clause the LLM received
      - LLM predicted label + full reasoning
      - LLM cited clauses (if any) + gold label

    MATCH hypotheses get a compact one-liner only.
    Ends with a mini accuracy + error-type summary.
    """
    print()
    print(_sep("="))
    print(f"  PHASE 4 — Diagnostic Deep-Dive: doc id={DIAG_DOC_ID}")
    print(_sep("="))
    print(f"  Test JSON : {TEST_JSON}")
    print(f"  Target doc: id={DIAG_DOC_ID} (worst performer in Phase 3)")
    print()

    if not TEST_JSON.exists():
        print(f"  [ERROR] {TEST_JSON} not found — skipping Phase 4.")
        return

    test_docs = load_test_documents()
    doc = next((d for d in test_docs if d["id"] == DIAG_DOC_ID), None)
    if doc is None:
        print(f"  [ERROR] doc id={DIAG_DOC_ID} not found in test.json — skipping Phase 4.")
        return

    fname = doc.get("file_name", "unknown")
    print(f"  File: {fname}")

    hyp_texts = load_hypothesis_texts()

    # -- Embed ----------------------------------------------------------------
    print()
    print("  Loading embedder (BAAI/bge-small-en) ...")
    embedder = Embedder()
    embedder.load()
    print(f"  Loaded: {embedder}")

    pages   = [PageBlock(text=doc["text"], page_num=0, bbox=None)]
    clauses = segment_clauses(pages)
    for c in clauses:
        c.id = f"doc{DIAG_DOC_ID}_{c.id}"

    if not clauses:
        print("  [ERROR] No clauses parsed — skipping Phase 4.")
        return

    print(f"  Clauses parsed: {len(clauses)}")
    texts      = [c.text for c in clauses]
    embeddings = embedder.embed(texts)

    coll_name  = f"diag_doc_{DIAG_DOC_ID}_clauses"
    collection = init_collection(coll_name)
    add_clauses(collection, clauses, embeddings)
    print(f"  Stored {collection.count()} clauses in '{coll_name}'.")

    # -- Ollama reachability --------------------------------------------------
    client = OllamaClient(model="llama3.1:8b")
    if not client.is_reachable():
        print(
            "\n  [SKIP] Ollama is not reachable at http://localhost:11434.\n"
            "         To run Phase 4 fully:\n"
            "           1. Start the server:  ollama serve\n"
            "           2. Pull the model:    ollama pull llama3.1:8b\n"
            "           3. Re-run this script."
        )
        print()
        print(_sep())
        print("  Phase 4 skipped (Ollama unavailable).")
        print(_sep())
        return

    print(f"  Model: {client.model}")

    doc_hyp_ids = sorted(
        doc["annotation_sets"][0]["annotations"].keys()
    ) if doc.get("annotation_sets") else []

    print(f"  Hypotheses to evaluate: {len(doc_hyp_ids)}")
    print()

    # -- Hypothesis loop ------------------------------------------------------
    diag_rows: list[tuple[str, str, str, str]] = []  # (hyp_id, pred, gold, flag)

    for i, hyp_id in enumerate(doc_hyp_ids, start=1):
        hyp_text = hyp_texts.get(hyp_id, "")
        gold_lbl = gold_label(doc, hyp_id)

        # Retrieve full candidate pool, apply adaptive gap filter
        n_clauses  = collection.count()
        candidates = query(collection, hyp_text, k=n_clauses,
                          embedder=embedder, with_scores=True)
        selected   = gap_filter(candidates)

        if not selected:
            predicted  = "NO_CLAUSES"
            match_flag = "MISMATCH"
            diag_rows.append((hyp_id, predicted, gold_lbl, match_flag))
            print(f"  [{i:2d}/17] {hyp_id:<10s}  [NO_CLAUSES retrieved — skipping LLM]")
            continue

        clause_texts = [c.text for c, _ in selected]

        try:
            result    = client.query_llm(
                clauses=clause_texts,
                hypothesis=hyp_text,
                triage_label="",  # Config A: no triage
            )
            predicted = result.label
        except OllamaConnectionError as exc:
            predicted  = "ERROR"
            match_flag = "ERROR"
            diag_rows.append((hyp_id, predicted, gold_lbl, match_flag))
            print(f"  [{i:2d}/17] {hyp_id:<10s}  [ERROR] {exc}")
            continue
        except Exception as exc:  # last-resort guard: log and skip this hypothesis
            predicted  = "SKIP"
            match_flag = "SKIP"
            diag_rows.append((hyp_id, predicted, gold_lbl, match_flag))
            print(f"  [{i:2d}/17] {hyp_id:<10s}  [SKIP] {type(exc).__name__}: {exc}")
            continue

        match_flag = "MATCH" if predicted == gold_lbl else "MISMATCH"
        diag_rows.append((hyp_id, predicted, gold_lbl, match_flag))

        if match_flag == "MATCH":
            # Compact one-liner for correct predictions
            print(
                f"  [{i:2d}/17] {hyp_id:<10s}  MATCH     "
                f"Predicted: {predicted:<15s}  Gold: {gold_lbl}  "
                f"[clauses sent: {len(selected)}]"
            )
        else:
            # Full diagnostic block for every mismatch
            error_type = _classify_error(predicted, gold_lbl)

            print()
            print(_sep("-"))
            print(f"  MISMATCH [{i:2d}/17]: {hyp_id}")
            print(_sep("-"))
            print(f"  Hypothesis : {hyp_text}")
            print(f"  Gold label : {gold_lbl}")
            print(f"  Predicted  : {predicted}")
            print(f"  Error type : {error_type}")
            print(f"  Gap filter : {len(candidates)} candidates -> "
                  f"{len(selected)} sent to LLM  "
                  f"(threshold={GAP_THRESHOLD:.0%})")
            print()

            # -- Gap-filtered clauses (full text + score) ---------------------
            print(f"  Clauses sent to LLM ({len(selected)}):")
            for rank, (clause, score) in enumerate(selected, start=1):
                label = chr(ord('A') + rank - 1)
                clen  = len(clause.text)
                print()
                print(f"    [Clause {label} | Rank {rank} | dist={score:.4f}] "
                      f"id={clause.id}  ({clen} chars)")
                for line in clause.text.splitlines():
                    stripped = line.strip()
                    if stripped:
                        print(_wrap(stripped, indent="      "))
                    else:
                        print()

            # -- Dropped candidates (for context) ----------------------------
            dropped = candidates[len(selected):]
            if dropped:
                print()
                print(f"  Dropped by gap filter ({len(dropped)} clause(s)):")
                for rank, (clause, score) in enumerate(
                        dropped, start=len(selected) + 1):
                    print(f"    [Rank {rank} | dist={score:.4f}] "
                          f"id={clause.id}  "
                          f"({len(clause.text)} chars)  "
                          f"{_preview(clause.text, 60)}")

            # -- LLM reasoning (full, word-wrapped) ---------------------------
            print()
            print("  LLM reasoning:")
            if result.reasoning:
                for para in result.reasoning.splitlines():
                    stripped = para.strip()
                    if stripped:
                        print(_wrap(stripped, indent="    "))
                    else:
                        print()
            else:
                print("    [no reasoning returned]")

            # -- LLM cited clauses --------------------------------------------
            print()
            print("  LLM cited clauses:")
            if result.cited_clauses:
                for ci, cited in enumerate(result.cited_clauses, start=1):
                    print(f"    [{ci}] {cited}")
            else:
                print("    [none returned by LLM]")

            print(_sep("-"))
            print()

    # -- Mini summary ---------------------------------------------------------
    correct = sum(1 for _, _, _, flag in diag_rows if flag == "MATCH")
    total   = len(diag_rows)
    pct     = (correct / total * 100) if total else 0.0

    print()
    print(_sep())
    print(f"  PHASE 4 SUMMARY — doc id={DIAG_DOC_ID}")
    print(_sep())
    print(f"  Accuracy: {correct} / {total} correct  ({pct:.1f}%)")
    print()

    mismatches = [
        (pred, gold)
        for _, pred, gold, flag in diag_rows
        if flag == "MISMATCH"
    ]
    total_mm = len(mismatches)
    buckets: dict[str, int] = {
        "Missed detection": 0,
        "False positive"  : 0,
        "Label confusion" : 0,
        "Other"           : 0,
    }
    for pred, gold in mismatches:
        buckets[_classify_error(pred, gold)] += 1

    print(f"  Error breakdown ({total_mm} mismatch{'es' if total_mm != 1 else ''}):")
    for bucket, count in buckets.items():
        if count == 0 and bucket == "Other":
            continue
        pct_mm = (count / total_mm * 100) if total_mm else 0.0
        print(f"    {bucket:<20s}: {count:>3}  ({pct_mm:.1f}%)")

    print()
    print(_sep())
    print("  Phase 4 complete.")
    print(_sep())


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    print(_sep("="))
    print("  EdgeLegal — No-Triage Pipeline Test (Config A)")
    print(_sep("="))
    print(f"  Train JSON : {TRAIN_JSON}")
    print(f"  Test JSON  : {TEST_JSON}")
    print(f"  Sampling   : train indices {SAMPLE_INDICES}")
    print(f"               test  indices {TEST_SAMPLE_INDICES}")
    print()

    if not TRAIN_JSON.exists():
        print(f"  [ERROR] {TRAIN_JSON} not found.")
        print("  Run: python backend/app/data_setup.py first.")
        sys.exit(1)

    docs = load_train_documents()
    print(f"  Loaded {len(docs)} documents from train.json")

    max_idx = max(SAMPLE_INDICES)
    if max_idx >= len(docs):
        print(
            f"  [ERROR] Requested index {max_idx} but only {len(docs)} docs available."
        )
        sys.exit(1)

    phase1_results = phase1_clause_audit(docs)
    phase2_e2e_all_hypotheses(docs, phase1_results)
    phase3_multi_doc_eval()
    # phase4_diag_doc408()   # Phase 4 diagnostic skipped — use for targeted re-runs


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_exception(logger, "test_pipeline.py crashed - see traceback above/below "
                      "and in logs/edgelegal.log for the full pipeline sequence "
                      "leading up to it")
        raise
