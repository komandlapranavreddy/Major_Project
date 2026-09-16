"""
backend/app/data_setup.py
Downloads the ContractNLI dataset (Stanford NLP / Hitachi America Ltd.,
CC-BY 4.0) and writes the three split JSON files to backend/data/contractnli/.

Published split sizes (EMNLP 2021 paper / official dataset page):
  train : 423 contracts
  dev   : 61  contracts
  test  : 123 contracts
  total : 607 contracts
  hypotheses (fixed across all splits) : 17

Usage:
    python backend/app/data_setup.py

No third-party dependencies required beyond the Python standard library.
"""

from __future__ import annotations

import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# ──────────────────────────────────────────────────────────────────────────────
# Paths & constants
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent      # backend/app/
REPO_ROOT   = SCRIPT_DIR.parent.parent             # edgelegal/
DATA_DIR    = REPO_ROOT / "backend" / "data" / "contractnli"

DATASET_URL = "https://stanfordnlp.github.io/contract-nli/resources/contract-nli.zip"

# Published ground-truth split sizes (ContractNLI paper, Table 1)
EXPECTED: dict[str, int] = {
    "train": 423,
    "dev":   61,
    "test":  123,
}
EXPECTED_TOTAL       = 607
EXPECTED_HYPOTHESES  = 17

CHECKMARK = "PASS"
CROSS     = "FAIL"

_failures: list[str] = []


# ──────────────────────────────────────────────────────────────────────────────
# Download & extract
# ──────────────────────────────────────────────────────────────────────────────

def download_and_extract() -> None:
    """
    Download contract-nli.zip from the Stanford NLP GitHub Pages host and
    extract train.json, dev.json, test.json into DATA_DIR.
    Skips the download if all three files are already present.
    """
    files_needed = [DATA_DIR / f"{split}.json" for split in EXPECTED]
    if all(f.exists() for f in files_needed):
        print("[ContractNLI] All split files already present — skipping download.")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[ContractNLI] Downloading dataset from:")
    print(f"              {DATASET_URL}")

    req = urllib.request.Request(
        DATASET_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; edgelegal-data-setup/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()

    print(f"[ContractNLI] Downloaded {len(raw) / 1_048_576:.1f} MB — extracting ...")

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
        # The zip may nest files under a subdirectory; locate each split file.
        for split in EXPECTED:
            filename = f"{split}.json"
            # Find the member whose basename matches (handles sub-dirs)
            match = next(
                (n for n in names if n.endswith(f"/{filename}") or n == filename),
                None,
            )
            if match is None:
                print(f"[WARN] '{filename}' not found inside zip. Contents: {names}")
                continue
            data = zf.read(match)
            out_path = DATA_DIR / filename
            out_path.write_bytes(data)
            print(f"[ContractNLI] Extracted {filename}")

    print()


# ──────────────────────────────────────────────────────────────────────────────
# Load splits
# ──────────────────────────────────────────────────────────────────────────────

def load_splits() -> dict[str, list]:
    """
    Load each split JSON and return a dict of {split_name: list_of_documents}.
    Handles both formats:
      • {"documents": [...]}  — Stanford baseline format
      • [...]                 — bare list
    """
    splits: dict[str, list] = {}
    for split in EXPECTED:
        path = DATA_DIR / f"{split}.json"
        if not path.exists():
            print(f"[ERROR] Expected file not found: {path}", file=sys.stderr)
            _failures.append(f"missing file: {path.name}")
            splits[split] = []
            continue
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict) and "documents" in raw:
            splits[split] = raw["documents"]
        elif isinstance(raw, list):
            splits[split] = raw
        else:
            print(f"[WARN] Unexpected JSON structure in {path.name}")
            splits[split] = []
    return splits


# ──────────────────────────────────────────────────────────────────────────────
# Verify split sizes
# ──────────────────────────────────────────────────────────────────────────────

def verify_splits(splits: dict[str, list]) -> None:
    print("Split sizes")
    print(f"  {'split':<8} {'actual':>8}  {'expected':>10}  check")
    print("  " + "-" * 42)

    for split, expected_count in EXPECTED.items():
        actual = len(splits.get(split, []))
        ok = actual == expected_count
        symbol = CHECKMARK if ok else CROSS
        print(f"  {split:<8} {actual:>8}  {expected_count:>10}  {symbol}")
        if not ok:
            _failures.append(f"{split}: expected {expected_count}, got {actual}")

    total = sum(len(splits.get(s, [])) for s in EXPECTED)
    ok_total = total == EXPECTED_TOTAL
    symbol = CHECKMARK if ok_total else CROSS
    print(f"  {'total':<8} {total:>8}  {EXPECTED_TOTAL:>10}  {symbol}")
    if not ok_total:
        _failures.append(f"total: expected {EXPECTED_TOTAL}, got {total}")


# ──────────────────────────────────────────────────────────────────────────────
# Verify hypothesis count
# ──────────────────────────────────────────────────────────────────────────────

def verify_hypotheses(splits: dict[str, list]) -> None:
    """
    Count unique hypothesis strings in the training split.
    Each document's annotation_sets[*].annotations is a dict keyed by hypothesis.
    """
    print("\nHypothesis count  (from train split)")
    hypotheses: set[str] = set()

    for doc in splits.get("train", []):
        ann_sets = doc.get("annotation_sets", [])
        for ann_set in ann_sets:
            annotations = ann_set.get("annotations", {})
            if isinstance(annotations, dict):
                hypotheses.update(annotations.keys())

    count = len(hypotheses)
    ok = count == EXPECTED_HYPOTHESES
    symbol = CHECKMARK if ok else CROSS
    print(f"  unique hypotheses : {count:>4}  (expected {EXPECTED_HYPOTHESES})  {symbol}")
    if not ok:
        _failures.append(
            f"hypotheses: expected {EXPECTED_HYPOTHESES}, got {count}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  ContractNLI — Data Setup & Verification")
    print("=" * 60)
    print(f"  Output directory : {DATA_DIR}")
    print(f"  Source           : {DATASET_URL}\n")

    download_and_extract()
    splits = load_splits()

    verify_splits(splits)
    verify_hypotheses(splits)

    print()
    if _failures:
        print("FAILED — the following checks did not pass:")
        for f in _failures:
            print(f"  {CROSS}  {f}")
        sys.exit(1)
    else:
        print("All assertions PASSED.")
        print("=" * 60)


if __name__ == "__main__":
    main()
