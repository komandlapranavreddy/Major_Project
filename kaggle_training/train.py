"""
train.py — Training loop for the ContractNLI triage classifier.

Quick local smoke test (CPU, ~2-3 min):
  python -m triage_model.train --smoke

Full training (GPU recommended):
  python -m triage_model.train \\
      --train_path data/contractnli/train.json \\
      --dev_path   data/contractnli/dev.json   \\
      --output_dir checkpoints/

CLI hyperparams (all overridable):
  --batch_size 32 --lr 2e-5 --epochs 3 --warmup_ratio 0.06
  --weight_decay 0.01 --max_length 512 --early_stopping_patience 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, get_linear_schedule_with_warmup
from sklearn.metrics import f1_score

# ---------------------------------------------------------------------------
# Import siblings — handle both `python -m triage_model.train` and direct run
# ---------------------------------------------------------------------------
try:
    from .dataset import ContractNLIDataset, compute_class_weights, LABEL2ID, ID2LABEL
    from .model import TriageModel, HF_CHECKPOINT, _best_device
except ImportError:
    from dataset import ContractNLIDataset, compute_class_weights, LABEL2ID, ID2LABEL
    from model import TriageModel, HF_CHECKPOINT, _best_device


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------

@dataclass
class TrainConfig:
    train_path: str = "data/contractnli/train.json"
    dev_path: str = "data/contractnli/dev.json"
    output_dir: str = "checkpoints"
    hf_checkpoint: str = HF_CHECKPOINT
    batch_size: int = 8
    gradient_accumulation_steps: int = 4  # effective batch = batch_size * grad_accum
    lr: float = 2e-5
    epochs: int = 3
    warmup_ratio: float = 0.06
    weight_decay: float = 0.01
    max_length: int = 384
    early_stopping_patience: int = 2
    smoke: bool = False
    # smoke-mode overrides
    smoke_train_limit: int = 32
    smoke_dev_limit: int = 16


# ---------------------------------------------------------------------------
# One training epoch
# ---------------------------------------------------------------------------

def train_epoch(
    model: TriageModel,
    dataloader: DataLoader,
    optimizer: AdamW,
    scheduler,
    loss_fn: nn.CrossEntropyLoss,
    device: torch.device,
    grad_accum_steps: int = 1,
) -> float:
    """
    Run one full pass over the training dataloader.

    Supports gradient accumulation: gradients are accumulated over
    `grad_accum_steps` micro-batches before an optimizer step, giving an
    effective batch size of batch_size * grad_accum_steps.

    Returns the average cross-entropy loss for this epoch.
    """
    model.train_mode()
    total_loss = 0.0
    n_batches = 0
    optimizer.zero_grad()

    for step, batch in enumerate(dataloader):
        labels = batch.pop("labels").to(device)
        batch = {k: v.to(device) for k, v in batch.items()}

        outputs = model(**batch)
        logits = outputs.logits  # (B, 3)

        # Scale loss so accumulated gradients equal a single full-batch gradient
        loss = loss_fn(logits, labels) / grad_accum_steps
        loss.backward()

        total_loss += loss.item() * grad_accum_steps  # log unscaled loss
        n_batches += 1

        # Optimizer step every `grad_accum_steps` micro-batches (or at end)
        if (step + 1) % grad_accum_steps == 0 or (step + 1) == len(dataloader):
            # Gradient clip — helps with DeBERTa instability at early epochs
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()

    return total_loss / max(n_batches, 1)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def evaluate_epoch(
    model: TriageModel,
    dataloader: DataLoader,
    loss_fn: nn.CrossEntropyLoss,
    device: torch.device,
) -> tuple[float, float]:
    """
    Run validation.

    Returns (avg_loss, macro_f1).
    """
    model.eval_mode()
    total_loss = 0.0
    all_preds: list[int] = []
    all_labels: list[int] = []
    n_batches = 0

    with torch.no_grad():
        for batch in dataloader:
            labels = batch.pop("labels").to(device)
            batch = {k: v.to(device) for k, v in batch.items()}

            outputs = model(**batch)
            logits = outputs.logits  # (B, 3)

            loss = loss_fn(logits, labels)
            total_loss += loss.item()
            n_batches += 1

            preds = logits.argmax(dim=-1)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())

    macro_f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    return total_loss / max(n_batches, 1), macro_f1


# ---------------------------------------------------------------------------
# Early stopping
# ---------------------------------------------------------------------------

class EarlyStopping:
    """Stops training when macro-F1 stops improving for `patience` epochs."""

    def __init__(self, patience: int, output_dir: Path) -> None:
        self.patience = patience
        self.best_f1 = -1.0
        self.epochs_without_improvement = 0
        self.best_checkpoint_path = output_dir / "best_model.pt"
        output_dir.mkdir(parents=True, exist_ok=True)

    def step(self, macro_f1: float, model: TriageModel) -> bool:
        """
        Update state. Saves checkpoint if F1 improved.

        Returns True if training should STOP.
        """
        if macro_f1 > self.best_f1:
            self.best_f1 = macro_f1
            self.epochs_without_improvement = 0
            torch.save(model.state_dict(), self.best_checkpoint_path)
            print(f"  ✓ New best macro-F1={macro_f1:.4f} — checkpoint saved.")
            return False
        else:
            self.epochs_without_improvement += 1
            print(
                f"  ✗ No improvement (best={self.best_f1:.4f}, "
                f"patience={self.epochs_without_improvement}/{self.patience})."
            )
            return self.epochs_without_improvement >= self.patience


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(config: TrainConfig) -> None:
    t0 = time.time()
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cpu") if config.smoke else _best_device()
    print(f"Device: {device}")
    print(f"Smoke mode: {config.smoke}")

    # ---- Tokenizer --------------------------------------------------------
    print(f"Loading tokenizer from {config.hf_checkpoint} …")
    tokenizer = AutoTokenizer.from_pretrained(config.hf_checkpoint)

    # ---- Datasets ---------------------------------------------------------
    print("Building datasets …")
    train_ds = ContractNLIDataset(
        config.train_path,
        tokenizer,
        max_length=config.max_length,
        smoke=config.smoke,
        smoke_limit=config.smoke_train_limit,
    )
    dev_ds = ContractNLIDataset(
        config.dev_path,
        tokenizer,
        max_length=config.max_length,
        smoke=config.smoke,
        smoke_limit=config.smoke_dev_limit,
    )
    print(f"  Train: {len(train_ds)} examples  |  Dev: {len(dev_ds)} examples")

    # ---- DataLoaders ------------------------------------------------------
    # num_workers=0 on Windows (multiprocessing + tokenizer = deadlock)
    nw = 0 if sys.platform == "win32" or config.smoke else 2
    train_loader = DataLoader(
        train_ds, batch_size=config.batch_size, shuffle=True, num_workers=nw
    )
    dev_loader = DataLoader(
        dev_ds, batch_size=config.batch_size, shuffle=False, num_workers=nw
    )

    # ---- Class weights (from TRAIN split only) ----------------------------
    class_weights = compute_class_weights(config.train_path).to(device)
    print(f"Class weights: {dict(zip(LABEL2ID.keys(), class_weights.tolist()))}")

    # ---- Model ------------------------------------------------------------
    print(f"Loading model from {config.hf_checkpoint} …")
    model = TriageModel(hf_checkpoint=config.hf_checkpoint)
    model.device = device
    model.load(checkpoint_path=None, device=device)

    # ---- Loss & optimiser -------------------------------------------------
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = AdamW(
        model.parameters(),
        lr=config.lr,
        weight_decay=config.weight_decay,
    )

    num_epochs = 1 if config.smoke else config.epochs
    grad_accum = max(1, config.gradient_accumulation_steps)
    # Scheduler steps = optimizer steps (every grad_accum micro-batches)
    total_steps = (len(train_loader) // grad_accum) * num_epochs
    warmup_steps = int(total_steps * config.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )
    eff_batch = config.batch_size * grad_accum
    print(f"Effective batch size: {config.batch_size} × {grad_accum} accum = {eff_batch}")

    early_stopper = EarlyStopping(
        patience=config.early_stopping_patience,
        output_dir=output_dir,
    )

    # ---- Training loop ----------------------------------------------------
    log: list[dict] = []

    print(f"\nStarting training for up to {num_epochs} epoch(s) …")
    for epoch in range(1, num_epochs + 1):
        print(f"\n{'='*60}")
        print(f"Epoch {epoch}/{num_epochs}")
        print(f"{'='*60}")

        train_loss = train_epoch(
            model, train_loader, optimizer, scheduler, loss_fn, device,
            grad_accum_steps=grad_accum,
        )
        val_loss, macro_f1 = evaluate_epoch(model, dev_loader, loss_fn, device)

        print(f"  train_loss={train_loss:.4f}  val_loss={val_loss:.4f}  macro_f1={macro_f1:.4f}")

        epoch_record = {
            "epoch": epoch,
            "train_loss": round(train_loss, 6),
            "val_loss": round(val_loss, 6),
            "macro_f1": round(macro_f1, 6),
        }
        log.append(epoch_record)

        should_stop = early_stopper.step(macro_f1, model)
        if should_stop:
            print(f"Early stopping triggered at epoch {epoch}.")
            break

    # ---- Save training log ------------------------------------------------
    log_path = output_dir / "training_log.json"
    with open(log_path, "w") as fh:
        json.dump(
            {
                "config": asdict(config),
                "epochs": log,
                "best_macro_f1": round(early_stopper.best_f1, 6),
                "best_checkpoint": str(early_stopper.best_checkpoint_path),
            },
            fh,
            indent=2,
        )
    print(f"\nTraining log saved → {log_path}")
    print(f"Best checkpoint   → {early_stopper.best_checkpoint_path}")
    print(f"Total wall time   : {(time.time() - t0) / 60:.1f} min")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> TrainConfig:
    p = argparse.ArgumentParser(
        description="Train the ContractNLI triage classifier."
    )
    p.add_argument("--train_path", default="data/contractnli/train.json")
    p.add_argument("--dev_path",   default="data/contractnli/dev.json")
    p.add_argument("--output_dir", default="checkpoints")
    p.add_argument("--hf_checkpoint", default=HF_CHECKPOINT)
    p.add_argument("--batch_size",  type=int,   default=8)
    p.add_argument("--gradient_accumulation_steps", type=int, default=4,
                   help="Micro-batches per optimizer step. Effective batch = batch_size * this.")
    p.add_argument("--lr",          type=float, default=2e-5)
    p.add_argument("--epochs",      type=int,   default=3)
    p.add_argument("--warmup_ratio",type=float, default=0.06)
    p.add_argument("--weight_decay",type=float, default=0.01)
    p.add_argument("--max_length",  type=int,   default=384)
    p.add_argument("--early_stopping_patience", type=int, default=2)
    p.add_argument(
        "--smoke",
        action="store_true",
        help=(
            "Smoke-test mode: 32 train / 16 dev samples, 1 epoch, CPU. "
            "Runs in ~2-3 minutes to verify the pipeline without a GPU."
        ),
    )
    args = p.parse_args()
    return TrainConfig(**vars(args))


if __name__ == "__main__":
    cfg = parse_args()
    main(cfg)
