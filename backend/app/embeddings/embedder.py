"""
embeddings/embedder.py
──────────────────────
Wraps BAAI/bge-small-en via sentence-transformers to produce
384-d clause embeddings for ChromaDB.

Public API (matches architecture123.md):
  class Embedder
    .load(model_name: str = "BAAI/bge-small-en") -> None
    .embed(texts: list[str]) -> np.ndarray
"""

from __future__ import annotations

import numpy as np

try:
    # This file previously had zero `backend.app.*` dependencies and was a
    # standalone leaf module. Falling back to a plain logger (rather than
    # letting this import fail) preserves that if it's ever imported from a
    # context without the repo root on sys.path.
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


class Embedder:
    """
    Thin wrapper around a SentenceTransformer model.

    Usage::

        embedder = Embedder()
        embedder.load()          # downloads / loads BAAI/bge-small-en
        vecs = embedder.embed(["clause text 1", "clause text 2"])
        # vecs.shape == (2, 384), float32, L2-normalised
    """

    def __init__(self) -> None:
        self._model = None
        self._model_name: str = ""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load(self, model_name: str = "BAAI/bge-small-en") -> None:
        """
        Load the sentence-transformers model.

        Args:
            model_name: HuggingFace model ID. Default is BAAI/bge-small-en
                        (384 dims, fast, strong retrieval performance).
        """
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError:
            logger.error("sentence-transformers is not installed - cannot load %s",
                         model_name)
            raise ImportError(
                "sentence-transformers is not installed.\n"
                "Run: pip install sentence-transformers"
            )

        log_step(logger, "embedder.load.start", model_name=model_name)
        try:
            self._model = SentenceTransformer(model_name)
        except Exception:
            # Most common real cause: no internet / HF Hub unreachable on
            # first-ever load (the model isn't cached yet). Log the exact
            # model name so it's obvious what to pre-download or check.
            log_exception(logger, "SentenceTransformer load failed",
                          model_name=model_name)
            raise
        self._model_name = model_name
        log_step(logger, "embedder.load.done", model_name=model_name)

    def embed(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """
        Embed a list of strings.

        Args:
            texts:      Non-empty list of strings to encode.
            batch_size: Encoding batch size (default 32).

        Returns:
            np.ndarray of shape (len(texts), embedding_dim), dtype float32.
            Vectors are L2-normalised (required for cosine similarity in ChromaDB).

        Raises:
            RuntimeError: if load() has not been called.
            ValueError:   if texts is empty.
        """
        if self._model is None:
            logger.error("embed() called before load() - %d texts dropped.", len(texts))
            raise RuntimeError("Embedder.load() must be called before embed().")
        if not texts:
            logger.error("embed() called with an empty texts list.")
            raise ValueError("texts must be a non-empty list.")

        try:
            vectors: np.ndarray = self._model.encode(
                texts,
                normalize_embeddings=True,   # cosine ~ dot-product after normalisation
                batch_size=batch_size,
                show_progress_bar=False,
            )
        except Exception:
            log_exception(logger, "encode() failed", n_texts=len(texts),
                          batch_size=batch_size, model_name=self._model_name)
            raise
        logger.debug("embed() encoded %d texts -> shape %s", len(texts), vectors.shape)
        return vectors.astype(np.float32)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        return self._model_name

    def __repr__(self) -> str:
        status = f"loaded({self._model_name})" if self._model else "unloaded"
        return f"Embedder({status})"
