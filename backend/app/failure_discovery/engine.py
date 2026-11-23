"""Hidden failure discovery.

Finds interpretable subgroups (rules over metadata and derived features) whose failure rate
is significantly higher than the rest of the data.

Methods
  single  every value of every categorical feature and every quantile bin of every numeric feature
  pair    conjunctions of two single conditions from different features
  tree    leaves of a shallow decision tree (fitted on a training split, validated on a holdout)

Safeguards
  * minimum subgroup size and minimum failure count
  * one-sided Fisher exact tests of subgroup vs. complement, with Benjamini-Hochberg FDR
    correction across *every* hypothesis tested (multiple comparisons)
  * tree rules are scored only on held-out rows they were not fitted on (overfitting)
  * a pair rule must beat both of its parent conditions (no restating a single effect)
  * near-duplicate groups (Jaccard overlap of members) are merged
  * features that almost perfectly separate failures are flagged as possible leakage and dropped
  * missing values are kept as an explicit "(missing)" level so missingness can be found
  * class-imbalance notes for classification tasks
Associations found here are correlations, not causes.
"""
from __future__ import annotations

import itertools
from collections import Counter
import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

from app.evaluation.config import DiscoveryConfig
from app.failure_discovery.features import MISSING, FeatureFrame, apply_conditions, condition_label, rule_text
from app.failure_discovery.stats import benjamini_hochberg, fisher_greater, wilson_interval

log = logging.getLogger(__name__)

MIN_FAILURES_IN_GROUP = 3
PAIR_CANDIDATE_LIMIT = 40
JACCARD_DUPLICATE = 0.85
LEAKAGE_SEPARATION = 0.98


@dataclass
class DiscoveredGroup:
    conditions: list[dict[str, Any]]
    method: str
    mask: np.ndarray
    n: int
    k: int
    rate: float
    complement_rate: float
    p_value: float
    q_value: float = 1.0
    ci: tuple[float, float] = (0.0, 1.0)
    notes: list[str] = field(default_factory=list)
    holdout: dict[str, Any] | None = None
    reliability: str = "tentative"
    severity: str = "low"
    severity_score: float = 0.0
    residual: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return " AND ".join(condition_label(c) for c in self.conditions)


@dataclass
class DiscoveryResult:
    groups: list[DiscoveredGroup]
    baseline_error_rate: float
    summary: dict[str, Any]


def _items(ff: FeatureFrame, cfg: DiscoveryConfig) -> list[tuple[list[dict[str, Any]], np.ndarray]]:
    """Single-condition candidates: (conditions, mask)."""
    out = []
    df = ff.frame
    for name, spec in ff.specs.items():
        col = df[name]
        if spec.kind == "categorical":
            for value in col.unique():
                cond = [{"feature": name, "op": "==", "value": str(value)}]
                out.append((cond, (col == value).to_numpy()))
        else:
            num = pd.to_numeric(col, errors="coerce")
            present = num.dropna()
            distinct = np.sort(present.unique())
            if len(distinct) < 2:
                continue
            integer = bool(np.all(np.equal(np.mod(distinct, 1), 0)))
            if len(distinct) <= 12:
                # Low-cardinality numbers: one-sided thresholds at each observed value.
                for v in distinct[1:]:
                    for cond in ({"feature": name, "op": "between", "low": float(v), "high": None},
                                 {"feature": name, "op": "between", "low": None, "high": float(v)}):
                        out.append(([cond], apply_conditions(df, [cond])))
            else:
                try:
                    _, edges = pd.qcut(present, q=cfg.numeric_bins, retbins=True, duplicates="drop")
                except ValueError:
                    continue
                edges = sorted(set(round(float(e), 6) for e in edges))
                if integer:
                    edges = sorted(set(math.floor(e) for e in edges[:-1]) | {math.floor(edges[-1]) + 1})
                for lo, hi in zip(edges[:-1], edges[1:]):
                    low = None if lo == edges[0] else lo
                    high = None if hi == edges[-1] else hi
                    if low is None and high is None:
                        continue
                    cond = [{"feature": name, "op": "between", "low": low, "high": high}]
                    out.append((cond, apply_conditions(df, cond)))
                # Upper and lower tails as their own candidates.
                for cond in ({"feature": name, "op": "between", "low": edges[-2], "high": None},
                             {"feature": name, "op": "between", "low": None, "high": edges[1]}):
                    out.append(([cond], apply_conditions(df, [cond])))
            if num.isna().any():
                cond = [{"feature": name, "op": "is_missing"}]
                out.append((cond, num.isna().to_numpy()))
    return out


def _stats(mask: np.ndarray, y: np.ndarray) -> tuple[int, int, float, float, float]:
    n = int(mask.sum())
    k = int(y[mask].sum())
    n_out = len(y) - n
    k_out = int(y.sum()) - k
    rate = k / n if n else 0.0
    comp = k_out / n_out if n_out else 0.0
    return n, k, rate, comp, fisher_greater(k, n, k_out, n_out)


def _detect_leakage(ff: FeatureFrame, y: np.ndarray, items) -> set[str]:
    """Features where one condition captures almost all failures and almost nothing else."""
    leaky: set[str] = set()
    total_fail = y.sum()
    if total_fail == 0:
        return leaky
    for conds, mask in items:
        n = mask.sum()
        if n == 0:
            continue
        k = y[mask].sum()
        precision, recall = k / n, k / total_fail
        if precision >= LEAKAGE_SEPARATION and recall >= LEAKAGE_SEPARATION:
            leaky.add(conds[0]["feature"])
    return leaky


def _tree_groups(ff: FeatureFrame, y: np.ndarray, cfg: DiscoveryConfig, seed: int = 7) -> tuple[list[DiscoveredGroup], dict[str, Any]]:
    df = ff.frame
    if len(df) < 4 * cfg.min_group_size or y.sum() < 10 or (len(y) - y.sum()) < 10:
        return [], {"skipped": "not enough rows or failures for a held-out tree"}
    cols, names = [], []
    for name, spec in ff.specs.items():
        if spec.kind == "categorical":
            for value in df[name].value_counts().index:
                if (df[name] == value).sum() >= max(5, cfg.min_group_size // 2):
                    cols.append((df[name] == value).astype(float).to_numpy())
                    names.append(("cat", name, value))
        else:
            num = pd.to_numeric(df[name], errors="coerce")
            cols.append(num.fillna(num.median()).to_numpy(dtype=float))
            names.append(("num", name, None))
    if not cols:
        return [], {"skipped": "no usable features"}
    X = np.column_stack(cols)
    idx = np.arange(len(y))
    tr, ho = train_test_split(idx, test_size=0.35, random_state=seed, stratify=y)
    tree = DecisionTreeClassifier(max_depth=cfg.max_tree_depth, min_samples_leaf=max(cfg.min_group_size // 2, 5),
                                  class_weight="balanced", random_state=seed)
    tree.fit(X[tr], y[tr])
    t = tree.tree_
    base_tr = y[tr].mean()
    groups: list[DiscoveredGroup] = []

    def walk(node: int, conds: list[dict[str, Any]]):
        if t.children_left[node] == -1:
            if not conds:
                return
            leaf_mask_tr = apply_conditions(df.iloc[tr].reset_index(drop=True), conds)
            if leaf_mask_tr.sum() == 0 or y[tr][leaf_mask_tr].mean() <= base_tr * 1.25:
                return
            pruned = _prune(_simplify(conds), df.iloc[tr].reset_index(drop=True), y[tr])
            groups.append(_from_tree_leaf(pruned, df, y, ho, cfg))
            return
        kind, name, value = names[t.feature[node]]
        thr = float(t.threshold[node])
        if kind == "cat":
            left = {"feature": name, "op": "!=", "value": str(value)}
            right = {"feature": name, "op": "==", "value": str(value)}
        else:
            num = pd.to_numeric(df[name], errors="coerce").dropna()
            integer = bool(np.all(np.equal(np.mod(num, 1), 0)))
            cut = math.floor(thr) + 1 if integer else round(thr, 4)
            left = {"feature": name, "op": "between", "low": None, "high": cut}
            right = {"feature": name, "op": "between", "low": cut, "high": None}
        walk(t.children_left[node], conds + [left])
        walk(t.children_right[node], conds + [right])

    walk(0, [])
    groups = [g for g in groups if g is not None]
    return groups, {"depth": int(tree.get_depth()), "leaves": int(tree.get_n_leaves()), "train_rows": len(tr), "holdout_rows": len(ho)}


def _simplify(conds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge numeric bounds on the same feature and drop '≠' conditions implied by an '=='."""
    out: list[dict[str, Any]] = []
    ranges: dict[str, dict[str, Any]] = {}
    eq = {c["feature"] for c in conds if c["op"] == "=="}
    for c in conds:
        if c["op"] == "between":
            r = ranges.setdefault(c["feature"], {"feature": c["feature"], "op": "between", "low": None, "high": None})
            if c["low"] is not None:
                r["low"] = c["low"] if r["low"] is None else max(r["low"], c["low"])
            if c["high"] is not None:
                r["high"] = c["high"] if r["high"] is None else min(r["high"], c["high"])
        elif c["op"] == "!=" and c["feature"] in eq:
            continue
        else:
            out.append(c)
    return out + list(ranges.values())


def _prune(conds: list[dict[str, Any]], df: pd.DataFrame, y: np.ndarray, tolerance: float = 0.03) -> list[dict[str, Any]]:
    """Greedily drop conditions that do not raise the rule's failure rate (on training rows)."""
    conds = list(conds)

    def rate(cs):
        m = apply_conditions(df, cs)
        return y[m].mean() if m.sum() else 0.0

    changed = True
    while changed and len(conds) > 1:
        changed = False
        full = rate(conds)
        for i in range(len(conds)):
            rest = conds[:i] + conds[i + 1:]
            if rate(rest) >= full - tolerance:
                conds = rest
                changed = True
                break
    return conds


def _from_tree_leaf(conds, df, y, ho, cfg) -> DiscoveredGroup | None:
    mask = apply_conditions(df, conds)
    n, k, rate, comp, _ = _stats(mask, y)
    ho_mask = np.zeros(len(y), dtype=bool)
    ho_mask[ho] = True
    in_ho = mask & ho_mask
    out_ho = ~mask & ho_mask
    n_h, k_h = int(in_ho.sum()), int(y[in_ho].sum())
    n_o, k_o = int(out_ho.sum()), int(y[out_ho].sum())
    p_holdout = fisher_greater(k_h, n_h, k_o, n_o)
    holdout = {"rows": n_h, "failures": k_h, "error_rate": k_h / n_h if n_h else None,
               "complement_error_rate": k_o / n_o if n_o else None, "p_value": p_holdout}
    g = DiscoveredGroup(conds, "tree", mask, n, k, rate, comp, p_holdout, holdout=holdout)
    g.notes.append(f"Decision-tree rule validated on {n_h} held-out rows: error rate {holdout['error_rate']:.0%} vs {holdout['complement_error_rate']:.0%} for other held-out rows." if n_h and n_o else "Too few held-out rows to validate this rule.")
    return g


SIMPLICITY_PENALTY = 0.3  # per extra condition: prefer "language = Hindi" over a 2-condition tree path


def _cond_key(c: dict[str, Any]) -> tuple:
    return (c["feature"], c["op"], str(c.get("value")), c.get("low"), c.get("high"))


def _prefer_explaining_refinements(pool: list[DiscoveredGroup], y: np.ndarray, base: float) -> list[DiscoveredGroup]:
    """Drop a broad rule when one narrower rule inside it explains its failures.

    Example: "region = IN" fails at 21%, but only because "channel = chat AND region = IN" fails
    at 45% while the other IN rows fail at the normal rate. Reporting the broad rule would point
    people at the wrong slice, so the narrower rule is kept and the broad one is dropped. The
    simplicity preference still applies whenever the broad rule has extra failures of its own.
    """
    dropped: set[int] = set()
    for parent in pool:
        p_keys = {_cond_key(c) for c in parent.conditions}
        parent_excess = parent.k - parent.n * base
        if parent_excess <= 0:
            continue
        best_child = None
        for child in pool:
            if child is parent or child.reliability != "reliable" or len(child.conditions) <= len(parent.conditions):
                continue
            if not p_keys <= {_cond_key(c) for c in child.conditions}:
                continue
            rest = parent.mask & ~child.mask
            n_rest, k_rest = int(rest.sum()), int(y[rest].sum())
            # Only a real narrowing counts: the leftover rows must be numerous enough to show they
            # fail at the normal rate. Otherwise a near-copy of the broad rule (for example
            # "Hinglish AND no numbers", 108 of 121 Hinglish rows) would replace the real cause.
            if child.n > 0.75 * parent.n or n_rest < 20:
                continue
            others = ~parent.mask
            n_o, k_o = int(others.sum()), int(y[others].sum())
            # The rest of the broad group must not be elevated on its own...
            if fisher_greater(k_rest, n_rest, k_o, n_o) <= 0.05 or k_rest / n_rest > base + 0.03:
                continue
            # ...and the narrow rule must carry most of the broad rule's excess failures.
            if child.k - child.n * base < 0.8 * parent_excess:
                continue
            if best_child is None or child.p_value < best_child.p_value:
                best_child = child
        if best_child is not None:
            dropped.add(id(parent))
            rest = parent.mask & ~best_child.mask
            best_child.notes.append(
                f"Explains the raised error rate of the broader rule '{parent.name}': the rest of that group fails at "
                f"{int(y[rest].sum()) / int(rest.sum()):.0%}, close to the overall {base:.0%}.")
    return [g for g in pool if id(g) not in dropped]


def _select_groups(candidates: list[DiscoveredGroup], y: np.ndarray, base: float, limit: int) -> list[DiscoveredGroup]:
    """Greedy sequential covering over candidate groups.

    At each step pick the group with the most *new* excess failures (failures beyond the baseline
    rate among rows not covered by groups already picked), discounted for rule complexity.
    Reliable groups are always considered before tentative ones.
    """
    total = len(y)
    covered = np.zeros(total, dtype=bool)
    pool = _prefer_explaining_refinements(list(candidates), y, base)
    kept: list[DiscoveredGroup] = []
    while pool and len(kept) < limit:
        best, best_key = None, None
        for g in pool:
            res = g.mask & ~covered
            n_r, k_r = int(res.sum()), int(y[res].sum())
            excess_r = k_r - n_r * base
            key = (0 if g.reliability == "reliable" else 1, -(excess_r * (1 - SIMPLICITY_PENALTY * (len(g.conditions) - 1))))
            if best_key is None or key < best_key:
                best, best_key = g, key
        pool.remove(best)
        feats = {c["feature"] for c in best.conditions}
        if any({c["feature"] for c in h.conditions} == feats and (best.mask & h.mask).sum() >= 0.6 * min(best.n, h.n) for h in kept):
            continue  # another threshold / value of the same rule already reported
        res = best.mask & ~covered
        n_r, k_r = int(res.sum()), int(y[res].sum())
        full_excess = best.k - best.n * base
        excess_r = k_r - n_r * base
        if kept:
            outside = ~best.mask & ~covered
            n_o, k_o = int(outside.sum()), int(y[outside].sum())
            p_res = fisher_greater(k_r, n_r, k_o, n_o) if n_r >= 5 and n_o >= 5 else 1.0
            best.residual = {"rows": n_r, "failures": k_r, "error_rate": k_r / n_r if n_r else None,
                             "other_error_rate": k_o / n_o if n_o else None, "p_value": p_res}
            if excess_r < max(2.0, 0.5 * full_excess) and p_res > 0.05:
                continue  # mostly the same failures as a group already reported
            if p_res <= 0.05 and n_r:
                best.notes.append(f"Still elevated after removing higher-ranked groups: {k_r / n_r:.0%} vs {k_o / n_o:.0%} on the remaining rows.")
            else:
                best.notes.append("Overlaps substantially with higher-ranked groups; it may be the same weakness seen from another angle.")
        kept.append(best)
        covered |= best.mask
    kept.sort(key=lambda g: (0 if g.reliability == "reliable" else 1, -g.severity_score))
    return kept


def discover_failures(ff: FeatureFrame, failures: np.ndarray, cfg: DiscoveryConfig, *, task_type: str = "", class_balance: dict[str, int] | None = None) -> DiscoveryResult:
    y = failures.astype(int)
    total = len(y)
    base = float(y.mean()) if total else 0.0
    summary: dict[str, Any] = {
        "records": total, "failures": int(y.sum()), "baseline_error_rate": base,
        "features_used": [{"name": s.name, "kind": s.kind, "origin": s.origin, "description": s.description} for s in ff.specs.values()],
        "features_excluded": list(ff.excluded), "min_group_size": cfg.min_group_size, "fdr_alpha": cfg.alpha,
        "safeguards": [], "warnings": [],
    }
    if total == 0 or y.sum() == 0:
        summary["warnings"].append("No failures to analyse." if total else "No records to analyse.")
        return DiscoveryResult([], base, summary)
    if y.sum() == total:
        summary["warnings"].append("Every record failed, so no subgroup can be worse than the baseline.")
        return DiscoveryResult([], base, summary)
    if not ff.specs:
        summary["warnings"].append("No metadata or derivable features are available. Map metadata columns or an input column to enable failure discovery.")
        return DiscoveryResult([], base, summary)
    if total < 2 * cfg.min_group_size:
        summary["warnings"].append(f"Only {total} records: subgroups smaller than {cfg.min_group_size} are not tested, so few or no groups can be found.")

    items = _items(ff, cfg)
    leaky = _detect_leakage(ff, y, items)
    if leaky:
        for f in sorted(leaky):
            summary["features_excluded"].append({"feature": f, "reason": "possible leakage: this feature almost perfectly separates failures from successes"})
        items = [(c, m) for c, m in items if c[0]["feature"] not in leaky]
        for f in leaky:
            ff.specs.pop(f, None)
        summary["safeguards"].append("Dropped features that look like they encode the outcome (leakage).")

    min_n = cfg.min_group_size
    tested: list[DiscoveredGroup] = []
    singles: list[DiscoveredGroup] = []
    for conds, mask in items:
        n, k, rate, comp, p = _stats(mask, y)
        if n < min_n or n == total:
            continue
        g = DiscoveredGroup(conds, "single", mask, n, k, rate, comp, p)
        tested.append(g)
        if rate > base:
            singles.append(g)

    # Pairs from the most promising single conditions on different features.
    promising = sorted(singles, key=lambda g: (g.rate - base) * math.sqrt(g.n), reverse=True)[:PAIR_CANDIDATE_LIMIT]
    parent_rate = {id(g): g.rate for g in promising}
    pairs: list[DiscoveredGroup] = []
    for a, b in itertools.combinations(promising, 2):
        if a.conditions[0]["feature"] == b.conditions[0]["feature"]:
            continue
        mask = a.mask & b.mask
        n, k, rate, comp, p = _stats(mask, y)
        if n < min_n:
            continue
        g = DiscoveredGroup(a.conditions + b.conditions, "pair", mask, n, k, rate, comp, p)
        tested.append(g)
        if n in (a.n, b.n):  # same rows as a parent condition: nothing new to report
            continue
        if rate < max(parent_rate[id(a)], parent_rate[id(b)]) + 0.05:
            continue
        # Each condition must add signal *within* the other (conditional test), otherwise the
        # pair just restates one strong single effect.
        p_b_given_a = fisher_greater(k, n, int(y[a.mask & ~b.mask].sum()), int((a.mask & ~b.mask).sum()))
        p_a_given_b = fisher_greater(k, n, int(y[b.mask & ~a.mask].sum()), int((b.mask & ~a.mask).sum()))
        if max(p_b_given_a, p_a_given_b) < 0.01:
            g.notes.append(f"Both conditions add signal: each raises the error rate within the other (p = {p_b_given_a:.3f}, {p_a_given_b:.3f}).")
            pairs.append(g)

    tree_groups, tree_info = _tree_groups(ff, y, cfg)
    summary["tree"] = tree_info

    # One multiple-comparison correction across everything searched: single conditions, the
    # whole space of two-condition rules (pairs are only tried among conditions that already
    # looked bad, so the ones screened out must still count), and held-out tree rules.
    by_feature = Counter(c[0]["feature"] for c, _ in items)
    pair_space = sum(a * b for a, b in itertools.combinations(by_feature.values(), 2))
    n_pairs_tried = sum(1 for g in tested if g.method == "pair")
    family = tested + tree_groups
    m = len(family) + max(0, pair_space - n_pairs_tried)
    qs = benjamini_hochberg([g.p_value for g in family], m=m)
    for g, q in zip(family, qs):
        g.q_value = q
    summary["hypotheses_tested"] = len(family)
    summary["hypothesis_family_size"] = m
    summary["safeguards"].append(
        f"Benjamini-Hochberg correction (FDR {cfg.alpha:.0%}) over the full search: {m:,} possible rules, "
        f"including two-condition rules that were screened out before testing.")
    summary["safeguards"].append(f"Subgroups smaller than {min_n} records were not tested.")
    if tree_groups:
        summary["safeguards"].append("Decision-tree rules are tested only on held-out rows the tree never saw.")

    candidates = [g for g in singles + pairs + tree_groups if g.n >= min_n and g.k >= MIN_FAILURES_IN_GROUP and g.rate > base]
    for g in candidates:
        lo, hi = wilson_interval(g.k, g.n)
        g.ci = (lo, hi)
        diff = g.rate - base
        significant = g.q_value <= cfg.alpha
        holdout_ok = g.holdout is None or (g.holdout.get("error_rate") is not None and g.holdout["error_rate"] > (g.holdout.get("complement_error_rate") or 0))
        if significant and holdout_ok and lo > base:
            g.reliability = "reliable"
        else:
            g.reliability = "tentative"
            if not significant:
                g.notes.append(f"Not significant after multiple-comparison correction (q = {g.q_value:.2f}). Treat as a lead, not a finding.")
            elif lo <= base:
                g.notes.append("The 95% interval overlaps the overall error rate.")
        if g.n < 2 * min_n:
            g.notes.append(f"Small subgroup ({g.n} records): estimates are uncertain.")
        if any(c.get("value") == MISSING or c["op"] == "is_missing" for c in g.conditions):
            g.notes.append("This rule involves missing values; check whether missingness itself is the signal.")
        excess = g.n * diff  # failures beyond what the baseline rate predicts
        g.severity_score = round(excess, 2)
        if g.reliability != "reliable":
            g.severity = "low"
        elif diff >= 0.25 and g.rate >= 2 * base:
            g.severity = "critical"
        elif diff >= 0.10:
            g.severity = "high"
        else:
            g.severity = "medium"

    # Keep tentative leads only if they are at least nominally interesting.
    candidates = [g for g in candidates if g.reliability == "reliable" or g.p_value < 0.1]
    kept = _select_groups(candidates, y, base, cfg.max_groups)
    summary["safeguards"].append("Groups are selected by sequential covering: each new group must explain failures not already covered by higher-ranked groups, with a preference for simpler rules.")

    if task_type == "classification" and class_balance:
        counts = list(class_balance.values())
        if counts and min(counts) > 0 and max(counts) / min(counts) >= 5:
            summary["warnings"].append(f"Classes are imbalanced (largest/smallest = {max(counts) / min(counts):.1f}). Overall accuracy can hide poor minority-class performance; check per-class recall.")
        summary["safeguards"].append("The ground-truth class is included as a feature so class-specific weaknesses surface as groups.")
    summary["groups_found"] = len(kept)
    summary["reliable_groups"] = sum(g.reliability == "reliable" for g in kept)
    summary["note"] = "Groups describe where failures concentrate. They are associations, not proof of what causes the failures."
    for g in kept:
        g.conditions = [dict(c) for c in g.conditions]
    return DiscoveryResult(kept, base, summary)


__all__ = ["discover_failures", "DiscoveredGroup", "DiscoveryResult", "rule_text"]
