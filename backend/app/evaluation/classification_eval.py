"""Classification evaluation with scikit-learn (deterministic)."""
from __future__ import annotations

from collections import Counter

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from app.evaluation.config import ClassificationEvalConfig
from app.evaluation.types import CaseResult, EvaluationOutcome, Metric

MAX_MATRIX_LABELS = 25
MISSING_LABEL = "(no prediction)"


def _canon(label: str | None, case_sensitive: bool) -> str:
    if label is None or not str(label).strip():
        return MISSING_LABEL
    s = " ".join(str(label).split())
    return s if case_sensitive else s.lower()


def evaluate_classification(indices: list[int], case_ids: list[str], expected: list[str], actual: list[str | None], cfg: ClassificationEvalConfig) -> EvaluationOutcome:
    y_true = [_canon(e, cfg.case_sensitive) for e in expected]
    y_pred = [_canon(a, cfg.case_sensitive) for a in actual]
    # Display names: keep the first original spelling seen for each canonical label.
    display: dict[str, str] = {}
    for raw, can in [*zip(expected, y_true), *zip(actual, y_pred)]:
        display.setdefault(can, " ".join(str(raw).split()) if raw else MISSING_LABEL)

    true_labels = sorted(set(y_true), key=lambda l: (-y_true.count(l), l))
    all_labels = true_labels + sorted(set(y_pred) - set(true_labels))

    cases = []
    for k, idx in enumerate(indices):
        ok = y_true[k] == y_pred[k]
        etype = "" if ok else ("empty_output" if y_pred[k] == MISSING_LABEL else ("unknown_label" if y_pred[k] not in true_labels else "misclassified"))
        cases.append(CaseResult(idx, case_ids[k], ok, float(ok), etype, {"expected_label": display[y_true[k]], "predicted_label": display[y_pred[k]]}))

    n = len(cases)
    acc = float(accuracy_score(y_true, y_pred)) if n else None
    metrics = [Metric("accuracy", acc), Metric("failure_rate", 1 - acc if acc is not None else None)]
    for avg in ("macro", "weighted"):
        p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, labels=true_labels, average=avg, zero_division=0)
        metrics += [Metric(f"precision_{avg}", float(p)), Metric(f"recall_{avg}", float(r)), Metric(f"f1_{avg}", float(f))]
    # Headline precision / recall / F1 cards use macro averages (robust to class imbalance).
    metrics += [Metric("precision", next(m.value for m in metrics if m.name == "precision_macro")),
                Metric("recall", next(m.value for m in metrics if m.name == "recall_macro")),
                Metric("f1", next(m.value for m in metrics if m.name == "f1_macro"))]

    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=true_labels, average=None, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=all_labels)
    per_class = []
    for i, lab in enumerate(true_labels):
        j = all_labels.index(lab)
        tp = int(cm[j, j])
        fp = int(cm[:, j].sum() - tp)
        fn = int(cm[j, :].sum() - tp)
        row = {"label": display[lab], "precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i]),
               "true_positives": tp, "false_positives": fp, "false_negatives": fn}
        per_class.append(row)
        for name in ("precision", "recall", "f1"):
            metrics.append(Metric(name, row[name], scope="class", scope_key=display[lab], extra={"support": row["support"]}))
        metrics.append(Metric("false_positives", fp, scope="class", scope_key=display[lab]))
        metrics.append(Metric("false_negatives", fn, scope="class", scope_key=display[lab]))

    if cfg.positive_label:
        pos = _canon(cfg.positive_label, cfg.case_sensitive)
        if pos in true_labels:
            bp, br, bf, _ = precision_recall_fscore_support(y_true, y_pred, labels=[pos], average=None, zero_division=0)
            metrics += [Metric("binary_precision", float(bp[0]), extra={"positive_label": cfg.positive_label}),
                        Metric("binary_recall", float(br[0]), extra={"positive_label": cfg.positive_label}),
                        Metric("binary_f1", float(bf[0]), extra={"positive_label": cfg.positive_label})]

    # Confusion matrix, truncated to the most frequent labels for display.
    shown = all_labels[:MAX_MATRIX_LABELS]
    matrix = cm[: len(shown), : len(shown)].tolist() if len(all_labels) <= MAX_MATRIX_LABELS else _collapse(cm, all_labels, shown)
    confusions = Counter((display[t], display[p_]) for t, p_ in zip(y_true, y_pred) if t != p_)
    extras = {
        "labels": [display[l] for l in shown] + (["(other)"] if len(all_labels) > MAX_MATRIX_LABELS else []),
        "confusion_matrix": matrix,
        "per_class": per_class,
        "top_confusions": [{"expected": a, "predicted": b, "count": c} for (a, b), c in confusions.most_common(10)],
        "class_balance": {display[l]: y_true.count(l) for l in true_labels},
        "imbalance_ratio": (max(Counter(y_true).values()) / min(Counter(y_true).values())) if n else None,
    }
    return EvaluationOutcome("classification", cases, metrics, "accuracy", acc, extras)


def _collapse(cm: np.ndarray, all_labels: list[str], shown: list[str]) -> list[list[int]]:
    k = len(shown)
    out = np.zeros((k + 1, k + 1), dtype=int)
    for i in range(len(all_labels)):
        for j in range(len(all_labels)):
            out[min(i, k), min(j, k)] += cm[i, j]
    return out.tolist()
