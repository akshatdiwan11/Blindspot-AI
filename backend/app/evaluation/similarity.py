"""Similarity backends.

* Lexical similarity (character n-gram TF-IDF cosine) is always available and cheap.
* Semantic similarity uses sentence-transformers when installed and enabled; otherwise it
  is reported as unavailable rather than silently substituted.

Neither score is evidence of factual correctness.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.core.config import get_settings

log = logging.getLogger(__name__)


def lexical_similarity(a: list[str], b: list[str]) -> np.ndarray:
    """Row-wise cosine similarity between a[i] and b[i] using char 2-4 grams."""
    if not a:
        return np.array([])
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, sublinear_tf=True)
    try:
        vec.fit([*a, *b])
    except ValueError:  # all empty
        return np.zeros(len(a))
    A, B = vec.transform(a), vec.transform(b)
    num = np.asarray(A.multiply(B).sum(axis=1)).ravel()
    return np.clip(num, 0.0, 1.0)  # rows are L2-normalised already


@lru_cache(maxsize=1)
def _embedding_model():
    settings = get_settings()
    if not settings.enable_embeddings:
        return None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError:
        log.info("sentence-transformers not installed; semantic similarity disabled")
        return None
    try:
        return SentenceTransformer(settings.embedding_model, device="cpu")
    except Exception:  # model download failure etc.
        log.exception("Could not load embedding model")
        return None


def embeddings_available() -> bool:
    return _embedding_model() is not None


def embed(texts: list[str]) -> np.ndarray | None:
    model = _embedding_model()
    if model is None:
        return None
    return np.asarray(model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False))


def semantic_similarity(a: list[str], b: list[str]) -> np.ndarray | None:
    ea, eb = embed(a), embed(b)
    if ea is None or eb is None:
        return None
    return np.clip((ea * eb).sum(axis=1), -1.0, 1.0)
