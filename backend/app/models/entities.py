"""Relational model.

Project ─┬─ Dataset (versioned) ── EvaluationRun ─┬─ EvaluationMetric
         │                                        ├─ FailureGroup ── FailureExample
         │                                        ├─ Cluster
         │                                        └─ Investigation ─┬─ InvestigationHypothesis
         │                                                          └─ EvidenceItem
         ├─ Experiment ── ExperimentResult
         └─ ActivityEvent

Deleting a project deletes everything below it (ON DELETE CASCADE in the database and
cascade="all, delete-orphan" in the ORM). API keys are never stored here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import JSONType, TimestampMixin, utcnow

MODEL_CATEGORIES = ("classification", "text_generation", "question_answering", "structured_extraction", "llm_application")
TASK_TYPES = ("classification", "text", "json")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(f"model_category IN {MODEL_CATEGORIES}", name="ck_projects_model_category"),
        CheckConstraint(f"evaluation_task IN {TASK_TYPES}", name="ck_projects_evaluation_task"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    model_category: Mapped[str] = mapped_column(String(40), nullable=False)
    evaluation_task: Mapped[str] = mapped_column(String(20), nullable=False)
    llm_investigation_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    datasets: Mapped[list[Dataset]] = relationship(back_populates="project", cascade="all, delete-orphan", passive_deletes=True)
    runs: Mapped[list[EvaluationRun]] = relationship(back_populates="project", cascade="all, delete-orphan", passive_deletes=True)
    experiments: Mapped[list[Experiment]] = relationship(back_populates="project", cascade="all, delete-orphan", passive_deletes=True)
    investigations: Mapped[list[Investigation]] = relationship(back_populates="project", cascade="all, delete-orphan", passive_deletes=True)
    activity: Mapped[list[ActivityEvent]] = relationship(back_populates="project", cascade="all, delete-orphan", passive_deletes=True)


class Dataset(TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("project_id", "name", "version", name="uq_dataset_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str | None] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    columns: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    profile: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    column_mapping: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(20), default="needs_mapping", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Parsed rows are kept in the database so results survive restarts on hosts with ephemeral disks.
    records: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)

    project: Mapped[Project] = relationship(back_populates="datasets")
    runs: Mapped[list[EvaluationRun]] = relationship(back_populates="dataset", cascade="all, delete-orphan", passive_deletes=True)


class EvaluationRun(TimestampMixin, Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=False)
    dataset_version: Mapped[int] = mapped_column(Integer, nullable=False)
    task_type: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    analysis_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evaluated_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_rate: Mapped[float | None] = mapped_column(Float)
    headline_metric: Mapped[str | None] = mapped_column(String(60))
    headline_value: Mapped[float | None] = mapped_column(Float)
    case_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    discovery_summary: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    clustering_summary: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="runs")
    dataset: Mapped[Dataset] = relationship(back_populates="runs")
    metrics: Mapped[list[EvaluationMetric]] = relationship(back_populates="run", cascade="all, delete-orphan", passive_deletes=True)
    failure_groups: Mapped[list[FailureGroup]] = relationship(back_populates="run", cascade="all, delete-orphan", passive_deletes=True, order_by="FailureGroup.rank")
    clusters: Mapped[list[Cluster]] = relationship(back_populates="run", cascade="all, delete-orphan", passive_deletes=True, order_by="Cluster.cluster_index")
    investigations: Mapped[list[Investigation]] = relationship(back_populates="run", cascade="all, delete-orphan", passive_deletes=True)


class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"
    __table_args__ = (Index("ix_metric_run_scope", "run_id", "scope", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    scope: Mapped[str] = mapped_column(String(20), default="overall", nullable=False)  # overall | class | field
    scope_key: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    run: Mapped[EvaluationRun] = relationship(back_populates="metrics")


class FailureGroup(Base):
    __tablename__ = "failure_groups"
    __table_args__ = (Index("ix_failure_group_run_rank", "run_id", "rank"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)  # single | pair | tree
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, nullable=False)
    error_rate: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_error_rate: Mapped[float] = mapped_column(Float, nullable=False)
    complement_error_rate: Mapped[float | None] = mapped_column(Float)
    difference: Mapped[float] = mapped_column(Float, nullable=False)
    lift: Mapped[float | None] = mapped_column(Float)
    ci_low: Mapped[float] = mapped_column(Float, nullable=False)
    ci_high: Mapped[float] = mapped_column(Float, nullable=False)
    p_value: Mapped[float] = mapped_column(Float, nullable=False)
    q_value: Mapped[float] = mapped_column(Float, nullable=False)
    reliability: Mapped[str] = mapped_column(String(20), nullable=False)  # reliable | tentative
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # critical | high | medium | low
    severity_score: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)

    run: Mapped[EvaluationRun] = relationship(back_populates="failure_groups")
    examples: Mapped[list[FailureExample]] = relationship(back_populates="group", cascade="all, delete-orphan", passive_deletes=True)


class FailureExample(Base):
    __tablename__ = "failure_examples"
    __table_args__ = (Index("ix_failure_example_group", "group_id", "representative"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("failure_groups.id", ondelete="CASCADE"), nullable=False)
    record_index: Mapped[int] = mapped_column(Integer, nullable=False)
    case_id: Mapped[str] = mapped_column(String(200), nullable=False)
    is_failure: Mapped[bool] = mapped_column(Boolean, nullable=False)
    representative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    group: Mapped[FailureGroup] = relationship(back_populates="examples")


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    cluster_index: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    top_terms: Mapped[list[str]] = mapped_column(JSONType, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    share_of_failures: Mapped[float] = mapped_column(Float, nullable=False)
    cohesion: Mapped[float | None] = mapped_column(Float)
    dominant_metadata: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    member_indices: Mapped[list[int]] = mapped_column(JSONType, nullable=False)
    representative_indices: Mapped[list[int]] = mapped_column(JSONType, nullable=False)

    run: Mapped[EvaluationRun] = relationship(back_populates="clusters")


class Investigation(TimestampMixin, Base):
    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(100))
    focus_group_ids: Mapped[list[int]] = mapped_column(JSONType, default=list, nullable=False)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    validation: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project: Mapped[Project] = relationship(back_populates="investigations")
    run: Mapped[EvaluationRun] = relationship(back_populates="investigations")
    hypotheses: Mapped[list[InvestigationHypothesis]] = relationship(back_populates="investigation", cascade="all, delete-orphan", passive_deletes=True, order_by="InvestigationHypothesis.rank")
    evidence: Mapped[list[EvidenceItem]] = relationship(back_populates="investigation", cascade="all, delete-orphan", passive_deletes=True, order_by="EvidenceItem.evidence_key")


class InvestigationHypothesis(Base):
    __tablename__ = "investigation_hypotheses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), index=True, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_level: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    supporting_evidence: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    counter_evidence: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    invalid_references: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False)  # valid | flagged

    investigation: Mapped[Investigation] = relationship(back_populates="hypotheses")


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (UniqueConstraint("investigation_id", "evidence_key", name="uq_evidence_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), index=True, nullable=False)
    evidence_key: Mapped[str] = mapped_column(String(20), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    record_index: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)

    investigation: Mapped[Investigation] = relationship(back_populates="evidence")


class Experiment(TimestampMixin, Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint("status IN ('recommended','planned','running','completed','abandoned')", name="ck_experiment_status"),
        Index("ix_experiment_project_status", "project_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    investigation_id: Mapped[int | None] = mapped_column(ForeignKey("investigations.id", ondelete="SET NULL"))
    failure_group_id: Mapped[int | None] = mapped_column(ForeignKey("failure_groups.id", ondelete="SET NULL"))
    baseline_run_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="SET NULL"))
    candidate_run_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    target_failure_group: Mapped[str] = mapped_column(Text, default="", nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    proposed_change: Mapped[str] = mapped_column(Text, default="", nullable=False)
    test_procedure: Mapped[str] = mapped_column(Text, default="", nullable=False)
    baseline_metric_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    baseline_metric_value: Mapped[float | None] = mapped_column(Float)
    success_criterion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    risks: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="planned", nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)  # manual | investigator
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="experiments")
    results: Mapped[list[ExperimentResult]] = relationship(back_populates="experiment", cascade="all, delete-orphan", passive_deletes=True, order_by="ExperimentResult.recorded_at")


class ExperimentResult(Base):
    __tablename__ = "experiment_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), index=True, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    baseline_value: Mapped[float | None] = mapped_column(Float)
    new_value: Mapped[float] = mapped_column(Float, nullable=False)
    higher_is_better: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)  # manual | measured_from_runs
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    experiment: Mapped[Experiment] = relationship(back_populates="results")


class ActivityEvent(TimestampMixin, Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(300))

    project: Mapped[Project | None] = relationship(back_populates="activity")
