"""Failure clustering: groups failed cases that look alike so similar mistakes can be read together.

Representation (default, no external services):
  TF-IDF over a per-case document made of the input, expected and actual outputs plus an
  error-type marker, reduced with truncated SVD (LSA) and L2-normalised.
Optional: sentence-transformer embeddings when installed and enabled.

Clustering: k-means for k in [2, max_clusters], k chosen by cosine silhouette. If the data is
too small, too short, or no k gives a meaningful silhouette, clustering is skipped and the
reason is reported. Clusters are labelled from their highest-weight terms and any metadata
value that is over-represented in the cluster.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

from app.evaluation.config import ClusteringConfig
from app.evaluation.similarity import embed
from app.utils.text import normalize_text, tokenize

log = logging.getLogger(__name__)

MIN_FAILURES = 12
MIN_VOCAB = 5
MIN_SILHOUETTE = 0.05
_DIGITS = re.compile(r"\d+")


@dataclass
class ClusterResult:
    index: int
    label: str
    top_terms: list[str]
    members: list[int]            # case positions (index into the evaluated-case list)
    representatives: list[int]
    cohesion: float
    dominant_metadata: list[dict[str, Any]] = field(default_factory=list)
    error_types: dict[str, int] = field(default_factory=dict)


@dataclass
class ClusteringOutcome:
    clusters: list[ClusterResult]
    summary: dict[str, Any]


def _norm_tokens(s: str) -> list[str]:
    return [("num" if t.isdigit() else t) for t in tokenize(normalize_text(s or ""))]


def _doc(inp: str, exp: str, act: str, etype: str, extra_tokens: list[str] | None = None) -> str:
    """A 'mistake signature' document: what was dropped, what was added, and where the
    prediction came from in the input. Digits collapse to 'num' so the shape of the mistake
    matters more than the specific values."""
    e_tok, a_tok = _norm_tokens(exp), _norm_tokens(act)
    parts = [f"errtype_{etype or 'none'}", *(extra_tokens or [])]
    parts += [f"dropped_{t}" for t in dict.fromkeys(e_tok) if t not in a_tok]
    parts += [f"added_{t}" for t in dict.fromkeys(a_tok) if t not in e_tok]
    if not a_tok:
        parts.append("pred_empty")
    if inp and a_tok:
        inp_norm = normalize_text(inp[:20000])
        act_norm = normalize_text(act or "")
        pos = inp_norm.find(act_norm) if act_norm else -1
        if pos >= 0:
            parts.append("pred_in_input")
            before = _norm_tokens(inp_norm[max(0, pos - 80):pos])[-5:]
            parts += [f"near_{t}" for t in before if t != "num"]
        else:
            parts.append("pred_not_in_input")
    if len(a_tok) and len(e_tok):
        ratio = len(a_tok) / len(e_tok)
        parts.append("pred_shorter" if ratio < 0.8 else ("pred_longer" if ratio > 1.25 else "pred_same_length"))
    return " ".join(parts)


_PHRASES = {"pred_in_input": "prediction copied from elsewhere in the input", "pred_not_in_input": "prediction not found in the input",
            "pred_empty": "empty prediction", "pred_shorter": "shorter than expected", "pred_longer": "longer than expected",
            "pred_same_length": "", }


def _phrase(term: str) -> str:
    if term in _PHRASES:
        return _PHRASES[term]
    for prefix, text in (("wrongfield_", "wrong '{}' field"), ("missingfield_", "missing '{}' field"), ("extrafield_", "extra '{}' field"),
                         ("dropped_", "missing '{}'"), ("added_", "extra '{}'"), ("near_", "'{}' before prediction")):
        if term.startswith(prefix):
            return text.format(term[len(prefix):])
    return term


def cluster_failures(
    positions: list[int],
    inputs: list[str],
    expected: list[str],
    actual: list[str],
    error_types: list[str],
    metadata: dict[str, list[str]],
    cfg: ClusteringConfig,
    seed: int = 13,
    extra_tokens: list[list[str]] | None = None,
) -> ClusteringOutcome:
    n = len(positions)
    summary: dict[str, Any] = {"failures": n, "method": None, "k": None, "silhouette": None, "skipped": None}
    if not cfg.enabled:
        summary["skipped"] = "Clustering is turned off in this run's configuration."
        return ClusteringOutcome([], summary)
    if n < MIN_FAILURES:
        summary["skipped"] = f"Only {n} failures. At least {MIN_FAILURES} are needed for meaningful clusters."
        return ClusteringOutcome([], summary)

    extra_tokens = extra_tokens or [[] for _ in range(n)]
    docs = [_doc(i, e, a, t, x) for i, e, a, t, x in zip(inputs, expected, actual, error_types, extra_tokens)]
    vec = TfidfVectorizer(ngram_range=(1, 1), min_df=2, max_df=0.95, sublinear_tf=True, token_pattern=r"\S+", lowercase=False, max_features=20000)
    try:
        X_tfidf = vec.fit_transform(docs)
    except ValueError:
        summary["skipped"] = "The failed cases contain too little text to cluster."
        return ClusteringOutcome([], summary)
    vocab = np.array(vec.get_feature_names_out())
    if len(vocab) < MIN_VOCAB:
        summary["skipped"] = "The failed cases contain too little distinct text to cluster."
        return ClusteringOutcome([], summary)

    X = None
    if cfg.use_embeddings:
        E = embed([d[:1000] for d in docs])
        if E is not None:
            X, summary["method"] = E, "sentence-transformer embeddings + k-means"
        else:
            summary.setdefault("notes", []).append("Embeddings were requested but are not available; used TF-IDF instead.")
    if X is None:
        comps = min(50, X_tfidf.shape[1] - 1, n - 1)
        X = normalize(TruncatedSVD(n_components=comps, random_state=seed).fit_transform(X_tfidf)) if comps >= 2 else normalize(X_tfidf.toarray())
        summary["method"] = "TF-IDF + LSA + k-means"

    best = None
    max_k = min(cfg.max_clusters, n // 4)
    scores = {}
    for k in range(2, max_k + 1):
        km = KMeans(n_clusters=k, n_init=10, random_state=seed)
        labels = km.fit_predict(X)
        if len(set(labels)) < 2 or np.bincount(labels).min() < max(3, int(0.02 * n)):
            continue  # avoid clusters of one or two cases
        s = float(silhouette_score(X, labels, metric="cosine"))
        scores[k] = round(s, 4)
        if best is None or s > best[0] + 0.01:  # prefer fewer clusters unless clearly better
            best = (s, k, labels, km)
    summary["silhouette_by_k"] = scores
    if best is None or best[0] < MIN_SILHOUETTE:
        summary["skipped"] = "No clear cluster structure: the failures do not separate into distinct groups."
        return ClusteringOutcome([], summary)

    sil, k, labels, km = best
    summary.update({"k": k, "silhouette": round(sil, 4)})
    overall_meta = {col: Counter(vals) for col, vals in metadata.items()}
    clusters: list[ClusterResult] = []
    for c in range(k):
        idx = np.where(labels == c)[0]
        if len(idx) == 0:
            continue
        centroid = X[idx].mean(axis=0)
        sims = X[idx] @ centroid / (np.linalg.norm(centroid) + 1e-12)
        reps = idx[np.argsort(-sims)[:5]].tolist()
        # Top terms by mean TF-IDF weight in the cluster relative to all failures.
        w_in = np.asarray(X_tfidf[idx].mean(axis=0)).ravel()
        w_all = np.asarray(X_tfidf.mean(axis=0)).ravel()
        distinct = w_in - 0.5 * w_all
        order = np.argsort(-distinct)
        terms = [t for t in vocab[order] if not t.startswith("errtype_") and _phrase(t) and distinct[list(vocab).index(t)] > 0][:6]
        etypes = Counter(error_types[i] for i in idx)
        dominant = []
        for col, vals in metadata.items():
            cnt = Counter(vals[i] for i in idx)
            value, count = cnt.most_common(1)[0]
            share = count / len(idx)
            base_share = overall_meta[col][value] / n
            if share >= 0.6 and share >= 1.3 * base_share:
                dominant.append({"column": col, "value": value, "share": round(share, 3), "share_among_all_failures": round(base_share, 3)})
        top_err = etypes.most_common(1)[0][0] if etypes else ""
        label_bits = [", ".join(_phrase(t) for t in terms[:2])]
        if dominant:
            label_bits.append(f"{dominant[0]['column']} = {dominant[0]['value']}")
        if top_err:
            label_bits.append(top_err.replace("_", " "))
        clusters.append(ClusterResult(
            index=c, label=" · ".join(b for b in label_bits if b), top_terms=terms, members=idx.tolist(), representatives=reps,
            cohesion=round(float(sims.mean()), 4), dominant_metadata=dominant, error_types=dict(etypes),
        ))
    clusters.sort(key=lambda c: -len(c.members))
    for new_i, c in enumerate(clusters):
        c.index = new_i
    summary["note"] = "Clusters group failures with similar text. They help you read failures in batches; they do not explain why the model failed."
    return ClusteringOutcome(clusters, summary)
