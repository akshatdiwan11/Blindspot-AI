import type {
  Activity, ClusterDetail, Cluster, ColumnMapping, Dataset, DatasetPreview, DemoInfo, EvidenceItem, Experiment, ExperimentStatus,
  FailureGroup, FailureGroupDetail, Investigation, Overview, Page, Project, PublicSettings, RunComparison, RunDetail, RunSummary, SearchResult, CaseRecord,
} from "../types/api";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";

export class ApiError extends Error {
  status: number;
  details: unknown;
  constructor(status: number, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: init.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Cannot reach the Blindspot AI server. Check that the backend is running.");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    const err = data?.error;
    let message = err?.message ?? `Request failed (${res.status})`;
    if (Array.isArray(err?.details) && err.details.length && err.details[0]?.message) {
      message += " " + err.details.map((d: any) => (d.field ? `${d.field}: ${d.message}` : d.message)).join("; ");
    }
    throw new ApiError(res.status, message, err?.details);
  }
  return data as T;
}

const qs = (params: Record<string, unknown>) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, String(v)); });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => request<{ status: string }>("/health"),
  settings: () => request<PublicSettings>("/settings"),
  overview: (projectId?: number) => request<Overview>(`/overview${qs({ project_id: projectId })}`),
  activity: (limit = 20, projectId?: number) => request<Activity[]>(`/activity${qs({ limit, project_id: projectId })}`),
  search: (q: string) => request<SearchResult[]>(`/search${qs({ q })}`),

  projects: (q?: string) => request<Page<Project>>(`/projects${qs({ q, limit: 200 })}`),
  project: (id: number) => request<Project>(`/projects/${id}`),
  createProject: (body: { name: string; description: string; model_category: string; evaluation_task?: string; llm_investigation_enabled: boolean }) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),
  updateProject: (id: number, body: Partial<Pick<Project, "name" | "description" | "llm_investigation_enabled" | "evaluation_task">>) =>
    request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteProject: (id: number) => request<void>(`/projects/${id}`, { method: "DELETE" }),

  datasets: (params: { project_id?: number; q?: string } = {}) => request<Page<Dataset>>(`/datasets${qs({ ...params, limit: 200 })}`),
  dataset: (id: number) => request<Dataset>(`/datasets/${id}`),
  preview: (id: number, params: { limit?: number; offset?: number; q?: string; column?: string; value?: string } = {}) =>
    request<DatasetPreview>(`/datasets/${id}/preview${qs(params)}`),
  upload: (projectId: number, file: File, name?: string) => {
    const fd = new FormData();
    fd.append("project_id", String(projectId));
    fd.append("file", file);
    if (name) fd.append("name", name);
    return request<Dataset>("/datasets/upload", { method: "POST", body: fd });
  },
  setMapping: (id: number, mapping: ColumnMapping) => request<DatasetPreview>(`/datasets/${id}/mapping`, { method: "PUT", body: JSON.stringify(mapping) }),
  deleteDataset: (id: number) => request<void>(`/datasets/${id}`, { method: "DELETE" }),

  runEvaluation: (datasetId: number, config: Record<string, unknown>) =>
    request<RunDetail>("/evaluations/run", { method: "POST", body: JSON.stringify({ dataset_id: datasetId, config }) }),
  runs: (projectId: number) => request<Page<RunSummary>>(`/projects/${projectId}/evaluations?limit=200`),
  allRuns: () => request<Page<RunSummary>>(`/evaluations?limit=200`),
  run: (id: number) => request<RunDetail>(`/evaluations/${id}`),
  deleteRun: (id: number) => request<void>(`/evaluations/${id}`, { method: "DELETE" }),
  cases: (runId: number, params: { outcome?: "failed" | "passed"; error_type?: string; q?: string; limit?: number; offset?: number }) =>
    request<Page<CaseRecord>>(`/evaluations/${runId}/cases${qs(params)}`),
  compare: (a: number, b: number) => request<RunComparison>(`/evaluations/compare${qs({ run_a: a, run_b: b })}`),
  failureGroups: (runId: number) => request<Page<FailureGroup>>(`/evaluations/${runId}/failure-groups?limit=200`),
  failureGroup: (runId: number, groupId: number, limit = 40) => request<FailureGroupDetail>(`/evaluations/${runId}/failure-groups/${groupId}?limit=${limit}`),
  clusters: (runId: number) => request<Cluster[]>(`/evaluations/${runId}/clusters`),
  cluster: (runId: number, clusterId: number) => request<ClusterDetail>(`/evaluations/${runId}/clusters/${clusterId}?limit=30`),

  investigate: (runId: number, failureGroupIds?: number[]) =>
    request<Investigation>("/investigations/run", { method: "POST", body: JSON.stringify({ run_id: runId, failure_group_ids: failureGroupIds?.length ? failureGroupIds : null }) }),
  investigations: (params: { project_id?: number; run_id?: number }) => request<Page<Investigation>>(`/investigations${qs({ ...params, limit: 100 })}`),
  investigation: (id: number) => request<Investigation>(`/investigations/${id}`),
  evidence: (id: number) => request<EvidenceItem[]>(`/investigations/${id}/evidence`),
  evidenceItem: (id: number, key: string) => request<EvidenceItem>(`/investigations/${id}/evidence/${key}`),

  experiments: (params: { project_id?: number; status?: ExperimentStatus }) => request<Page<Experiment>>(`/experiments${qs({ ...params, limit: 200 })}`),
  createExperiment: (body: Record<string, unknown>) => request<Experiment>("/experiments", { method: "POST", body: JSON.stringify(body) }),
  updateExperiment: (id: number, body: Record<string, unknown>) => request<Experiment>(`/experiments/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  addResult: (id: number, body: Record<string, unknown>) => request<Experiment>(`/experiments/${id}/results`, { method: "POST", body: JSON.stringify(body) }),
  measure: (id: number, candidateRunId: number) => request<Experiment>(`/experiments/${id}/measure`, { method: "POST", body: JSON.stringify({ candidate_run_id: candidateRunId }) }),
  deleteExperiment: (id: number) => request<void>(`/experiments/${id}`, { method: "DELETE" }),

  demos: () => request<DemoInfo[]>("/demo"),
  loadDemo: (key: string) => request<{ project_id: number; run_id: number; dataset_id: number }>(`/demo/${key}`, { method: "POST" }),

  reportUrl: (runId: number, format: "json" | "markdown" | "csv" | "pdf", download = true, investigationId?: number) =>
    `${BASE}/reports/${runId}${qs({ format, download: download ? "true" : undefined, investigation_id: investigationId })}`,
};
