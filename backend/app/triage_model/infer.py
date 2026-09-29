"""
triage_model/infer.py
──────────────────────
Runtime inference for the triage classifier.

Public API (matches architecture123.md):
  predict(clause: str, hypothesis: str) -> tuple[str, float]
      Returns (label, confidence) for a single clause/hypothesis pair.

Loads the fine-tuned checkpoint lazily on first call, from
TRIAGE_CHECKPOINT_PATH (env var) or DEFAULT_CHECKPOINT_PATH.

Updated 2026-09-27 to match model.py's actual checkpoint format: a raw
`state_dict` .pt FILE (saved by train.py's EarlyStopping via
`torch.save(model.state_dict(), ...)`), not an HF `save_pretrained()`
directory — so this now checks os.path.isfile(), not isdir(), and passes
the checkpoint straight through to TriageModel.load(), which reconstructs
the architecture from HF_CHECKPOINT ("cross-encoder/nli-deberta-v3-base")
and loads the fine-tuned weights on top. Label order also fixed to match
the checkpoint's native head (Contradiction=0, Entailment=1,
NotMentioned=2) via triage_model.dataset.LABEL2ID/ID2LABEL — the previous
LABELS=(Entailment, Contradiction, NotMentioned) tuple here did NOT match
and would have silently swapped Entailment/Contradiction predictions.

TRIAGE_CHECKPOINT_PATH selects one of three modes:
  - path to a .pt file   -> fine-tuned weights (Config C; the default path)
  - "pretrained"         -> off-the-shelf cross-encoder/nli-deberta-v3-base,
                            zero ContractNLI fine-tuning (Config B). Its
                            native head order matches LABEL2ID index-for-index
                            (verified against the HF config), so no remap.
  - anything missing     -> the untrained STUB below

If no checkpoint has been trained yet, falls back to a STUB heuristic
classifier so the LangGraph agent and eval harness can be built and tested
end-to-end before the real model lands. THE STUB IS NOT A TRAINED MODEL —
it is deterministic lexical overlap, un-calibrated, and must never be used
to generate accuracy, calibration, or paper numbers. A loud one-time
warning is printed the first time it's used, mirroring the existing
LLM_PROVIDER=groq warning in llm/ollama_client.py.

Once the real checkpoint is trained and dropped at TRIAGE_CHECKPOINT_PATH,
predict() switches over automatically — no caller changes required.
"""

from __future__ import annotations

import os
import re

from backend.app.triage_model.model import TriageModel
from backend.app.logging_config import get_logger, log_exception, log_step

logger = get_logger(__name__)

DEFAULT_CHECKPOINT_PATH = os.path.join(
    os.path.dirname(__file__), "checkpoints", "current", "best_model.pt"
)

PRETRAINED_SENTINEL = "pretrained"

_model: TriageModel | None = None
_stub_warned = False


def _get_model() -> TriageModel | None:
    """Lazily load the selected model. Returns None if no checkpoint exists (stub mode)."""
    global _model
    if _model is not None:
        return _model

    checkpoint_path = os.getenv("TRIAGE_CHECKPOINT_PATH", DEFAULT_CHECKPOINT_PATH)
    candidate = TriageModel()
    try:
        if checkpoint_path.strip().lower() == PRETRAINED_SENTINEL:
            log_step(logger, "triage.load", mode="pretrained (Config B, no fine-tuning)")
            candidate.load(checkpoint_path=None)
        elif os.path.isfile(checkpoint_path):
            log_step(logger, "triage.load", mode="fine-tuned (Config C)",
                     checkpoint_path=checkpoint_path)
            candidate.load(checkpoint_path=checkpoint_path)
        else:
            logger.warning(
                "No triage checkpoint at %r and it is not the '%s' sentinel - "
                "falling back to the untrained lexical-overlap STUB.",
                checkpoint_path, PRETRAINED_SENTINEL,
            )
            return None
    except Exception:
        log_exception(logger, "TriageModel.load() failed",
                      checkpoint_path=checkpoint_path)
        raise

    logger.info("Triage model loaded successfully (device=%s)", candidate.device)
    _model = candidate
    return _model


def predict(clause: str, hypothesis: str) -> tuple[str, float]:
    """
    Single-pair triage inference.

    Args:
        clause:     Contract clause text (the premise).
        hypothesis: NDA hypothesis text.

    Returns:
        (label, confidence) — label is one of
        {"Entailment", "Contradiction", "NotMentioned"}, confidence in
        [0, 1] is the softmax probability of the predicted class.
    """
    model = _get_model()
    if model is not None:
        try:
            label, confidence = model.predict(clause, hypothesis)
        except Exception:
            log_exception(logger, "triage predict() failed",
                          clause_len=len(clause), hypothesis=hypothesis[:80])
            raise
        logger.debug("triage.predict -> %s (%.4f) | clause_len=%d hyp=%r",
                    label, confidence, len(clause), hypothesis[:60])
        return label, confidence

    return _stub_predict(clause, hypothesis)


def reset_cache() -> None:
    """Force the next predict() call to re-check for a checkpoint. Test helper."""
    global _model, _stub_warned
    _model = None
    _stub_warned = False


# ─────────────────────────────────────────────────────────────────────────────
# Stub fallback — NOT a trained model. Replace by training and dropping a
# checkpoint at TRIAGE_CHECKPOINT_PATH (see triage_model/train.py).
# ─────────────────────────────────────────────────────────────────────────────

_CONTRADICTION_CUES = ("shall not", "must not", "prohibited", "no later than", "except")
_WORD_RE = re.compile(r"[a-z]+")


def _stub_predict(clause: str, hypothesis: str) -> tuple[str, float]:
    """
    Deterministic lexical-overlap heuristic — a placeholder only, used so the
    agent and eval harness are runnable before the real triage model exists.
    Confidence is intentionally mediocre and un-calibrated.
    """
    global _stub_warned
    if not _stub_warned:
        checkpoint_path = os.getenv("TRIAGE_CHECKPOINT_PATH", DEFAULT_CHECKPOINT_PATH)
        logger.warning(
            "No trained checkpoint found at %r - using an untrained "
            "lexical-overlap STUB. Do not use these predictions for "
            "accuracy, calibration, or paper numbers.", checkpoint_path,
        )
        _stub_warned = True

    clause_words = set(_WORD_RE.findall(clause.lower()))
    hyp_words = set(_WORD_RE.findall(hypothesis.lower()))
    if not hyp_words:
        return "NotMentioned", 0.5

    overlap = len(clause_words & hyp_words) / len(hyp_words)

    if overlap < 0.15:
        return "NotMentioned", min(0.5 + (0.15 - overlap), 0.95)
    if any(cue in clause.lower() for cue in _CONTRADICTION_CUES):
        return "Contradiction", min(0.5 + overlap, 0.95)
    return "Entailment", min(0.5 + overlap, 0.95)
