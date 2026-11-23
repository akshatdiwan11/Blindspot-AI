"""Statistical helpers: Wilson intervals, Fisher tests, Benjamini-Hochberg."""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import fisher_exact, norm


def wilson_interval(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    z = norm.ppf(1 - (1 - confidence) / 2)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def fisher_greater(k_in: int, n_in: int, k_out: int, n_out: int) -> float:
    """One-sided p-value that the subgroup's failure rate exceeds the rest of the data."""
    if n_in == 0 or n_out == 0:
        return 1.0
    table = [[k_in, n_in - k_in], [k_out, n_out - k_out]]
    return float(fisher_exact(table, alternative="greater").pvalue)


def two_proportion_test(k1: int, n1: int, k2: int, n2: int) -> dict[str, float]:
    """Two-sided z-test for a difference in proportions (used to compare runs)."""
    if n1 == 0 or n2 == 0:
        return {"z": 0.0, "p_value": 1.0, "difference": 0.0}
    p1, p2 = k1 / n1, k2 / n2
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return {"z": 0.0, "p_value": 1.0, "difference": p2 - p1}
    z = (p2 - p1) / se
    return {"z": z, "p_value": float(2 * (1 - norm.cdf(abs(z)))), "difference": p2 - p1}


def benjamini_hochberg(pvalues: list[float]) -> list[float]:
    """Adjusted q-values controlling the false discovery rate."""
    m = len(pvalues)
    if m == 0:
        return []
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(q, 1.0)
    return out.tolist()
