"""Runs an evaluation end to end: metrics -> failure discovery -> clustering -> persistence."""
from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.clustering.engine import cluster_failures
from app.core.errors import ConflictError, ValidationFailed
from app.evaluation.config import EvaluationConfig
from app.evaluation.runner import evaluate_records
from app.evidence.retrieval import CaseIndex, case_text
from app.failure_discovery.engine import discover_failures
from app.failure_discovery.features import build_feature_frame, rule_text
from app.models import Cluster, Dataset, EvaluationMetric, EvaluationRun, FailureExample, FailureGroup, Project
from app.models.base import utcnow
from app.services.activity import log_activity

log = logging.getLogger(__name__)

MAX_STORED_EXAMPLES = 300
MAX_STORED_SUCCESSES = 40


def parse_config(project: Project, raw: dict[str, Any]) -> EvaluationConfig:
    data = dict(raw or {})
    data.setdefault("task_type", project.evaluation_task)
    try:
        return EvaluationConfig.model_validate(data)
    except ValidationError as e:
        raise ValidationFailed("Invalid evaluation configuration.", details=[{"field": ".".join(map(str, err["loc"])), "message": err["msg"]} for err in e.errors()]) from e


def run_evaluation(db: Session, project: Project, dataset: Dataset, raw_config: dict[str, Any]) -> EvaluationRun:
    if dataset.project_id != project.id:
        raise ValidationFailed("The dataset does not belong to this project.")
    if dataset.status != "ready" or not dataset.column_mapping:
        raise ConflictError("Map the dataset's columns before running an evaluation.")
    config = parse_config(project, raw_config)
    mapping = dataset.column_mapping
    run = EvaluationRun(
        project_id=project.id, dataset_id=dataset.id, dataset_version=dataset.version, task_type=config.task_type,
        label=config.label or f"{dataset.name} v{dataset.version}", config=config.to_storage(), status="running",
        analysis_status="pending", total_records=dataset.row_count,
    )
    db.add(run)
    db.flush()
    started = time.perf_counter()
    try:
        outcome, excluded = evaluate_records(dataset.records, mapping, config)
    except ValidationFailed as e:
        run.status, run.error_message = "failed", e.message
        db.commit()
        raise
    run.evaluated_records = len(outcome.cases)
    run.failure_count = outcome.failure_count
    run.error_rate = outcome.error_rate
    run.headline_metric, run.headline_value = outcome.headline_metric, outcome.headline_value
    run.case_results = [c.to_dict() for c in outcome.cases]
    for m in outcome.metrics:
        run.metrics.append(EvaluationMetric(name=m.name, value=None if m.value is None or np.isnan(m.value) else float(m.value), scope=m.scope, scope_key=m.scope_key, extra=m.extra))
    run.status = "completed"

    # ---- Failure discovery and clustering (deterministic analysis) ----
    try:
        _analyse(run, dataset, config, outcome, excluded)
        run.analysis_status = "completed"
    except Exception as e:  # analysis problems must not lose the metrics
        log.exception("Failure analysis failed for run %s", run.id)
        run.analysis_status = "failed"
        run.discovery_summary = {**(run.discovery_summary or {}), "error": f"Failure analysis failed: {e.__class__.__name__}"}
    run.duration_ms = int((time.perf_counter() - started) * 1000)
    run.completed_at = utcnow()
    log_activity(db, "evaluation", f"Evaluation run #{run.id} finished: {run.failure_count} failures in {run.evaluated_records} records, {len(run.failure_groups)} failure groups.", project.id, f"/evaluations/{run.id}")
    db.commit()
    db.refresh(run)
    return run


def _analyse(run: EvaluationRun, dataset: Dataset, config: EvaluationConfig, outcome, excluded: list[int]) -> None:
    records, mapping = dataset.records, dataset.column_mapping
    cases = outcome.cases
    positions = [c.index for c in cases]
    failures = np.array([not c.correct for c in cases])
    extra = None
    if config.task_type == "classification":
        extra = {"expected_label": [c.details.get("expected_label", "") for c in cases]}
    ff = build_feature_frame(records, positions, mapping, derive=config.discovery.derive_text_features, extra_categorical=extra)
    result = discover_failures(ff, failures, config.discovery, task_type=config.task_type,
                               class_balance=outcome.extras.get("class_balance"))
    summary = dict(result.summary)
    summary["excluded_records"] = len(excluded)
    summary["evaluation_extras"] = outcome.extras
    run.discovery_summary = summary

    texts = [case_text(records[i], mapping) for i in positions]
    index = CaseIndex(texts, use_embeddings=config.clustering.use_embeddings)
    for rank, g in enumerate(result.groups, start=1):
        fg = FailureGroup(
            rank=rank, name=g.name, method=g.method, conditions=g.conditions, rule_text=rule_text(g.conditions),
            sample_size=g.n, failures=g.k, error_rate=g.rate, baseline_error_rate=result.baseline_error_rate,
            complement_error_rate=g.complement_rate, difference=g.rate - result.baseline_error_rate,
            lift=(g.rate / result.baseline_error_rate) if result.baseline_error_rate else None,
            ci_low=g.ci[0], ci_high=g.ci[1], p_value=g.p_value, q_value=g.q_value, reliability=g.reliability,
            severity=g.severity, severity_score=g.severity_score, notes=g.notes,
        )
        member_pos = np.where(g.mask)[0].tolist()
        fail_pos = [p for p in member_pos if failures[p]]
        ok_pos = [p for p in member_pos if not failures[p]]
        reps = set(index.representatives(fail_pos, 5))
        for p in fail_pos[:MAX_STORED_EXAMPLES]:
            fg.examples.append(FailureExample(record_index=positions[p], case_id=cases[p].case_id, is_failure=True, representative=p in reps))
        for p in sorted(reps - set(fail_pos[:MAX_STORED_EXAMPLES])):
            fg.examples.append(FailureExample(record_index=positions[p], case_id=cases[p].case_id, is_failure=True, representative=True))
        for p, _ in index.nearest(fail_pos, ok_pos, MAX_STORED_SUCCESSES):
            fg.examples.append(FailureExample(record_index=positions[p], case_id=cases[p].case_id, is_failure=False, representative=False))
        run.failure_groups.append(fg)

    # Clustering of failed cases.
    fail_cases = [c for c in cases if not c.correct]
    inp_col = mapping.get("input_column")
    meta_cols = [m for m in mapping.get("metadata_columns", []) if m in ff.frame.columns and ff.specs.get(m) and ff.specs[m].kind == "categorical"]
    def field_tokens(c) -> list[str]:
        d = c.details or {}
        return ([f"wrongfield_{f}" for f in d.get("wrong_fields", [])] + [f"missingfield_{f}" for f in d.get("missing_fields", [])]
                + [f"extrafield_{f}" for f in d.get("extra_fields", [])])

    use_input = bool(inp_col) and config.task_type != "classification"  # for labels, the confusion itself is the signature
    co = cluster_failures(
        positions=[c.index for c in fail_cases],
        inputs=[(records[c.index].get(inp_col) or "") if use_input else "" for c in fail_cases],
        expected=[records[c.index].get(mapping["expected_column"]) or "" for c in fail_cases],
        actual=[records[c.index].get(mapping["actual_column"]) or "" for c in fail_cases],
        error_types=[c.error_type for c in fail_cases],
        metadata={m: [str(records[c.index].get(m)) for c in fail_cases] for m in meta_cols},
        cfg=config.clustering,
        extra_tokens=[field_tokens(c) for c in fail_cases] if config.task_type == "json" else None,
    )
    run.clustering_summary = co.summary
    total_fail = len(fail_cases) or 1
    for cl in co.clusters:
        run.clusters.append(Cluster(
            cluster_index=cl.index, label=cl.label, method=co.summary.get("method") or "", top_terms=cl.top_terms,
            size=len(cl.members), share_of_failures=len(cl.members) / total_fail, cohesion=cl.cohesion,
            dominant_metadata=cl.dominant_metadata + [{"column": "error_type", "counts": cl.error_types}],
            member_indices=[fail_cases[m].index for m in cl.members],
            representative_indices=[fail_cases[m].index for m in cl.representatives],
        ))
