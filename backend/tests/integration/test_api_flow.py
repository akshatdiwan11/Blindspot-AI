import json


def _project(client, **kw):
    body = {"name": "Extraction model", "description": "test", "model_category": "structured_extraction", "evaluation_task": "text", **kw}
    r = client.post("/api/projects", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_full_flow_upload_map_evaluate(client, sample_csv):
    p = _project(client)
    r = client.post("/api/datasets/upload", data={"project_id": p["id"]}, files={"file": ("sample.csv", sample_csv, "text/csv")})
    assert r.status_code == 201, r.text
    ds = r.json()
    assert ds["row_count"] == 4 and ds["status"] == "needs_mapping"
    assert ds["profile"]["suggested_mapping"]["expected_column"] == "expected_output"

    # Running before mapping is a clear 409, not a crash.
    r = client.post("/api/evaluations/run", json={"dataset_id": ds["id"]})
    assert r.status_code == 409 and "Map the dataset" in r.json()["error"]["message"]

    mapping = {"input_column": "input_text", "expected_column": "expected_output", "actual_column": "actual_output",
               "case_id_column": "case_id", "metadata_columns": ["language", "document_type", "source"]}
    r = client.put(f"/api/datasets/{ds['id']}/mapping", json=mapping)
    assert r.status_code == 200, r.text
    assert r.json()["mapping_check"]["valid_records"] == 4

    r = client.get(f"/api/datasets/{ds['id']}/preview", params={"limit": 2, "q": "deadline"})
    assert r.status_code == 200 and r.json()["total"] == 1

    r = client.post("/api/evaluations/run", json={"dataset_id": ds["id"], "config": {"task_type": "text"}})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["evaluated_records"] == 4 and run["failure_count"] == 3
    names = {m["name"] for m in run["metrics"]}
    assert {"exact_match", "normalized_exact_match", "token_precision", "token_recall", "token_f1"} <= names
    # Too few rows: discovery explains rather than inventing groups.
    assert run["discovery_summary"]["warnings"]
    assert client.get(f"/api/evaluations/{run['id']}/failure-groups").json()["total"] == 0
    assert run["clustering_summary"]["skipped"]

    cases = client.get(f"/api/evaluations/{run['id']}/cases", params={"outcome": "failed"}).json()
    assert cases["total"] == 3 and cases["items"][0]["expected"] == "15 December"

    runs = client.get(f"/api/projects/{p['id']}/evaluations").json()
    assert runs["total"] == 1
    proj = client.get(f"/api/projects/{p['id']}").json()
    assert proj["run_count"] == 1 and proj["latest_run_id"] == run["id"]


def test_validation_errors_are_meaningful(client, sample_csv):
    r = client.post("/api/projects", json={"name": "  ", "model_category": "classification"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"
    r = client.post("/api/projects", json={"name": "x", "model_category": "nope"})
    assert r.status_code == 422
    p = _project(client)
    r = client.post("/api/datasets/upload", data={"project_id": p["id"]}, files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 422 and "Unsupported file type" in r.json()["error"]["message"]
    r = client.post("/api/datasets/upload", data={"project_id": 999}, files={"file": ("x.csv", sample_csv, "text/csv")})
    assert r.status_code == 404
    ds = client.post("/api/datasets/upload", data={"project_id": p["id"]}, files={"file": ("x.csv", sample_csv, "text/csv")}).json()
    r = client.put(f"/api/datasets/{ds['id']}/mapping", json={"expected_column": "nope", "actual_column": "actual_output"})
    assert r.status_code == 422 and "Unknown column" in r.json()["error"]["message"]
    r = client.put(f"/api/datasets/{ds['id']}/mapping", json={"expected_column": "actual_output", "actual_column": "actual_output"})
    assert r.status_code == 422
    assert client.get("/api/evaluations/12345").status_code == 404
    r = client.post("/api/evaluations/run", json={"dataset_id": ds["id"], "config": {"task_type": "regression"}})
    assert r.status_code in (409, 422)


def test_upload_size_limit(client, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0.0001)
    p = _project(client)
    big = b"a,b\n" + b"1,2\n" * 200
    r = client.post("/api/datasets/upload", data={"project_id": p["id"]}, files={"file": ("x.csv", big, "text/csv")})
    assert r.status_code == 413


def test_dataset_versions_and_delete_cascade(client, sample_csv):
    p = _project(client)
    up = lambda: client.post("/api/datasets/upload", data={"project_id": p["id"], "name": "evalset"}, files={"file": ("x.csv", sample_csv, "text/csv")}).json()  # noqa: E731
    a, b = up(), up()
    assert (a["version"], b["version"]) == (1, 2)
    listed = client.get("/api/datasets", params={"project_id": p["id"]}).json()
    assert listed["total"] == 2
    assert client.delete(f"/api/projects/{p['id']}").status_code == 204
    assert client.get(f"/api/datasets/{a['id']}").status_code == 404
    assert client.get(f"/api/projects/{p['id']}").status_code == 404


def test_json_upload_and_structured_evaluation(client):
    rows = [{"id": i, "expected": json.dumps({"a": i, "b": "x"}), "actual": json.dumps({"a": i, "b": "x" if i % 3 else "y"})} for i in range(30)]
    p = _project(client, evaluation_task="json")
    ds = client.post("/api/datasets/upload", data={"project_id": p["id"]}, files={"file": ("rows.json", json.dumps(rows).encode(), "application/json")}).json()
    client.put(f"/api/datasets/{ds['id']}/mapping", json={"expected_column": "expected", "actual_column": "actual", "case_id_column": "id"})
    run = client.post("/api/evaluations/run", json={"dataset_id": ds["id"]}).json()
    m = {x["name"]: x["value"] for x in run["metrics"] if x["scope"] == "overall"}
    assert m["exact_json_match"] == 20 / 30
    assert m["field_accuracy"] == 50 / 60
