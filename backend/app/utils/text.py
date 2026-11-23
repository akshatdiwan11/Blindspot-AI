"""Text normalisation helpers shared by evaluation, discovery and clustering."""
from __future__ import annotations

import re
import string
import unicodedata
from collections import Counter

_PUNCT = set(string.punctuation) | {"।", "॥", "“", "”", "‘", "’", "–", "—", "…"}
_ARTICLES = re.compile(r"\b(a|an|the)\b", re.UNICODE)
_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"\w+", re.UNICODE)


def normalize_text(text: str, *, lowercase: bool = True, strip_punctuation: bool = True, remove_articles: bool = True) -> str:
    """SQuAD-style answer normalisation, Unicode aware (works for Devanagari etc.)."""
    t = unicodedata.normalize("NFKC", text or "")
    if lowercase:
        t = t.lower()
    if strip_punctuation:
        t = "".join(ch if ch not in _PUNCT else " " for ch in t)
    if remove_articles:
        t = _ARTICLES.sub(" ", t)
    return _WS.sub(" ", t).strip()


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text or "")


def token_prf(prediction: str, reference: str) -> tuple[float, float, float]:
    """Token-level precision, recall and F1 on already-normalised strings."""
    pred, ref = tokenize(prediction), tokenize(reference)
    if not pred and not ref:
        return 1.0, 1.0, 1.0
    if not pred or not ref:
        return 0.0, 0.0, 0.0
    common = Counter(pred) & Counter(ref)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0, 0.0, 0.0
    p, r = overlap / len(pred), overlap / len(ref)
    return p, r, 2 * p * r / (p + r)


def truncate(text: str | None, limit: int = 600) -> str:
    if text is None:
        return ""
    return text if len(text) <= limit else text[: limit - 1] + "…"
