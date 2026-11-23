import clsx from "clsx";
import { FlaskConical, Plus, Ruler, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisProps, C, ChartTooltip } from "../components/charts/theme";
import { Badge, Button, Card, Drawer, EmptyState, ErrorState, Field, inputCls, Modal, Notice, PageHeader, Select, Spinner } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";
import type { Experiment, ExperimentStatus } from "../types/api";
import { ago, dateTime, num, pct, pval } from "../utils/format";

const COLUMNS: { status: ExperimentStatus; label: string; hint: string }[] = [
  { status: "recommended", label: "Recommended", hint: "Suggested by the investigator" },
  { status: "planned", label: "Planned", hint: "Accepted, not started" },
  { status: "running", label: "Running", hint: "Being tested" },
  { status: "completed", label: "Completed", hint: "Has measured results" },
];
const NEXT: Record<ExperimentStatus, ExperimentStatus[]> = {
  recommended: ["planned", "running", "abandoned"], planned: ["running", "abandoned"], running: ["completed", "planned", "abandoned"], completed: ["running"], abandoned: ["planned"],
};
const OUTCOME_TONE: Record<string, "ok" | "bad" | "warn" | "neutral"> = { improved: "ok", regressed: "bad", improved_not_significant: "warn", regressed_not_significant: "warn", no_change: "neutral", not_measured: "neutral", measured: "neutral" };

export default function Experiments() {
  const { projectId, project } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const list = useAsync(() => api.experiments({ project_id: projectId ?? undefined }), [projectId]);
  const focus = params.get("focus") ? Number(params.get("focus")) : null;
  const [showAbandoned, setShowAbandoned] = useState(false);
  const items = list.data?.items ?? [];
  const open = items.find((e) => e.id === focus) ?? null;
  const setFocus = (id: number | null) => { id ? params.set("focus", String(id)) : params.delete("focus"); setParams(params, { replace: true }); };
  const newOpen = params.get("new") === "1";

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Experiment lab" title="Experiments" description="Turn hypotheses into measured changes. Improvements are only shown once results exist."
        actions={<Button onClick={() => { params.set("new", "1"); setParams(params, { replace: true }); }} disabled={!projectId}><Plus className="h-4 w-4" /> New experiment</Button>} />
      {list.loading && !list.data ? <Spinner /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : items.length === 0 ? (
        <EmptyState icon={<FlaskConical className="h-6 w-6" />} title={project ? `No experiments in ${project.name}` : "No experiments"}>
          Run an AI investigation to get recommended experiments, or create one from a failure group.
        </EmptyState>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-4">
            {COLUMNS.map((col) => {
              const colItems = items.filter((e) => e.status === col.status);
              return (
                <div key={col.status} className="rounded-xl border border-line bg-ink-900/60 p-3">
                  <div className="mb-3 flex items-center justify-between px-1"><div><div className="text-sm font-medium">{col.label}</div><div className="text-[11px] text-fg-faint">{col.hint}</div></div><Badge>{colItems.length}</Badge></div>
                  <div className="space-y-2">
                    {colItems.map((e) => (
                      <button key={e.id} onClick={() => setFocus(e.id)} className="w-full rounded-lg border border-line bg-ink-800 p-3 text-left hover:border-accent/40">
                        <div className="text-sm font-medium leading-snug">{e.title}</div>
                        <div className="mt-1 line-clamp-2 text-[11px] text-fg-muted">{e.target_failure_group || "No target group"}</div>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          {e.source === "investigator" && <Badge tone="violet">from investigator</Badge>}
                          <Badge tone={OUTCOME_TONE[e.outcome.state] ?? "neutral"}>{e.outcome.state.replace(/_/g, " ")}</Badge>
                          <span className="text-[10px] text-fg-faint">{ago(e.updated_at)}</span>
                        </div>
                      </button>
                    ))}
                    {colItems.length === 0 && <div className="rounded-lg border border-dashed border-line px-3 py-6 text-center text-[11px] text-fg-faint">Empty</div>}
                  </div>
                </div>
              );
            })}
          </div>
          {items.some((e) => e.status === "abandoned") && (
            <div>
              <button onClick={() => setShowAbandoned((s) => !s)} className="text-xs text-fg-muted hover:text-fg">{showAbandoned ? "Hide" : "Show"} abandoned ({items.filter((e) => e.status === "abandoned").length})</button>
              {showAbandoned && <div className="mt-2 flex flex-wrap gap-2">{items.filter((e) => e.status === "abandoned").map((e) => <button key={e.id} onClick={() => setFocus(e.id)} className="rounded-lg border border-line px-3 py-1.5 text-xs text-fg-muted hover:bg-ink-700">{e.title}</button>)}</div>}
            </div>
          )}
          <ComparisonView items={items.filter((e) => e.results.length > 0)} />
        </>
      )}
      {open && <ExperimentDrawer exp={open} onClose={() => setFocus(null)} onChange={() => list.reload()} />}
      {newOpen && projectId && <NewExperimentModal projectId={projectId} groupId={params.get("group") ? Number(params.get("group")) : null}
        onClose={() => { params.delete("new"); params.delete("group"); setParams(params, { replace: true }); }}
        onCreated={(id) => { list.reload(); params.delete("new"); params.delete("group"); params.set("focus", String(id)); setParams(params, { replace: true }); }} />}
    </div>
  );
}

function ComparisonView({ items }: { items: Experiment[] }) {
  if (!items.length) return null;
  const data = items.map((e) => { const r = e.results[e.results.length - 1]; return { name: e.title.length > 28 ? e.title.slice(0, 27) + "…" : e.title, baseline: r.baseline_value, after: r.new_value, metric: r.metric_name }; });
  return (
    <Card className="p-5">
      <div className="mb-1 text-sm font-medium">Measured comparison</div>
      <div className="mb-4 text-xs text-fg-muted">Latest measured result per experiment: baseline vs. after the change. Only experiments with recorded measurements appear.</div>
      <div className="h-72"><ResponsiveContainer>
        <BarChart data={data}><CartesianGrid stroke={C.grid} vertical={false} /><XAxis dataKey="name" {...axisProps} /><YAxis {...axisProps} width={50} />
          <Tooltip content={<ChartTooltip formatter={(v) => num(v, 4)} />} cursor={{ fill: "#ffffff08" }} />
          <Bar dataKey="baseline" name="Baseline" fill={C.axis} radius={[4, 4, 0, 0]} /><Bar dataKey="after" name="After change" fill={C.accent} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer></div>
    </Card>
  );
}

function ExperimentDrawer({ exp, onClose, onChange }: { exp: Experiment; onClose: () => void; onChange: () => void }) {
  const runs = useAsync(() => api.runs(exp.project_id), [exp.project_id]);
  const [notes, setNotes] = useState(exp.notes);
  const [err, setErr] = useState<string>();
  const [busy, setBusy] = useState<string | null>(null);
  const [cand, setCand] = useState("");
  const [manual, setManual] = useState({ metric_name: "", baseline_value: "", new_value: "", higher_is_better: true });
  useEffect(() => setNotes(exp.notes), [exp.id, exp.notes]);

  const act = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key); setErr(undefined);
    try { await fn(); onChange(); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };
  const latest = exp.results[exp.results.length - 1];
  const candidates = (runs.data?.items ?? []).filter((r) => r.id !== exp.baseline_run_id && r.status === "completed");

  return (
    <Drawer open onClose={onClose} wide title={exp.title} subtitle={`Experiment #${exp.id} · ${exp.status} · updated ${dateTime(exp.updated_at)}`}>
      <div className="space-y-5">
        <div className="flex flex-wrap gap-2">{NEXT[exp.status].map((s) => <Button key={s} size="sm" variant={s === "abandoned" ? "ghost" : "secondary"} loading={busy === s} onClick={() => act(s, () => api.updateExperiment(exp.id, { status: s }))}>Mark {s}</Button>)}</div>
        {err && <Notice tone="error">{err}</Notice>}
        <Notice tone={OUTCOME_TONE[exp.outcome.state] === "ok" ? "ok" : OUTCOME_TONE[exp.outcome.state] === "bad" ? "error" : "info"} title={exp.outcome.message}>
          {exp.outcome.p_value != null && <>Two-proportion test p = {pval(exp.outcome.p_value)}.</>}
        </Notice>
        <dl className="grid gap-4 text-sm md:grid-cols-2">
          {[["Target failure group", exp.target_failure_group || "—"], ["Hypothesis", exp.hypothesis], ["Proposed change", exp.proposed_change], ["Test procedure", exp.test_procedure],
            ["Baseline metric (measured by the engine)", exp.baseline_metric_name ? `${exp.baseline_metric_name}: ${exp.baseline_metric_value != null ? pct(exp.baseline_metric_value) : "—"}` : "—"], ["Success criterion", exp.success_criterion]].map(([k, v]) => (
            <div key={k}><dt className="text-[11px] uppercase tracking-wider text-fg-faint">{k}</dt><dd className="mt-1 whitespace-pre-wrap text-fg-muted">{v || "—"}</dd></div>
          ))}
          <div><dt className="text-[11px] uppercase tracking-wider text-fg-faint">Risks</dt><dd className="mt-1 flex flex-wrap gap-1">{exp.risks.length ? exp.risks.map((r) => <Badge key={r} tone="warn">{r}</Badge>) : <span className="text-fg-muted">—</span>}</dd></div>
          <div><dt className="text-[11px] uppercase tracking-wider text-fg-faint">Evidence references</dt><dd className="mt-1 flex flex-wrap gap-1">{exp.evidence_refs.length ? exp.evidence_refs.map((r) => <Badge key={r}>{r}</Badge>) : <span className="text-fg-muted">—</span>}</dd></div>
        </dl>

        <div className="rounded-lg border border-line p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium"><Ruler className="h-4 w-4 text-accent" /> Measure on a new evaluation run</div>
          <p className="mb-3 text-xs text-fg-muted">Re-applies the target group's rule to the new run's data and compares its error rate with the baseline run. Upload the model's new outputs as a new dataset version and evaluate it first.</p>
          <div className="flex flex-col gap-2 md:flex-row">
            <Select value={cand} onChange={setCand} className="flex-1"><option value="">Choose the run after the change…</option>{candidates.map((r) => <option key={r.id} value={r.id}>Run #{r.id} · {r.label} · {pct(r.error_rate)} errors</option>)}</Select>
            <Button disabled={!cand || !exp.baseline_run_id} loading={busy === "measure"} onClick={() => act("measure", () => api.measure(exp.id, Number(cand)))}>Measure</Button>
          </div>
          {!exp.baseline_run_id && <p className="mt-2 text-xs text-warn">This experiment has no baseline run, so record results manually below.</p>}
        </div>

        <div className="rounded-lg border border-line p-4">
          <div className="mb-3 text-sm font-medium">Record a result manually</div>
          <div className="grid gap-3 md:grid-cols-4">
            <input className={inputCls + " md:col-span-2"} placeholder="Metric name" value={manual.metric_name} onChange={(e) => setManual({ ...manual, metric_name: e.target.value })} />
            <input className={inputCls} placeholder="Baseline value" inputMode="decimal" value={manual.baseline_value} onChange={(e) => setManual({ ...manual, baseline_value: e.target.value })} />
            <input className={inputCls} placeholder="New value" inputMode="decimal" value={manual.new_value} onChange={(e) => setManual({ ...manual, new_value: e.target.value })} />
          </div>
          <div className="mt-3 flex items-center justify-between">
            <label className="flex items-center gap-2 text-xs text-fg-muted"><input type="checkbox" className="accent-[#6275FF]" checked={manual.higher_is_better} onChange={(e) => setManual({ ...manual, higher_is_better: e.target.checked })} /> Higher is better</label>
            <Button size="sm" variant="secondary" loading={busy === "manual"} disabled={!manual.metric_name || manual.new_value === "" || Number.isNaN(Number(manual.new_value))}
              onClick={() => act("manual", async () => { await api.addResult(exp.id, { metric_name: manual.metric_name, baseline_value: manual.baseline_value === "" ? null : Number(manual.baseline_value), new_value: Number(manual.new_value), higher_is_better: manual.higher_is_better }); setManual({ metric_name: "", baseline_value: "", new_value: "", higher_is_better: true }); })}>Save result</Button>
          </div>
        </div>

        {exp.results.length > 0 && (
          <div>
            <div className="mb-2 text-sm font-medium">Results</div>
            <table className="w-full text-left text-sm"><thead className="text-xs text-fg-muted"><tr className="border-b border-line"><th className="py-2">Metric</th><th className="py-2">Baseline</th><th className="py-2">New</th><th className="py-2">Source</th><th className="py-2">Recorded</th></tr></thead>
              <tbody className="divide-y divide-line">{exp.results.map((r) => (
                <tr key={r.id}><td className="py-2 pr-3">{r.metric_name}</td><td className="py-2">{num(r.baseline_value, 4)}</td><td className={clsx("py-2", latest?.id === r.id && "font-medium")}>{num(r.new_value, 4)}</td>
                  <td className="py-2"><Badge tone={r.source === "measured_from_runs" ? "ok" : "neutral"}>{r.source === "measured_from_runs" ? "measured from runs" : "manual"}</Badge></td><td className="py-2 text-xs text-fg-faint">{ago(r.recorded_at)}</td></tr>
              ))}</tbody></table>
          </div>
        )}

        <Field label="Notes"><textarea className={inputCls + " min-h-[110px]"} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        <div className="flex justify-between">
          <Button variant="danger" size="sm" loading={busy === "delete"} onClick={() => act("delete", async () => { await api.deleteExperiment(exp.id); onClose(); })}><Trash2 className="h-4 w-4" /> Delete</Button>
          <Button size="sm" loading={busy === "notes"} disabled={notes === exp.notes} onClick={() => act("notes", () => api.updateExperiment(exp.id, { notes }))}>Save notes</Button>
        </div>
      </div>
    </Drawer>
  );
}

function NewExperimentModal({ projectId, groupId, onClose, onCreated }: { projectId: number; groupId: number | null; onClose: () => void; onCreated: (id: number) => void }) {
  const [f, setF] = useState({ title: "", hypothesis: "", proposed_change: "", test_procedure: "", success_criterion: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string>();
  const submit = async () => {
    setBusy(true); setErr(undefined);
    try { const e = await api.createExperiment({ project_id: projectId, failure_group_id: groupId, ...f }); onCreated(e.id); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} title="New experiment" footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button loading={busy} disabled={!f.title.trim()} onClick={submit}>Create</Button></>}>
      <div className="space-y-3">
        {groupId && <Notice tone="info">Targets failure group #{groupId}. Its current error rate becomes the measured baseline.</Notice>}
        <Field label="Title" required><input className={inputCls} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} autoFocus /></Field>
        <Field label="Hypothesis"><textarea className={inputCls} value={f.hypothesis} onChange={(e) => setF({ ...f, hypothesis: e.target.value })} /></Field>
        <Field label="Proposed change"><textarea className={inputCls} value={f.proposed_change} onChange={(e) => setF({ ...f, proposed_change: e.target.value })} /></Field>
        <Field label="Test procedure"><input className={inputCls} value={f.test_procedure} onChange={(e) => setF({ ...f, test_procedure: e.target.value })} placeholder="Re-run the same cases with the change" /></Field>
        <Field label="Success criterion"><input className={inputCls} value={f.success_criterion} onChange={(e) => setF({ ...f, success_criterion: e.target.value })} /></Field>
        {err && <Notice tone="error">{err}</Notice>}
      </div>
    </Modal>
  );
}
