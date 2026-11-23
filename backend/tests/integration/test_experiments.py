import csv
import io

from app.demo.catalog import DEMOS


def _demo(client):
    return client.post("/api/demo/deadline_extraction").json()


def test_manual_experiment_lifecycle(client):
    info = _demo(client)
    groups = client.get(f"/api/evaluations/{info['run_id']}/failure-groups").json()["items"]
    g = groups[0]
    r = client.post("/api/experiments", json={"project_id": info["project_id"], "title": "Date-role prompt", "failure_group_id": g["id"],
                                              "hypothesis": "h", "proposed_change": "c"})
    assert r.status_code == 201
    exp = r.json()
    assert exp["baseline_metric_value"] == g["error_rate"] and exp["baseline_run_id"] == info["run_id"]
    assert exp["outcome"]["state"] == "not_measured"
    eid = exp["id"]
    assert client.patch(f"/api/experiments/{eid}", json={"status": "running", "notes": "started"}).json()["status"] == "running"
    r = client.patch(f"/api/experiments/{eid}", json={"status": "completed"})
    assert r.status_code == 409 and "measured result" in r.json()["error"]["message"]
    r = client.post(f"/api/experiments/{eid}/results", json={"metric_name": "deadline accuracy", "baseline_value": 0.5, "new_value": 0.8})
    assert r.json()["outcome"]["state"] == "improved"
    assert client.patch(f"/api/experiments/{eid}", json={"status": "completed"}).json()["status"] == "completed"
    assert client.patch(f"/api/experiments/{eid}", json={"status": "recommended"}).status_code == 409
    listed = client.get("/api/experiments", params={"project_id": info["project_id"], "status": "completed"}).json()
    assert listed["total"] == 1


def test_measure_experiment_from_a_new_run(client):
    info = _demo(client)
    groups = client.get(f"/api/evaluations/{info['run_id']}/failure-groups").json()["items"]
    g = groups[0]
    exp = client.post("/api/experiments", json={"project_id": info["project_id"], "title": "fix", "failure_group_id": g["id"]}).json()
    # Simulate a fixed model: correct every failure inside the target group, upload as a new dataset version.
    records, _ = DEMOS["deadline_extraction"].generate()
    failed = {c["case_id"] for c in client.get(f"/api/evaluations/{info['run_id']}/failure-groups/{g['id']}", params={"limit": 300}).json()["examples"]}
    for r in records:
        if r["case_id"] in failed:
            r["actual_output"] = r["expected_output"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(records[0]))
    w.writeheader()
    w.writerows(records)
    ds = client.post("/api/datasets/upload", data={"project_id": info["project_id"], "name": "deadline_extraction_benchmark"},
                     files={"file": ("v2.csv", buf.getvalue().encode(), "text/csv")}).json()
    assert ds["version"] == 2
    client.put(f"/api/datasets/{ds['id']}/mapping", json=DEMOS["deadline_extraction"].mapping)
    run2 = client.post("/api/evaluations/run", json={"dataset_id": ds["id"], "config": {"label": "prompt v2"}}).json()
    r = client.post(f"/api/experiments/{exp['id']}/measure", json={"candidate_run_id": run2["id"]})
    assert r.status_code == 201, r.text
    res = r.json()
    assert res["results"][0]["source"] == "measured_from_runs"
    assert res["results"][0]["new_value"] < res["results"][0]["baseline_value"]
    assert res["outcome"]["state"] == "improved" and res["outcome"]["p_value"] < 0.05
    cmp = client.get("/api/evaluations/compare", params={"run_a": info["run_id"], "run_b": run2["id"]}).json()
    assert "improved" in cmp["verdict"]
    assert cmp["groups"][0]["run_b_error_rate"] < cmp["groups"][0]["run_a_error_rate"]
    assert any("different versions" in n for n in cmp["notes"])
