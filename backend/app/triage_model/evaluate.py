"""
triage_model/evaluate.py
──────────────────────────
Evaluation and calibration utilities for the triage classifier.

Reconstructed 2026-09-27 to match the actual call signatures used in
kaggle_train.ipynb (model + dataloader + device, not the
predicted/gold-label-list signature architecture123.md originally sketched)
since that notebook is what actually produced the checkpoint's reported
numbers (accuracy 0.9701, macro-F1 0.9391, ECE 0.0285, frozen tau=0.95) —
matching its behavior exactly is required to trust those numbers apply to
this implementation.

Public API:
  evaluate(model, dataloader, device) -> Metrics
  compute_calibration(confidences, correct, n_bins=10) -> ECEResult
  select_threshold(model, dataloader, device, candidates=...) -> (float, list[dict])
  _collect_predictions(model, dataloader, device) -> (true_labels, pred_labels, confidences)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import torch
from sklearn.metrics import precision_recall_fscore_support, accuracy_score

from .dataset import ID2LABEL

# Validation-only sweep range per Project Guide / architecture123.md
# (0.60-0.95, step 0.05) — matches what kaggle_train.ipynb actually swept.
DEFAULT_THRESHOLD_CANDIDATES: tuple[float, ...] = tuple(
    round(0.60 + 0.05 * i, 2) for i in range(8)
)


@dataclass
class ClassMetrics:
    label: str
    precision: float
    recall: float
    f1: float
    support: int


@dataclass
class Metrics:
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    per_class: list = field(default_factory=list)  # list[ClassMetrics]

    def __repr__(self) -> str:
        lines = [
            f"Accuracy      : {self.accuracy:.4f}",
            f"Macro P/R/F1  : {self.macro_precision:.4f} / {self.macro_recall:.4f} / {self.macro_f1:.4f}",
            "",
            f"{'Label':<20}{'Precision':>12}{'Recall':>11}{'F1':>11}{'Support':>11}",
            "-" * 64,
        ]
        for cm in self.per_class:
            lines.append(
                f"{cm.label:<20}{cm.precision:>12.4f}{cm.recall:>11.4f}"
                f"{cm.f1:>11.4f}{cm.support:>11}"
            )
        return "\n".join(lines)


@dataclass
class ECEResult:
    ece: float
    bin_confidences: list
    bin_accuracies: list
    bin_counts: list

    def __repr__(self) -> str:
        lines = [f"ECE ({len(self.bin_counts)} bins): {self.ece:.4f}"]
        for i, (conf, acc, n) in enumerate(
            zip(self.bin_confidences, self.bin_accuracies, self.bin_counts), start=1
        ):
            if n == 0:
                continue
            lines.append(f"  bin {i:>2}: conf={conf:.3f}  acc={acc:.3f}  n={n}")
        return "\n".join(lines)


def _collect_predictions(model, dataloader, device):
    """
    Run `model` over every batch in `dataloader`.

    Returns:
        true_labels: list[str]
        pred_labels: list[str]
        confidences: list[float] — max softmax probability per prediction
    """
    true_labels: list[str] = []
    pred_labels: list[str] = []
    confidences: list[float] = []

    was_training = getattr(model, "_model", None) is not None and model._model.training
    model.eval_mode()

    with torch.no_grad():
        for batch in dataloader:
            batch = dict(batch)
            labels = batch.pop("labels")
            batch = {k: v.to(device) for k, v in batch.items()}

            outputs = model(**batch)
            logits = outputs.logits  # (B, 3)
            probs = torch.softmax(logits, dim=-1)
            conf, pred_idx = probs.max(dim=-1)

            true_labels.extend(ID2LABEL[i] for i in labels.tolist())
            pred_labels.extend(ID2LABEL[i] for i in pred_idx.cpu().tolist())
            confidences.extend(conf.cpu().tolist())

    if was_training:
        model.train_mode()

    return true_labels, pred_labels, confidences


def evaluate(model, dataloader, device) -> Metrics:
    """Accuracy, per-class precision/recall/F1, and macro P/R/F1."""
    true_labels, pred_labels, _ = _collect_predictions(model, dataloader, device)
    labels_order = ["Contradiction", "Entailment", "NotMentioned"]

    acc = accuracy_score(true_labels, pred_labels)
    precisions, recalls, f1s, supports = precision_recall_fscore_support(
        true_labels, pred_labels, labels=labels_order, zero_division=0
    )
    macro_p = sum(precisions) / len(labels_order)
    macro_r = sum(recalls) / len(labels_order)
    macro_f1 = sum(f1s) / len(labels_order)

    per_class = [
        ClassMetrics(label=lbl, precision=p, recall=r, f1=f, support=int(s))
        for lbl, p, r, f, s in zip(labels_order, precisions, recalls, f1s, supports)
    ]
    return Metrics(
        accuracy=acc,
        macro_precision=macro_p,
        macro_recall=macro_r,
        macro_f1=macro_f1,
        per_class=per_class,
    )


def compute_calibration(
    confidences: Sequence[float], correct: Sequence[bool], n_bins: int = 10
) -> ECEResult:
    """
    Expected Calibration Error with `n_bins` equal-width bins over [0, 1].

    ECE = sum_b (n_b / N) * |acc_b - conf_b|
    """
    n_bins = max(n_bins, 1)
    bin_conf_sums = [0.0] * n_bins
    bin_correct_sums = [0.0] * n_bins
    bin_counts = [0] * n_bins

    for conf, is_correct in zip(confidences, correct):
        b = min(int(conf * n_bins), n_bins - 1)
        bin_conf_sums[b] += conf
        bin_correct_sums[b] += float(is_correct)
        bin_counts[b] += 1

    bin_confidences = [
        (bin_conf_sums[b] / bin_counts[b]) if bin_counts[b] else 0.0
        for b in range(n_bins)
    ]
    bin_accuracies = [
        (bin_correct_sums[b] / bin_counts[b]) if bin_counts[b] else 0.0
        for b in range(n_bins)
    ]

    total = sum(bin_counts)
    ece = 0.0
    if total > 0:
        for b in range(n_bins):
            if bin_counts[b] == 0:
                continue
            ece += (bin_counts[b] / total) * abs(bin_accuracies[b] - bin_confidences[b])

    return ECEResult(
        ece=ece,
        bin_confidences=bin_confidences,
        bin_accuracies=bin_accuracies,
        bin_counts=bin_counts,
    )


def select_threshold(
    model,
    dataloader,
    device,
    candidates: Sequence[float] = DEFAULT_THRESHOLD_CANDIDATES,
):
    """
    Sweep candidate confidence thresholds on validation only. For each tau,
    keep only predictions with confidence >= tau and compute coverage,
    macro-F1, and accuracy among the kept subset. Freezes the tau with the
    highest macro-F1 (ties broken by higher coverage).

    Returns:
        (frozen_tau, sweep) where sweep is a list of dicts:
        {tau, coverage, macro_f1, accuracy, n_above}
    """
    true_labels, pred_labels, confidences = _collect_predictions(model, dataloader, device)
    n_total = len(true_labels)
    labels_order = ["Contradiction", "Entailment", "NotMentioned"]

    sweep = []
    for tau in candidates:
        kept_true = [t for t, c in zip(true_labels, confidences) if c >= tau]
        kept_pred = [p for p, c in zip(pred_labels, confidences) if c >= tau]
        n_above = len(kept_true)
        coverage = n_above / n_total if n_total else 0.0

        if n_above == 0:
            sweep.append({"tau": tau, "coverage": 0.0, "macro_f1": 0.0, "accuracy": 0.0, "n_above": 0})
            continue

        acc = accuracy_score(kept_true, kept_pred)
        _, _, f1s, _ = precision_recall_fscore_support(
            kept_true, kept_pred, labels=labels_order, zero_division=0
        )
        macro_f1 = sum(f1s) / len(labels_order)

        sweep.append(
            {"tau": tau, "coverage": coverage, "macro_f1": macro_f1, "accuracy": acc, "n_above": n_above}
        )

    best = max(sweep, key=lambda r: (r["macro_f1"], r["coverage"]))
    return best["tau"], sweep
