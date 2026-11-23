"""Text generation / QA / extraction evaluation (deterministic)."""
from __future__ import annotations

import numpy as np

from app.evaluation.config import TextEvalConfig
from app.evaluation.similarity import lexical_similarity, semantic_similarity
from app.evaluation.types import CaseResult, EvaluationOutcome, Metric
from app.utils.text import normalize_text, token_prf


def evaluate_text(indices: list[int], case_ids: list[str], expected: list[str], actual: list[str | None], cfg: TextEvalConfig) -> EvaluationOutcome:
    norm = lambda s: normalize_text(s or "", lowercase=cfg.lowercase, strip_punctuation=cfg.strip_punctuation, remove_articles=cfg.remove_articles)  # noqa: E731
    exp_n = [norm(e) for e in expected]
    act_raw = [a or "" for a in actual]
    act_n = [norm(a) for a in act_raw]

    lexical = lexical_similarity(exp_n, act_n) if cfg.compute_similarity else None
    semantic = semantic_similarity(expected, act_raw) if (cfg.compute_similarity or cfg.match == "similarity") else None
    if cfg.match == "similarity" and semantic is None:
        # Fall back explicitly and record it; never pretend lexical overlap is semantic.
        sim_for_match, sim_kind = lexical, "lexical"
    else:
        sim_for_match, sim_kind = semantic, "semantic"

    cases: list[CaseResult] = []
    em_list, nem_list, p_list, r_list, f_list = [], [], [], [], []
    for k, idx in enumerate(indices):
        em = float(act_raw[k].strip() == (expected[k] or "").strip())
        nem = float(act_n[k] == exp_n[k])
        p, r, f = token_prf(act_n[k], exp_n[k])
        em_list.append(em); nem_list.append(nem); p_list.append(p); r_list.append(r); f_list.append(f)
        if cfg.match == "exact":
            correct, score = bool(em), em
        elif cfg.match == "normalized_exact":
            correct, score = bool(nem), nem
        elif cfg.match == "token_f1":
            correct, score = f >= cfg.threshold, f
        else:
            s = float(sim_for_match[k]) if sim_for_match is not None else 0.0
            correct, score = s >= cfg.threshold, s
        if correct:
            etype = ""
        elif not act_raw[k].strip():
            etype = "empty_output"
        elif f > 0:
            etype = "partial_match"
        else:
            etype = "mismatch"
        details = {"token_f1": round(f, 4), "normalized_exact": bool(nem)}
        if lexical is not None:
            details["lexical_similarity"] = round(float(lexical[k]), 4)
        if semantic is not None:
            details["semantic_similarity"] = round(float(semantic[k]), 4)
        cases.append(CaseResult(idx, case_ids[k], correct, score, etype, details))

    n = len(cases)
    mean = lambda xs: float(np.mean(xs)) if xs else None  # noqa: E731
    accuracy = sum(c.correct for c in cases) / n if n else None
    metrics = [
        Metric("accuracy", accuracy, extra={"definition": f"share of cases judged correct by '{cfg.match}' matching"}),
        Metric("exact_match", mean(em_list)),
        Metric("normalized_exact_match", mean(nem_list)),
        Metric("token_precision", mean(p_list)),
        Metric("token_recall", mean(r_list)),
        Metric("token_f1", mean(f_list)),
        Metric("failure_rate", 1 - accuracy if accuracy is not None else None),
    ]
    if lexical is not None:
        metrics.append(Metric("lexical_similarity", float(np.mean(lexical)) if n else None, extra={"note": "character n-gram overlap; not a measure of factual correctness"}))
    if semantic is not None:
        metrics.append(Metric("semantic_similarity", float(np.mean(semantic)) if n else None, extra={"note": "embedding cosine similarity; not a measure of factual correctness"}))
    error_types: dict[str, int] = {}
    for c in cases:
        if not c.correct:
            error_types[c.error_type] = error_types.get(c.error_type, 0) + 1
    extras = {"match": cfg.match, "threshold": cfg.threshold, "similarity_backend": sim_kind if cfg.match == "similarity" else None,
              "semantic_available": semantic is not None, "error_types": error_types}
    return EvaluationOutcome("text", cases, metrics, "accuracy", accuracy, extras)
