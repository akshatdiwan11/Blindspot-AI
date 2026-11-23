export type TaskType = "classification" | "text" | "json";
export type ModelCategory = "classification" | "text_generation" | "question_answering" | "structured_extraction" | "llm_application";

export interface Page<T> { items: T[]; total: number; limit: number; offset: number }

export interface Project {
  id: number; name: string; description: string; model_category: ModelCategory; evaluation_task: TaskType;
  llm_investigation_enabled: boolean; is_demo: boolean; created_at: string; updated_at: string;
  dataset_count: number; run_count: number; latest_run_id: number | null; latest_error_rate: number | null;
  latest_headline_value: number | null; failure_group_count: number;
}

export interface ColumnProfile { name: string; dtype: string; missing: number; unique: number; missing_pct?: number; top_values?: { value: string; count: number }[]; avg_length?: number }

export interface ColumnMapping {
  input_column: string | null; expected_column: string; actual_column: string; case_id_column: string | null; metadata_columns: string[];
}

export interface DatasetProfile {
  total_records: number; total_columns: number; missing_values: number; duplicate_records: number; invalid_records: number;
  invalid_rows: { line: number; reason: string }[]; columns: ColumnProfile[]; warnings: string[];
  suggested_mapping: Partial<ColumnMapping> & { metadata_columns: string[] };
  mapping_check?: MappingCheck;
}

export interface MappingCheck {
  valid_records: number; excluded_records: number; missing_actual: number; missing_input: number; duplicate_case_ids: number;
  leaky_metadata_columns: string[]; warnings: string[];
  suggested_task?: { task: TaskType; reason: string };
}

export interface Dataset {
  id: number; project_id: number; name: string; version: number; file_format: string; original_filename: string; size_bytes: number;
  row_count: number; status: "needs_mapping" | "ready"; is_synthetic: boolean; columns: ColumnProfile[]; column_mapping: ColumnMapping | null; created_at: string;
  profile?: DatasetProfile;
}

export interface DatasetPreview {
  dataset: Dataset; profile: DatasetProfile; sample_rows: Record<string, string | number | null>[]; total: number; limit: number; offset: number;
  mapping_check: MappingCheck | null;
}

export interface Metric { name: string; value: number | null; scope: "overall" | "class" | "field"; scope_key: string; extra: Record<string, unknown> }

export interface RunSummary {
  id: number; project_id: number; dataset_id: number; dataset_version: number; task_type: TaskType; label: string; status: string;
  analysis_status: string; total_records: number; evaluated_records: number; failure_count: number; error_rate: number | null;
  headline_metric: string | null; headline_value: number | null; duration_ms: number | null; created_at: string; completed_at: string | null;
  error_message?: string | null;
}

export interface DiscoverySummary {
  records?: number; failures?: number; baseline_error_rate?: number; hypotheses_tested?: number; groups_found?: number; reliable_groups?: number; fdr_alpha?: number; min_group_size?: number;
  features_used?: { name: string; kind: string; origin: string; description: string }[];
  features_excluded?: { feature: string; reason: string }[]; safeguards?: string[]; warnings?: string[]; note?: string; excluded_records?: number;
  tree?: Record<string, unknown>;
  evaluation_extras?: {
    labels?: string[]; confusion_matrix?: number[][]; per_class?: { label: string; precision: number; recall: number; f1: number; support: number; false_positives: number; false_negatives: number }[];
    top_confusions?: { expected: string; predicted: string; count: number }[]; class_balance?: Record<string, number>;
    per_field?: { field: string; accuracy: number | null; total: number; correct: number; missing: number; wrong: number }[];
    error_types?: Record<string, number>; match?: string; threshold?: number; semantic_available?: boolean; criterion?: string;
  };
  error?: string;
}

export interface RunDetail extends RunSummary {
  config: Record<string, any>; metrics: Metric[]; discovery_summary: DiscoverySummary;
  clustering_summary: { method?: string | null; k?: number | null; silhouette?: number | null; skipped?: string | null; note?: string; silhouette_by_k?: Record<string, number>; notes?: string[] };
  dataset_name: string; failure_group_count: number; cluster_count: number;
}

export interface Condition { feature: string; op: "==" | "!=" | "between" | "is_missing"; value?: string; low?: number | null; high?: number | null }

export interface FailureGroup {
  id: number; run_id: number; rank: number; name: string; method: "single" | "pair" | "tree"; conditions: Condition[]; rule_text: string;
  sample_size: number; failures: number; error_rate: number; baseline_error_rate: number; complement_error_rate: number | null;
  difference: number; lift: number | null; ci_low: number; ci_high: number; p_value: number; q_value: number;
  reliability: "reliable" | "tentative"; severity: "critical" | "high" | "medium" | "low"; severity_score: number; notes: string[];
}

export interface CaseRecord {
  index: number; case_id: string; correct: boolean; score: number; error_type: string; input: string | null; expected: string | null;
  actual: string | null; metadata: Record<string, string | null>; details: Record<string, any>; representative: boolean;
}

export interface FailureGroupDetail extends FailureGroup { examples: CaseRecord[]; successes: CaseRecord[] }

export interface Cluster {
  id: number; run_id: number; cluster_index: number; label: string; method: string; top_terms: string[]; size: number;
  share_of_failures: number; cohesion: number | null; dominant_metadata: Record<string, any>[]; representative_indices: number[];
}
export interface ClusterDetail extends Cluster { examples: CaseRecord[] }

export interface RunComparison {
  run_a: RunSummary; run_b: RunSummary; verdict: string; comparable: boolean; notes: string[];
  metrics: { name: string; scope: string; scope_key: string; run_a: number | null; run_b: number | null; delta: number | null; lower_is_better: boolean; direction: string | null }[];
  error_rate_test: { z: number; p_value: number; difference: number; significant: boolean } | null;
  groups: { group_id: number; name: string; run_a_error_rate: number; run_a_rows: number; run_b_error_rate: number | null; run_b_rows: number; delta: number | null }[];
}

export interface EvidenceRef { evidence_id: string; explanation: string }
export interface Hypothesis {
  title: string; explanation: string; confidence: "low" | "medium" | "high"; related_groups: string[]; supporting_evidence: EvidenceRef[];
  counter_evidence: EvidenceRef[]; how_to_test: string; validation_status?: "valid" | "flagged"; invalid_references?: string[]; evidence_level?: string;
}
export interface RecommendedExperiment {
  title: string; target_group: string; hypothesis: string; proposed_change: string; test_procedure: string; measurement: string;
  success_criterion: string; expected_outcome: string; risks: string[]; evidence_ids: string[]; failure_group_id?: number;
}
export interface InvestigationReport {
  sufficient_evidence: boolean; summary: string; main_pattern: { description: string; failure_groups: string[]; evidence_ids: string[] } | null;
  hypotheses: Hypothesis[]; assessment: { severity: string; priority: string; rationale: string } | null; experiments: RecommendedExperiment[]; limitations: string[];
}
export interface Investigation {
  id: number; project_id: number; run_id: number; status: string; message: string | null; provider: string | null; model: string | null;
  focus_group_ids: number[]; report: InvestigationReport | null;
  validation: { issues?: { severity: string; where: string; message: string }[]; invalid_references?: string[]; unverified_numbers?: string[]; flagged_hypotheses?: number; groups?: Record<string, number>; evidence_count?: number; status?: string; schema_errors?: string };
  prompt_tokens: number; completion_tokens: number; cost_usd: number; latency_ms: number | null; attempts: number; created_at: string; evidence_count: number;
}
export interface EvidenceItem { evidence_id: string; kind: string; title: string; record_index: number | null; content: Record<string, any>; record?: CaseRecord | null }

export type ExperimentStatus = "recommended" | "planned" | "running" | "completed" | "abandoned";
export interface ExperimentResult { id: number; metric_name: string; baseline_value: number | null; new_value: number; higher_is_better: boolean; source: string; details: Record<string, any>; notes: string; recorded_at: string }
export interface Experiment {
  id: number; project_id: number; investigation_id: number | null; failure_group_id: number | null; baseline_run_id: number | null; candidate_run_id: number | null;
  title: string; target_failure_group: string; hypothesis: string; proposed_change: string; test_procedure: string; baseline_metric_name: string;
  baseline_metric_value: number | null; success_criterion: string; risks: string[]; evidence_refs: string[]; status: ExperimentStatus; source: string; notes: string;
  created_at: string; updated_at: string; results: ExperimentResult[]; outcome: { state: string; message: string; delta?: number; p_value?: number | null };
}

export interface Overview {
  projects: number; demo_projects: number; datasets: number; evaluation_runs: number; failure_groups: number; reliable_failure_groups: number;
  investigations_completed: number; investigations_total: number; experiments: Record<string, number>; pending_experiments: number;
  latest_run: null | { id: number; project_id: number; project_name: string; label: string; task_type: TaskType; error_rate: number | null; headline_metric: string | null; headline_value: number | null; failure_groups: number; created_at: string; synthetic: boolean; analysis_status: string };
  trend: { run_id: number; label: string; project: string; created_at: string; error_rate: number | null; headline_value: number | null; failure_groups: number; synthetic: boolean }[];
  latest_error_types: Record<string, number>;
  latest_groups: { id: number; name: string; error_rate: number; baseline: number; records: number; reliability: string; severity: string }[];
}
export interface Activity { id: number; kind: string; message: string; link: string | null; project_id: number | null; created_at: string }
export interface SearchResult { type: string; title: string; subtitle: string; link: string }
export interface DemoInfo { key: string; name: string; description: string; task: TaskType; records: number; planted_patterns: string[] }
export interface PublicSettings {
  llm: { configured: boolean; provider: string; model: string; base_url: string; timeout_seconds: number; max_retries: number; price_per_million_tokens: { input: number; output: number }; daily_budget_usd: number; spent_today_usd: number };
  limits: { max_upload_mb: number; max_rows: number }; retention_days: number; analysis: { min_group_size: number; fdr_alpha: number; embeddings_available: boolean }; environment: string;
}
