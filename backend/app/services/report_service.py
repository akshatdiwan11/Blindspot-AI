"""Report exports for an evaluation run: JSON, Markdown, CSV (per-case results) and PDF."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.experiments.service import outcome
from app.failure_discovery.features import apply_conditions, build_feature_frame
from app.investigator.service import investigation_payload
from app.models import EvaluationRun, Experiment, Investigation

DISCLAIMER = ("Metrics, failure groups and clusters are computed deterministically by the Blindspot AI engine. "
              "Failure groups are statistical associations, not proven causes. Root-cause statements from the AI investigator "
              "are untested hypotheses that cite evidence IDs; they become findings only when an experiment measures the effect.")


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def _num(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.4f}"


def build_report(db: Session, run: EvaluationRun, investigation_id: int | None = None) -> dict[str, Any]:
    inv = None
    if investigation_id is not None:
        inv = db.get(Investigation, investigation_id)
        if inv is not None and inv.run_id != run.id:
            inv = None
    if inv is None:
        inv = db.scalars(select(Investigation).where(Investigation.run_id == run.id).order_by(Investigation.created_at.desc()).limit(1)).first()
    experiments = db.scalars(select(Experiment).where(Experiment.baseline_run_id == run.id).order_by(Experiment.created_at)).all()
    ds = run.dataset
    return {
        "report_type": "blindspot_investigation_report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run.id,
        "run_created_at": run.created_at.isoformat(),
        "run_label": run.label,
        "project": {"id": run.project.id, "name": run.project.name, "model_category": run.project.model_category, "demo": run.project.is_demo},
        "dataset": {"id": ds.id, "name": ds.name, "version": ds.version, "records": ds.row_count, "synthetic": ds.is_synthetic, "sha256": ds.sha256},
        "configuration": run.config,
        "summary": {"task_type": run.task_type, "evaluated_records": run.evaluated_records, "failures": run.failure_count,
                    "error_rate": run.error_rate, "headline_metric": run.headline_metric, "headline_value": run.headline_value},
        "metrics": [{"name": m.name, "scope": m.scope, "scope_key": m.scope_key, "value": m.value} for m in run.metrics],
        "failure_groups": [{"rank": g.rank, "name": g.name, "rule": g.rule_text, "method": g.method, "records": g.sample_size, "failures": g.failures,
                            "error_rate": g.error_rate, "baseline_error_rate": g.baseline_error_rate, "difference": g.difference,
                            "ci95": [g.ci_low, g.ci_high], "p_value": g.p_value, "q_value": g.q_value, "reliability": g.reliability,
                            "severity": g.severity, "excess_failures": g.severity_score, "notes": g.notes} for g in run.failure_groups],
        "clusters": [{"label": c.label, "size": c.size, "share_of_failures": c.share_of_failures, "top_terms": c.top_terms, "method": c.method}
                     for c in run.clusters],
        "analysis_notes": {"discovery": {k: run.discovery_summary.get(k) for k in ("safeguards", "warnings", "features_excluded", "hypotheses_tested", "note")},
                           "clustering": {k: run.clustering_summary.get(k) for k in ("method", "k", "silhouette", "skipped", "note")}},
        "investigation": investigation_payload(inv) if inv else None,
        "evidence": [{"evidence_id": e.evidence_key, "kind": e.kind, "title": e.title, "content": e.content} for e in inv.evidence] if inv else [],
        "experiments": [{"id": e.id, "title": e.title, "status": e.status, "target": e.target_failure_group, "hypothesis": e.hypothesis,
                         "proposed_change": e.proposed_change, "baseline_metric": e.baseline_metric_name, "baseline_value": e.baseline_metric_value,
                         "success_criterion": e.success_criterion, "outcome": outcome(e),
                         "results": [{"metric": r.metric_name, "baseline": r.baseline_value, "new": r.new_value, "source": r.source} for r in e.results]}
                        for e in experiments],
        "disclaimer": DISCLAIMER,
    }


def to_markdown(r: dict[str, Any]) -> str:
    L: list[str] = []
    s = r["summary"]
    L += [f"# Blindspot AI investigation report: {r['project']['name']}", "",
          f"- **Evaluation run:** #{r['run_id']} ({r['run_label']})", f"- **Run timestamp:** {r['run_created_at']}",
          f"- **Report generated:** {r['generated_at']}",
          f"- **Dataset:** {r['dataset']['name']} v{r['dataset']['version']} ({r['dataset']['records']:,} records, sha256 `{r['dataset']['sha256'][:12]}`)"]
    if r["dataset"]["synthetic"]:
        L.append("- **Data:** SYNTHETIC benchmark data with deliberately planted failure patterns.")
    L += ["", f"> {r['disclaimer']}", "", "## 1. Evaluation summary (verified by the engine)", "",
          f"Task: `{s['task_type']}` · evaluated records: {s['evaluated_records']:,} · failures: {s['failures']:,} · error rate: {_pct(s['error_rate'])}", "",
          "| Metric | Value |", "|---|---|"]
    for m in r["metrics"]:
        if m["scope"] == "overall":
            L.append(f"| {m['name']} | {_num(m['value'])} |")
    per = [m for m in r["metrics"] if m["scope"] != "overall" and m["name"] in ("f1", "recall", "field_accuracy")]
    if per:
        L += ["", "| Scope | Key | Metric | Value |", "|---|---|---|---|"] + [f"| {m['scope']} | {m['scope_key']} | {m['name']} | {_num(m['value'])} |" for m in per[:60]]
    L += ["", "## 2. Hidden failure groups (verified statistics)", ""]
    if not r["failure_groups"]:
        L.append("No failure groups met the reliability and size thresholds.")
    for g in r["failure_groups"]:
        L += [f"### #{g['rank']} {g['name']}", "", f"- Rule: `{g['rule'].replace(chr(10), ' ')}` ({g['method']})",
              f"- Records: {g['records']:,} · failures: {g['failures']:,} · error rate: {_pct(g['error_rate'])} vs overall {_pct(g['baseline_error_rate'])} "
              f"(+{g['difference'] * 100:.1f} pp)",
              f"- 95% CI: {_pct(g['ci95'][0])} to {_pct(g['ci95'][1])} · q-value: {g['q_value']:.4f} · reliability: **{g['reliability']}** · severity: {g['severity']}",
              *[f"- Note: {n}" for n in g["notes"]], ""]
    L += ["## 3. Failure clusters", ""]
    sk = r["analysis_notes"]["clustering"].get("skipped")
    if sk:
        L.append(f"Clustering skipped: {sk}")
    for c in r["clusters"]:
        L.append(f"- **{c['label']}**: {c['size']} failures ({_pct(c['share_of_failures'])} of all failures)")
    L += ["", "## 4. AI investigation (hypotheses, not facts)", ""]
    inv = r["investigation"]
    if not inv:
        L.append("No investigation has been run for this evaluation.")
    else:
        L += [f"Investigation #{inv['id']} · status: `{inv['status']}` · model: {inv['model'] or 'n/a'} · tokens: {inv['prompt_tokens'] + inv['completion_tokens']:,} · est. cost: ${inv['cost_usd']:.4f}", ""]
        if inv["message"]:
            L += [f"_{inv['message']}_", ""]
        rep = inv["report"] or {}
        if rep.get("summary"):
            L += [f"**Summary:** {rep['summary']}", ""]
        if rep.get("main_pattern"):
            mp = rep["main_pattern"]
            L += [f"**Main detected pattern:** {mp['description']} (groups: {', '.join(mp['failure_groups']) or 'n/a'}; evidence: {', '.join(mp['evidence_ids']) or 'n/a'})", ""]
        for i, h in enumerate(rep.get("hypotheses", []), 1):
            L += [f"### Hypothesis {i}: {h['title']} ({h['confidence']} confidence, {h.get('validation_status', 'unchecked')})", "", h["explanation"], ""]
            L += [f"- Supporting {e['evidence_id']}: {e['explanation']}" for e in h["supporting_evidence"]]
            L += [f"- Counter-evidence {e['evidence_id']}: {e['explanation']}" for e in h["counter_evidence"]]
            L += [f"- How to test: {h['how_to_test']}", ""]
        if rep.get("assessment"):
            a = rep["assessment"]
            L += [f"**Severity:** {a['severity']} · **Priority:** {a['priority']}. {a['rationale']}", ""]
        if rep.get("limitations"):
            L += ["**Limitations:**", *[f"- {x}" for x in rep["limitations"]], ""]
        v = inv.get("validation") or {}
        if v.get("issues"):
            L += ["**Validation issues:**", *[f"- [{i['severity']}] {i['where']}: {i['message']}" for i in v["issues"]], ""]
    L += ["## 5. Experiments", ""]
    if not r["experiments"]:
        L.append("No experiments are linked to this run.")
    for e in r["experiments"]:
        L += [f"### {e['title']} ({e['status']})", f"- Target: {e['target'] or 'n/a'}", f"- Hypothesis: {e['hypothesis']}", f"- Proposed change: {e['proposed_change']}",
              f"- Baseline: {e['baseline_metric']} = {_num(e['baseline_value'])} (measured by the engine)", f"- Success criterion: {e['success_criterion']}",
              f"- Outcome: {e['outcome']['message']}", ""]
    if r["evidence"]:
        L += ["## Appendix: evidence items", ""]
        for e in r["evidence"]:
            L.append(f"- **{e['evidence_id']}** ({e['kind']}): {e['title']}")
    return "\n".join(L) + "\n"


def to_csv(db: Session, run: EvaluationRun) -> str:
    ds = run.dataset
    mapping = ds.column_mapping or {}
    meta = mapping.get("metadata_columns", [])
    positions = [c["index"] for c in run.case_results]
    extra = {"expected_label": [c["details"].get("expected_label", "") for c in run.case_results]} if run.task_type == "classification" else None
    ff = build_feature_frame(ds.records, positions, mapping, extra_categorical=extra)
    memberships = [[] for _ in positions]
    for g in run.failure_groups:
        for p, hit in enumerate(apply_conditions(ff.frame, g.conditions)):
            if hit:
                memberships[p].append(str(g.rank))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["run_id", "case_id", "row_number", "correct", "score", "error_type", "expected_output", "actual_output", "failure_groups", *meta])
    for p, c in enumerate(run.case_results):
        rec = ds.records[c["index"]]
        w.writerow([run.id, c["case_id"], c["index"] + 1, c["correct"], c["score"], c["error_type"], rec.get(mapping.get("expected_column")),
                    rec.get(mapping.get("actual_column")), ";".join(memberships[p]), *[rec.get(m) for m in meta]])
    return buf.getvalue()


_PDF_MAP = str.maketrans({"≥": ">=", "≤": "<=", "≠": "!=", "→": "->", "—": "-", "–": "-", "…": "...", "·": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "•": "-"})


def _latin(text: str) -> str:
    t = str(text).translate(_PDF_MAP)
    return t.encode("latin-1", "replace").decode("latin-1")


def to_pdf(r: dict[str, Any]) -> bytes:
    md = to_markdown(r)
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.set_title(_latin(f"Blindspot AI report - run {r['run_id']}"))
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin
    for line in md.splitlines():
        text = _latin(line.replace("**", "").replace("`", "").replace("_", " ").strip())
        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 16); pdf.multi_cell(width, 8, text[2:]); pdf.ln(1)
        elif line.startswith("## "):
            pdf.ln(2); pdf.set_font("Helvetica", "B", 13); pdf.multi_cell(width, 7, text[3:])
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 11); pdf.multi_cell(width, 6, text[4:])
        elif line.startswith("|"):
            if set(line.replace("|", "").strip()) <= {"-"}:
                continue
            cells = [c.strip() for c in text.strip("|").split("|")]
            pdf.set_font("Courier", "", 8); pdf.multi_cell(width, 4.5, "  ".join(f"{c[:38]:<38}" if i == 0 else c for i, c in enumerate(cells)))
        elif line.startswith("> "):
            pdf.set_font("Helvetica", "I", 8); pdf.multi_cell(width, 4.5, text[2:]); pdf.ln(1)
        elif not line.strip():
            pdf.ln(2)
        else:
            pdf.set_font("Helvetica", "", 9); pdf.multi_cell(width, 4.8, text)
    pdf.set_font("Helvetica", "I", 7)
    pdf.multi_cell(width, 4, "Non-Latin characters are shown as '?' in the PDF. The JSON and Markdown exports contain the original text.")
    return bytes(pdf.output())
