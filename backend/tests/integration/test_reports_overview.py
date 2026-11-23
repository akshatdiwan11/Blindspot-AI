import json


def test_reports_in_all_formats(client):
    info = client.post("/api/demo/email_triage").json()
    rid = info["run_id"]
    r = client.get(f"/api/reports/{rid}")
    assert r.status_code == 200
    rep = r.json()
    assert rep["run_id"] == rid and rep["run_created_at"] and rep["generated_at"]
    assert rep["dataset"]["synthetic"] is True and rep["failure_groups"]
    md = client.get(f"/api/reports/{rid}", params={"format": "markdown"}).text
    assert f"Evaluation run:** #{rid}" in md and "SYNTHETIC" in md and "hypotheses, not facts" in md
    csv_text = client.get(f"/api/reports/{rid}", params={"format": "csv", "download": True})
    assert csv_text.headers["content-disposition"].startswith("attachment")
    lines = csv_text.text.strip().splitlines()
    assert lines[0].startswith("run_id,case_id") and len(lines) == 701
    pdf = client.get(f"/api/reports/{rid}", params={"format": "pdf"})
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content[:4] == b"%PDF"
    assert client.get(f"/api/reports/{rid}", params={"format": "docx"}).status_code == 422


def test_overview_activity_search_settings(client):
    empty = client.get("/api/overview").json()
    assert empty["projects"] == 0 and empty["latest_run"] is None
    info = client.post("/api/demo/deadline_extraction").json()
    ov = client.get("/api/overview").json()
    assert ov["projects"] == 1 and ov["evaluation_runs"] == 1 and ov["failure_groups"] >= 4
    assert ov["latest_run"]["synthetic"] is True and ov["trend"][0]["run_id"] == info["run_id"]
    acts = client.get("/api/activity").json()
    assert any("Evaluation run" in a["message"] for a in acts)
    res = client.get("/api/search", params={"q": "deadline"}).json()
    assert {r["type"] for r in res} >= {"project", "dataset"}
    s = client.get("/api/settings").json()
    assert s["llm"]["configured"] is False
    assert "sk-" not in json.dumps(s) and "api_key" not in json.dumps(s)
