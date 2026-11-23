# API reference

All endpoints are under `/api`. Interactive documentation (OpenAPI / Swagger) is served at
`/api/docs` by the running backend.

Errors always have the same shape:

```json
{ "error": { "code": "validation_failed", "message": "Readable explanation.", "details": [ { "field": "...", "message": "..." } ] } }
```

Codes: `validation_failed` (422), `not_found` (404), `conflict` (409), `payload_too_large` (413),
`internal_error` (500). List endpoints return `{ "items": [...], "total", "limit", "offset" }`.

## Projects

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects` | Create a project (`name`, `description`, `model_category`, `evaluation_task`, `llm_investigation_enabled`) |
| GET | `/projects` | List projects (`q` to search) |
| GET | `/projects/{id}` | Get one project |
| PATCH | `/projects/{id}` | Rename, describe, change task type, turn AI investigation on or off |
| DELETE | `/projects/{id}` | Delete the project and everything in it |
| GET | `/projects/{id}/evaluations` | Evaluation runs of a project |

## Datasets

| Method | Path | Purpose |
|---|---|---|
| POST | `/datasets/upload` | Multipart upload: `project_id`, `file` (CSV, JSON or JSONL), optional `name`. Re-uploading under the same name creates a new version |
| GET | `/datasets` | List (`project_id` to filter) |
| GET | `/datasets/{id}` | Dataset with its profile (column types, missing values, duplicates, invalid rows, suggested mapping) |
| GET | `/datasets/{id}/preview` | Rows in file column order; `limit`, `offset`, `q` (text filter), `column` + `value` (exact filter) |
| PUT | `/datasets/{id}/mapping` | Set `input_column`, `expected_column`, `actual_column`, `case_id_column`, `metadata_columns`. Returns row checks and a suggested task type |
| DELETE | `/datasets/{id}` | Delete a dataset version |

## Evaluations and analysis

| Method | Path | Purpose |
|---|---|---|
| POST | `/evaluations/run` | `{ "dataset_id", "config": { "task_type", "label", "text", "classification", "json", "discovery", "clustering" } }`. Scores every case, then runs discovery and clustering |
| GET | `/evaluations` | All runs |
| GET | `/evaluations/{id}` | Run with metrics, discovery summary and clustering summary |
| GET | `/evaluations/compare?run_a=&run_b=` | Metric deltas, per-segment error rates and a two-proportion test between two runs |
| GET | `/evaluations/{id}/cases` | Per-case results; filter by `outcome` (`failed` or `passed`), `error_type`, `q` (text search) |
| GET | `/evaluations/{id}/cases/{index}` | One case with its full record |
| GET | `/evaluations/{id}/failure-groups` | Failure groups with rule, sample size, error rate, interval, p and q values, reliability, severity |
| GET | `/evaluations/{id}/failure-groups/{group_id}` | One group with example failures and correct cases |
| GET | `/evaluations/{id}/clusters` | Failure clusters |
| GET | `/evaluations/{id}/clusters/{cluster_id}` | One cluster with its cases |
| DELETE | `/evaluations/{id}` | Delete a run |

## Investigations

| Method | Path | Purpose |
|---|---|---|
| POST | `/investigations/run` | `{ "run_id", "failure_group_ids"?: [..] (up to 4), "model"?: "..." }`. Builds the evidence package and, when enabled and configured, asks the LLM |
| GET | `/investigations` | List (`project_id`, `run_id` to filter) |
| GET | `/investigations/{id}` | Status, validated report, hypotheses, validation warnings, tokens, cost, latency |
| GET | `/investigations/{id}/evidence` | The evidence package |
| GET | `/investigations/{id}/evidence/{EVIDENCE_###}` | One evidence item with the full source record |
| DELETE | `/investigations/{id}` | Delete |

## Experiments

| Method | Path | Purpose |
|---|---|---|
| POST | `/experiments` | Create (usually from a hypothesis): title, target group, proposed change, success criterion |
| GET | `/experiments` | List (`project_id`, `status`) |
| GET / PATCH / DELETE | `/experiments/{id}` | Read, move between statuses, edit, delete |
| POST | `/experiments/{id}/results` | Record a manual result (metric, baseline, new value) |
| POST | `/experiments/{id}/measure` | `{ "candidate_run_id" }`: re-apply the group rule to a newer run and test the change |

## Reports and other endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/reports/{run_id}?format=pdf\|markdown\|json\|csv` | Export; add `investigation_id` to include an investigation and `download=true` for a file |
| GET | `/overview` | Dashboard numbers (`project_id` to scope) |
| GET | `/activity` | Activity log |
| GET | `/search?q=` | Search projects, datasets, runs and failure groups |
| GET | `/settings` | Public settings (limits, AI provider and model, whether a key is configured; never the key) |
| GET | `/demo`, POST `/demo/{key}` | List and load the synthetic demos |
| GET | `/health` | Health check |
