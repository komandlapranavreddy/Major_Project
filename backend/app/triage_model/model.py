"""
model.py — TriageModel: single DeBERTa-v3-base NLI classifier.

Checkpoint: cross-encoder/nli-deberta-v3-base
  id2label: {0: "contradiction", 1: "entailment", 2: "neutral"}

Our mapping aligns exactly:
  0 → Contradiction
  1 → Entailment
  2 → NotMentioned

The classification head from the NLI checkpoint is reused without modification
because the label *count* (3) and *order* match our target classes — this is
the warm-start benefit. We do NOT replace the head with a random one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
from transformers import AutoTokenizer, DebertaV2ForSequenceClassification

from .dataset import LABEL2ID, ID2LABEL

try:
    # This file previously had zero `backend.app.*` dependencies, so it was
    # importable regardless of sys.path (e.g. train.py / verify_checkpoint.py's
    # documented `python -m triage_model.train` form, run with cwd=backend/app/,
    # which does NOT put the repo root on sys.path). Falling back to a plain
    # logger here — rather than letting this import fail — keeps that
    # invocation style working exactly as before if the shared config isn't
    # reachable from wherever this module happened to be imported.
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

# ---------------------------------------------------------------------------
# Checkpoint default
# ---------------------------------------------------------------------------

HF_CHECKPOINT = "cross-encoder/nli-deberta-v3-base"


# ---------------------------------------------------------------------------
# Device helper
# ---------------------------------------------------------------------------

def _best_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    # Apple Silicon — optional, no-op on Windows/Linux
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


# ---------------------------------------------------------------------------
# TriageModel
# ---------------------------------------------------------------------------

class TriageModel(nn.Module):
    """
    Thin wrapper around DebertaV2ForSequenceClassification.

    The wrapped model already has a 3-class head from NLI pre-training;
    we do NOT replace it so the warm-start weights are preserved.

    Usage
    -----
    model = TriageModel()
    model.load()                   # downloads from HF the first time
    logits = model.forward("premise text", "hypothesis text")
    label, conf = model.predict("premise text", "hypothesis text")
    """

    NUM_LABELS: int = 3

    def __init__(self, hf_checkpoint: str = HF_CHECKPOINT) -> None:
        super().__init__()
        self.hf_checkpoint = hf_checkpoint
        self.device = _best_device()
        self._model: Optional[DebertaV2ForSequenceClassification] = None
        self._tokenizer = None

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(
        self,
        checkpoint_path: Optional[str | Path] = None,
        *,
        device: Optional[torch.device] = None,
    ) -> "TriageModel":
        """
        Load the model and tokenizer.

        If checkpoint_path is provided, loads fine-tuned weights from disk
        (state_dict saved by train.py).  Otherwise falls back to the HF
        pretrained checkpoint.

        Parameters
        ----------
        checkpoint_path : path to a .pt file saved by train.py, or None
        device          : override the auto-detected device

        Returns self for chaining.
        """
        if device is not None:
            self.device = device

        log_step(logger, "model.load.start", hf_checkpoint=self.hf_checkpoint,
                 checkpoint_path=str(checkpoint_path) if checkpoint_path else None,
                 device=str(self.device))

        # Always load the architecture + tokenizer from HF.
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self.hf_checkpoint)
            self._model = DebertaV2ForSequenceClassification.from_pretrained(
                self.hf_checkpoint,
                num_labels=self.NUM_LABELS,
                ignore_mismatched_sizes=False,  # sizes MUST match — we verified
            )
        except Exception:
            # Common real causes: no internet on first-ever download (not yet
            # in the HF cache), or a corrupted local cache entry.
            log_exception(logger, "Failed to load base HF architecture/tokenizer",
                          hf_checkpoint=self.hf_checkpoint)
            raise

        if checkpoint_path is not None:
            checkpoint_path = Path(checkpoint_path)
            if not checkpoint_path.exists():
                logger.error("Checkpoint file does not exist: %s", checkpoint_path)
                raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
            try:
                state = torch.load(checkpoint_path, map_location="cpu")
                # Support both raw state_dict and wrapped {"model_state": ...} dicts
                if isinstance(state, dict) and "model_state" in state:
                    state = state["model_state"]
                self._model.load_state_dict(state, strict=True)
            except Exception:
                # strict=True means any architecture/key mismatch between the
                # checkpoint and hf_checkpoint's current head raises here —
                # log both paths so a mismatched checkpoint is diagnosable
                # instead of a bare "size mismatch for classifier.weight".
                log_exception(logger, "Failed to load fine-tuned state_dict",
                              checkpoint_path=str(checkpoint_path),
                              hf_checkpoint=self.hf_checkpoint)
                raise

        self._model.to(self.device)
        self._model.eval()
        log_step(logger, "model.load.done", hf_checkpoint=self.hf_checkpoint,
                 fine_tuned=checkpoint_path is not None, device=str(self.device))
        return self

    # ------------------------------------------------------------------
    # Inference helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._model is None or self._tokenizer is None:
            raise RuntimeError(
                "Call TriageModel.load() before running inference."
            )

    def forward(self, premise: str, hypothesis: str) -> torch.Tensor:
        """
        Run a single (premise, hypothesis) pair through the model.

        Returns raw logits of shape (3,) — [Contradiction, Entailment, NotMentioned].
        Inference only: gradients are disabled.
        """
        self._ensure_loaded()
        inputs = self._tokenizer(
            premise,
            hypothesis,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)

        return outputs.logits.squeeze(0)  # (3,)

    def predict(self, premise: str, hypothesis: str) -> tuple[str, float]:
        """
        High-level wrapper: returns (label_string, confidence).

        confidence = max softmax probability.
        """
        logits = self.forward(premise, hypothesis)
        probs = torch.softmax(logits, dim=-1)
        label_id = int(probs.argmax().item())
        confidence = float(probs[label_id].item())
        return ID2LABEL[label_id], confidence

    # ------------------------------------------------------------------
    # Training helpers
    # ------------------------------------------------------------------

    def train_mode(self) -> "TriageModel":
        """Switch to training mode (enables dropout etc.)."""
        self._ensure_loaded()
        self._model.train()
        return self

    def eval_mode(self) -> "TriageModel":
        """Switch back to eval mode."""
        self._ensure_loaded()
        self._model.eval()
        return self

    def parameters(self, recurse: bool = True):
        """Delegate to the inner HF model so optimizers work normally."""
        self._ensure_loaded()
        return self._model.parameters(recurse=recurse)

    def named_parameters(self, prefix: str = "", recurse: bool = True):
        self._ensure_loaded()
        return self._model.named_parameters(prefix=prefix, recurse=recurse)

    def state_dict(self, **kwargs):
        self._ensure_loaded()
        return self._model.state_dict(**kwargs)

    def __call__(self, **kwargs):
        """Allow using TriageModel directly as a callable in the training loop."""
        self._ensure_loaded()
        return self._model(**kwargs)
