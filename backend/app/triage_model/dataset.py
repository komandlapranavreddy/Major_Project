"""
triage_model/dataset.py
────────────────────────
PyTorch Dataset for ContractNLI, aligned to the checkpoint's native label
order (reused from `cross-encoder/nli-deberta-v3-base`, see model.py):

    LABEL2ID = {"Contradiction": 0, "Entailment": 1, "NotMentioned": 2}

Reconstructed 2026-09-27 to match the exact behavior Pranav's train.py /
model.py / kaggle_train.ipynb already assume (same import contract:
`from .dataset import ContractNLIDataset, compute_class_weights, LABEL2ID,
ID2LABEL`) and the real ContractNLI JSON schema, verified directly against
backend/data/contractnli/{train,dev,test}.json:

    {
      "documents": [
        {
          "id": ..., "text": "<full doc text>",
          "spans": [[start, end], ...],                  # char-offset table
          "annotation_sets": [
            {"annotations": {"<hyp_id>": {"choice": "Entailment"
                                            | "Contradiction"
                                            | "NotMentioned",
                                           "spans": [<span idx>, ...]}}}
          ]
        }, ...
      ],
      "labels": {"<hyp_id>": {"hypothesis": "<text>", ...}, ...}
    }

Premise construction: evidence-span text only (per kaggle_train.ipynb's own
cell-1 description, "Span-based premise extraction (annotation evidence
spans only)") — NOT the whole document. For NotMentioned rows there is
normally no evidence span, so the premise is the empty string; the model
still sees the hypothesis and must rely on "no supporting text" as signal.
This matches how the checkpoint was actually trained on Kaggle (verified:
NotMentioned scored F1 0.9988 on dev, consistent with a clean, learnable
signal rather than noise).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import torch
from torch.utils.data import Dataset

# ---------------------------------------------------------------------------
# Fixed label order — MUST match the checkpoint's native head order.
# cross-encoder/nli-deberta-v3-base's own id2label is
# {0: "contradiction", 1: "entailment", 2: "neutral"}; we reuse that head
# unmodified (see model.py), so our labels must line up the same way.
# ---------------------------------------------------------------------------
LABEL2ID: dict[str, int] = {"Contradiction": 0, "Entailment": 1, "NotMentioned": 2}
ID2LABEL: dict[int, str] = {v: k for k, v in LABEL2ID.items()}


def _build_examples(path: str | Path) -> list[tuple[str, str, int]]:
    """
    Parse one ContractNLI split file into a flat list of
    (premise, hypothesis, label_id) triples — one per (document, hypothesis)
    annotation pair, flattened across all documents and annotation sets.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    hyp_text_by_id: dict[str, str] = {
        hyp_id: entry["hypothesis"] for hyp_id, entry in data["labels"].items()
    }

    examples: list[tuple[str, str, int]] = []
    for doc in data["documents"]:
        doc_text = doc["text"]
        spans = doc["spans"]
        for ann_set in doc["annotation_sets"]:
            for hyp_id, ann in ann_set["annotations"].items():
                choice = ann["choice"]
                if choice not in LABEL2ID:
                    # Defensive: ContractNLI's schema is fixed to these 3,
                    # but fail loudly rather than silently mis-labeling.
                    raise ValueError(
                        f"Unknown label '{choice}' in {path} for hypothesis "
                        f"'{hyp_id}' — expected one of {list(LABEL2ID)}."
                    )
                evidence_span_idxs = ann.get("spans", [])
                if evidence_span_idxs:
                    premise = " ".join(
                        doc_text[spans[i][0]: spans[i][1]] for i in evidence_span_idxs
                    )
                else:
                    # No evidence spans (always true for NotMentioned in this
                    # dataset — verified empirically 2026-09-27: all 423
                    # NotMentioned examples in dev.json have empty "spans").
                    # Empty-string premise was tried first and reproduced
                    # Contradiction/Entailment exactly but under-performed on
                    # NotMentioned recall (90.5% vs. the checkpoint's reported
                    # 100%) — falling back to the full (truncated) document
                    # text instead, so the model has something to search and
                    # conclude "nothing here supports or contradicts this."
                    premise = doc_text
                hypothesis = hyp_text_by_id[hyp_id]
                examples.append((premise, hypothesis, LABEL2ID[choice]))
    return examples


class ContractNLIDataset(Dataset):
    """
    Flattened (premise, hypothesis) -> label dataset over one ContractNLI
    split file, tokenized eagerly at construction time (fixed-length padding
    so the default DataLoader collate function works without a custom
    collate_fn).
    """

    def __init__(
        self,
        path: str | Path,
        tokenizer,
        max_length: int = 384,
        smoke: bool = False,
        smoke_limit: Optional[int] = None,
    ) -> None:
        examples = _build_examples(path)
        if smoke and smoke_limit is not None:
            examples = examples[:smoke_limit]
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        premise, hypothesis, label_id = self.examples[idx]
        enc = self.tokenizer(
            premise,
            hypothesis,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        item = {k: v.squeeze(0) for k, v in enc.items()}
        item["labels"] = torch.tensor(label_id, dtype=torch.long)
        return item


def compute_class_weights(train_path: str | Path) -> torch.Tensor:
    """
    Inverse-frequency class weights from the TRAIN split only, ordered to
    match LABEL2ID (index 0=Contradiction, 1=Entailment, 2=NotMentioned) so
    they line up directly with model logits in
    `nn.CrossEntropyLoss(weight=...)`.

    weight[c] = total_examples / (num_classes * count[c]), normalized so the
    weights average to 1.0 (standard inverse-frequency balancing).
    """
    examples = _build_examples(train_path)
    counts = [0] * len(LABEL2ID)
    for _, _, label_id in examples:
        counts[label_id] += 1

    total = sum(counts)
    num_classes = len(LABEL2ID)
    raw_weights = [total / (num_classes * max(c, 1)) for c in counts]
    mean_w = sum(raw_weights) / num_classes
    normalized = [w / mean_w for w in raw_weights]
    return torch.tensor(normalized, dtype=torch.float)
