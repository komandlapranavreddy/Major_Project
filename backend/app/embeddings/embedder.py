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
            raise ImportError(
                "sentence-transformers is not installed.\n"
                "Run: pip install sentence-transformers"
            )

        self._model_name = model_name
        self._model = SentenceTransformer(model_name)

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
            raise RuntimeError("Embedder.load() must be called before embed().")
        if not texts:
            raise ValueError("texts must be a non-empty list.")

        vectors: np.ndarray = self._model.encode(
            texts,
            normalize_embeddings=True,   # cosine ~ dot-product after normalisation
            batch_size=batch_size,
            show_progress_bar=False,
        )
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
