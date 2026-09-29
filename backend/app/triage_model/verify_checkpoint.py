"""
verify_checkpoint.py — one-off script to confirm the reconstructed
dataset.py/evaluate.py reproduce Pranav's reported numbers on this
checkpoint. Run from the EdgeLegal_CodeBase root:

    (venv) > python -m backend.app.triage_model.verify_checkpoint

Expected (from kaggle_train.ipynb output, dev split):
    Accuracy      : 0.9701
    Macro P/R/F1  : 0.9305 / 0.9486 / 0.9391
    ECE (10 bins) : 0.0285
    Frozen tau    : 0.95

v2 (2026-09-27): runs model inference ONCE and reuses it for metrics,
calibration, and the threshold sweep — the first version ran 3 separate
full passes (mirroring kaggle_train.ipynb's own cell structure, fine on a
GPU, ~3x slower than necessary on CPU). Also updated to match dataset.py's
new full-document fallback for no-evidence (NotMentioned) premises.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from transformers import AutoTokenizer

from backend.app.triage_model.model import TriageModel, HF_CHECKPOINT
from backend.app.triage_model.dataset import ContractNLIDataset
from backend.app.triage_model.evaluate import (
    Metrics,
    ClassMetrics,
    compute_calibration,
    select_threshold,
    DEFAULT_THRESHOLD_CANDIDATES,
    _collect_predictions,
)

DEV_JSON = Path("backend/data/contractnli/dev.json")
CHECKPOINT = Path("backend/app/triage_model/checkpoints/current/best_model.pt")
LABELS_ORDER = ["Contradiction", "Entailment", "NotMentioned"]

# Small JSON artifact, not under checkpoints/ (gitignored for the multi-GB
# .pt files) — this is a few KB of real dev-set numbers meant to be checked
# into git and read by GET /research/metrics for the paper's reliability
# diagram and threshold sweep chart.
RESULTS_JSON = Path("backend/app/triage_model/dev_eval_results.json")


def metrics_from_predictions(true_labels, pred_labels) -> Metrics:
    acc = accuracy_score(true_labels, pred_labels)
    precisions, recalls, f1s, supports = precision_recall_fscore_support(
        true_labels, pred_labels, labels=LABELS_ORDER, zero_division=0
    )
    per_class = [
        ClassMetrics(label=lbl, precision=p, recall=r, f1=f, support=int(s))
        for lbl, p, r, f, s in zip(LABELS_ORDER, precisions, recalls, f1s, supports)
    ]
    return Metrics(
        accuracy=acc,
        macro_precision=sum(precisions) / len(LABELS_ORDER),
        macro_recall=sum(recalls) / len(LABELS_ORDER),
        macro_f1=sum(f1s) / len(LABELS_ORDER),
        per_class=per_class,
    )


def sweep_from_predictions(true_labels, pred_labels, confidences, candidates):
    n_total = len(true_labels)
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
            kept_true, kept_pred, labels=LABELS_ORDER, zero_division=0
        )
        macro_f1 = sum(f1s) / len(LABELS_ORDER)
        sweep.append({"tau": tau, "coverage": coverage, "macro_f1": macro_f1, "accuracy": acc, "n_above": n_above})
    best = max(sweep, key=lambda r: (r["macro_f1"], r["coverage"]))
    return best["tau"], sweep


def save_results_json(path, metrics, ece, sweep, frozen_tau, n_dev, device):
    """
    Persist real dev-set numbers as JSON for GET /research/metrics — the
    reliability diagram and threshold sweep chart on the frontend's
    /research page read this file directly. No fabricated numbers: every
    value here comes straight out of this run's actual inference pass.
    """
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "device": str(device),
        "dataset": {"split": "dev", "n_examples": n_dev, "path": str(DEV_JSON)},
        "checkpoint": str(CHECKPOINT),
        "metrics": {
            "accuracy": metrics.accuracy,
            "macro_precision": metrics.macro_precision,
            "macro_recall": metrics.macro_recall,
            "macro_f1": metrics.macro_f1,
            "per_class": [
                {"label": c.label, "precision": c.precision, "recall": c.recall, "f1": c.f1, "support": c.support}
                for c in metrics.per_class
            ],
        },
        "calibration": {
            "ece": ece.ece,
            "n_bins": len(ece.bin_counts),
            "bin_confidences": ece.bin_confidences,
            "bin_accuracies": ece.bin_accuracies,
            "bin_counts": ece.bin_counts,
        },
        "threshold_sweep": sweep,
        "frozen_threshold": 0.95,
        "selected_threshold_by_macro_f1": frozen_tau,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\nSaved results JSON -> {path}")


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Device:", device)

    tok = AutoTokenizer.from_pretrained(HF_CHECKPOINT)
    dev_ds = ContractNLIDataset(str(DEV_JSON), tok, max_length=512)
    dev_loader = DataLoader(dev_ds, batch_size=32, shuffle=False, num_workers=0)
    print(f"Dev examples: {len(dev_ds)}")

    model = TriageModel()
    model.load(checkpoint_path=CHECKPOINT, device=device)

    print("Running inference once over the dev set...")
    true_labels, pred_labels, confidences = _collect_predictions(model, dev_loader, device)

    metrics = metrics_from_predictions(true_labels, pred_labels)
    print()
    print(metrics)

    correct = [t == p for t, p in zip(true_labels, pred_labels)]
    ece = compute_calibration(confidences, correct)
    print()
    print(ece)

    frozen_tau, sweep = sweep_from_predictions(
        true_labels, pred_labels, confidences, DEFAULT_THRESHOLD_CANDIDATES
    )
    print()
    print("Threshold sweep:")
    for row in sweep:
        print(f"  tau={row['tau']:.2f}  coverage={row['coverage']:.3f}  "
              f"macro_f1={row['macro_f1']:.4f}  accuracy={row['accuracy']:.4f}  "
              f"n_above={row['n_above']}")
    print()
    print("Frozen threshold:", frozen_tau)

    save_results_json(RESULTS_JSON, metrics, ece, sweep, frozen_tau, len(dev_ds), device)


if __name__ == "__main__":
    main()
