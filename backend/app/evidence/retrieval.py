"""Lightweight retrieval over a run's cases (TF-IDF cosine; embeddings optional).

Used to pick representative failures, find failures similar to a given one, and find
*successful* cases that resemble failures (useful counter-evidence: same kind of input,
but the model got it right).
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from app.evaluation.similarity import embed


class CaseIndex:
    def __init__(self, texts: list[str], use_embeddings: bool = False):
        self.n = len(texts)
        self.method = "tfidf"
        M = None
        if use_embeddings:
            E = embed([t[:1500] for t in texts])
            if E is not None:
                M, self.method = E, "embeddings"
        if M is None:
            try:
                vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_df=0.95, sublinear_tf=True, max_features=30000)
                M = normalize(vec.fit_transform([t[:5000] for t in texts]))
            except ValueError:
                M = None
        self.M = M

    def _sims(self, query_rows: list[int]) -> np.ndarray:
        if self.M is None or not query_rows:
            return np.zeros(self.n)
        q = self.M[query_rows]
        centroid = np.asarray(q.mean(axis=0)).ravel()
        s = self.M @ centroid
        return np.asarray(s).ravel()

    def nearest(self, query_rows: list[int], candidates: list[int], k: int, exclude: set[int] | None = None) -> list[tuple[int, float]]:
        if not candidates:
            return []
        sims = self._sims(query_rows)
        exclude = exclude or set()
        scored = [(c, float(sims[c])) for c in candidates if c not in exclude]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]

    def representatives(self, rows: list[int], k: int = 5) -> list[int]:
        """Most typical members (closest to the group centroid), deterministic."""
        if len(rows) <= k:
            return list(rows)
        return [r for r, _ in self.nearest(rows, rows, k)]


def case_text(record: dict[str, Any], mapping: dict[str, Any]) -> str:
    parts = []
    for key in ("input_column", "expected_column", "actual_column"):
        col = mapping.get(key)
        if col and record.get(col):
            parts.append(str(record[col]))
    return "\n".join(parts)
