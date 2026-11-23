import clsx from "clsx";
import { ChevronLeft, ChevronRight, FileBarChart2, Gauge, Microscope, Search, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisProps, C, ChartTooltip } from "../components/charts/theme";
import { CaseCard } from "../components/domain";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, inputCls, LinkButton, Notice, PageHeader, Select, Spinner, Stat, Tabs } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";
import type { RunDetail } from "../types/api";
import { dateTime, int, metricLabel, num, pct, pval, TASK_LABEL, titleCase } from "../utils/format";

export function EvaluationsList() {
  const { projectId, project } = useWorkspace();
  const runs = useAsync(() => (projectId ? api.runs(projectId) : api.allRuns()), [projectId]);
  const navigate = useNavigate();
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const items = runs.data?.items ?? [];
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Evaluations" title="Evaluation runs" description={project ? `Runs for ${project.name}. Switch project from the top bar.` : "All evaluation runs."} />
      {runs.loading && !runs.data ? <Spinner /> : runs.error ? <ErrorState error={runs.error} onRetry={runs.reload} /> : items.length === 0 ? (
        <EmptyState icon={<Gauge className="h-6 w-6" />} title="No evaluation runs" action={<LinkButton to="/datasets">Go to datasets</LinkButton>}>Map a dataset's columns and run an evaluation to see results here.</EmptyState>
      ) : (
        <>
          <Card className="flex flex-col gap-3 p-4 md:flex-row md:items-end">
            <div className="flex-1"><div className="mb-1 text-xs text-fg-muted">Baseline run</div><Select value={a} onChange={setA}><option value="">Choose…</option>{items.map((r) => <option key={r.id} value={r.id}>#{r.id} {r.label}</option>)}</Select></div>
            <div className="flex-1"><div className="mb-1 text-xs text-fg-muted">Compare with</div><Select value={b} onChange={setB}><option value="">Choose…</option>{items.map((r) => <option key={r.id} value={r.id}>#{r.id} {r.label}</option>)}</Select></div>
            <Button disabled={!a || !b || a === b} onClick={() => navigate(`/evaluations/compare?a=${a}&b=${b}`)}>Compare runs</Button>
          </Card>
          <div className="grid gap-3">
            {items.map((r) => (
              <Link key={r.id} to={`/evaluations/${r.id}`} className="flex flex-col gap-3 rounded-xl border border-line bg-ink-800 p-4 hover:border-accent/40 md:flex-row md:items-center md:justify-between">
                <div><div className="font-medium">Run #{r.id} · {r.label}</div><div className="text-xs text-fg-muted">{TASK_LABEL[r.task_type]} · dataset v{r.dataset_version} · {dateTime(r.created_at)}</div></div>
                <div className="flex items-center gap-6 text-sm">
                  <span><span className="text-fg-muted">records</span> {int(r.evaluated_records)}</span>
                  <span><span className="text-fg-muted">failures</span> {int(r.failure_count)}</span>
                  <span className="font-display text-2xl">{pct(r.error_rate)}</span>
                  <Badge tone={r.status === "completed" ? "ok" : "bad"}>{r.status}</Badge>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function overall(run: RunDetail) {
  return Object.fromEntries(run.metrics.filter((m) => m.scope === "overall").map((m) => [m.name, m.value]));
}

export function EvaluationDetail() {
  const id = Number(useParams().id);
  const run = useAsync(() => api.run(id), [id]);
  const [tab, setTab] = useState<"metrics" | "cases">("metrics");
  if (run.loading && !run.data) return <Spinner />;
  if (run.error) return <ErrorState error={run.error} onRetry={run.reload} />;
  const r = run.data!;
  const m = overall(r);
  const extras = r.discovery_summary.evaluation_extras ?? {};
  const cards: [string, number | null | undefined, boolean?][] =
    r.task_type === "classification" ? [["Accuracy", m.accuracy], ["Precision (macro)", m.precision], ["Recall (macro)", m.recall], ["Macro F1", m.f1_macro], ["Weighted F1", m.f1_weighted]]
      : r.task_type === "json" ? [["Accuracy", m.accuracy], ["Exact JSON match", m.exact_json_match], ["Field accuracy", m.field_accuracy], ["Invalid JSON rate", m.invalid_json_rate, true]]
        : [["Accuracy", m.accuracy], ["Normalized exact match", m.normalized_exact_match], ["Token precision", m.token_precision], ["Token recall", m.token_recall], ["Token F1", m.token_f1]];
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={<Link to="/evaluations" className="hover:underline">Evaluations</Link>} title={`Run #${r.id} · ${r.label}`}
        description={<>{TASK_LABEL[r.task_type]} · {r.dataset_name} v{r.dataset_version} · {dateTime(r.created_at)} · {r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)} s` : ""}</>}
        actions={<>
          <LinkButton to={`/failures?run=${r.id}`} variant="secondary"><Microscope className="h-4 w-4" /> Failure discovery</LinkButton>
          <LinkButton to={`/investigator?run=${r.id}`} variant="secondary"><Sparkles className="h-4 w-4" /> Investigate</LinkButton>
          <LinkButton to={`/reports?run=${r.id}`} variant="ghost"><FileBarChart2 className="h-4 w-4" /> Report</LinkButton></>} />
      {r.status !== "completed" && <Notice tone="error" title="This run failed">{r.error_message}</Notice>}
      {r.analysis_status === "failed" && <Notice tone="warn" title="Failure analysis did not complete">{r.discovery_summary.error}. Metrics below are still valid.</Notice>}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-7">
        {cards.map(([k, v, lowerBetter]) => <Stat key={k} label={k} value={k.includes("rate") ? pct(v ?? null) : pct(v ?? null)} tone={v == null ? undefined : lowerBetter ? (v > 0.05 ? "warn" : "ok") : undefined} />)}
        <Stat label="Failure rate" value={pct(r.error_rate)} tone={(r.error_rate ?? 0) > 0.1 ? "bad" : "ok"} />
        <Stat label="Records" value={int(r.evaluated_records)} hint={r.discovery_summary.excluded_records ? `${r.discovery_summary.excluded_records} excluded (no expected output)` : `${int(r.failure_count)} failures`} />
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "metrics", label: "Detailed metrics" }, { value: "cases", label: "Cases", count: r.evaluated_records }]} />
      {tab === "metrics" ? (
        <div className="grid gap-6 xl:grid-cols-2">
          {r.task_type === "classification" && extras.confusion_matrix && extras.labels && <ConfusionMatrix labels={extras.labels} matrix={extras.confusion_matrix} />}
          {r.task_type === "classification" && extras.per_class && (
            <Card>
              <CardHeader title="Per-class performance" subtitle={extras.class_balance ? "Support shows how many true cases each class has" : undefined} />
              <div className="overflow-x-auto"><table className="w-full text-left text-sm">
                <thead className="text-xs text-fg-muted"><tr className="border-b border-line"><th className="px-5 py-2">Class</th><th className="px-3 py-2">Precision</th><th className="px-3 py-2">Recall</th><th className="px-3 py-2">F1</th><th className="px-3 py-2">Support</th><th className="px-3 py-2">FP</th><th className="px-3 py-2">FN</th></tr></thead>
                <tbody className="divide-y divide-line">{extras.per_class.map((c) => (
                  <tr key={c.label}><td className="px-5 py-2 font-medium">{c.label}</td><td className="px-3 py-2">{pct(c.precision)}</td><td className={clsx("px-3 py-2", c.recall < 0.75 && "text-bad")}>{pct(c.recall)}</td><td className="px-3 py-2">{pct(c.f1)}</td><td className="px-3 py-2">{c.support}</td><td className="px-3 py-2">{c.false_positives}</td><td className="px-3 py-2">{c.false_negatives}</td></tr>
                ))}</tbody>
              </table></div>
            </Card>
          )}
          {r.task_type === "json" && extras.per_field && (
            <Card className="xl:col-span-2">
              <CardHeader title="Field-level accuracy" subtitle="Share of cases where each expected field was present and correct" />
              <div className="h-72 p-4"><ResponsiveContainer>
                <BarChart data={extras.per_field.slice(0, 20).map((f) => ({ name: f.field, accuracy: f.accuracy, missing: f.missing, wrong: f.wrong }))}>
                  <CartesianGrid stroke={C.grid} vertical={false} /><XAxis dataKey="name" {...axisProps} /><YAxis {...axisProps} domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} width={40} />
                  <Tooltip content={<ChartTooltip formatter={(v, n) => (n === "Accuracy" ? pct(v) : String(v))} />} cursor={{ fill: "#ffffff08" }} />
                  <Bar dataKey="accuracy" name="Accuracy" radius={[4, 4, 0, 0]}>{extras.per_field.slice(0, 20).map((f) => <Cell key={f.field} fill={(f.accuracy ?? 0) < 0.85 ? C.bad : C.ok} />)}</Bar>
                </BarChart>
              </ResponsiveContainer></div>
            </Card>
          )}
          <Card>
            <CardHeader title="All overall metrics" subtitle="Computed deterministically by the evaluation engine" />
            <table className="w-full text-sm"><tbody className="divide-y divide-line">
              {r.metrics.filter((x) => x.scope === "overall").map((x) => (
                <tr key={x.name}><td className="px-5 py-2 text-fg-muted">{metricLabel(x.name)}{x.extra?.note ? <div className="text-[11px] text-fg-faint">{String(x.extra.note)}</div> : null}</td><td className="px-5 py-2 text-right font-mono">{num(x.value, 4)}</td></tr>
              ))}
            </tbody></table>
          </Card>
          <Card>
            <CardHeader title="Failure types" subtitle="How the failed cases went wrong" />
            <div className="h-64 p-4"><ResponsiveContainer>
              <BarChart data={Object.entries(extras.error_types ?? {}).map(([k, v]) => ({ name: titleCase(k), count: v }))} layout="vertical">
                <CartesianGrid stroke={C.grid} horizontal={false} /><XAxis type="number" {...axisProps} allowDecimals={false} /><YAxis type="category" dataKey="name" {...axisProps} width={130} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "#ffffff08" }} /><Bar dataKey="count" name="Failures" fill={C.violet} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer></div>
            {r.task_type === "text" && <p className="px-5 pb-4 text-xs text-fg-faint">Matching rule: {String(r.config?.text?.match ?? "normalized_exact").replace(/_/g, " ")}{extras.semantic_available === false ? " · semantic similarity not installed" : ""}. Similarity scores are not proof of factual correctness.</p>}
          </Card>
        </div>
      ) : <CasesBrowser runId={r.id} />}
    </div>
  );
}

function ConfusionMatrix({ labels, matrix }: { labels: string[]; matrix: number[][] }) {
  const max = Math.max(1, ...matrix.flat());
  return (
    <Card>
      <CardHeader title="Confusion matrix" subtitle="Rows: expected label · columns: predicted label" />
      <div className="overflow-x-auto p-5">
        <table className="mx-auto border-separate border-spacing-1 text-xs">
          <thead><tr><th />{labels.map((l) => <th key={l} className="max-w-[80px] truncate px-1 pb-1 font-normal text-fg-muted" title={l}>{l}</th>)}</tr></thead>
          <tbody>{matrix.map((row, i) => (
            <tr key={i}><th className="pr-2 text-right font-normal text-fg-muted">{labels[i]}</th>
              {row.map((v, j) => {
                const a = v / max;
                return <td key={j} title={`${labels[i]} → ${labels[j]}: ${v}`} className="h-11 w-14 rounded text-center tabular-nums"
                  style={{ background: i === j ? `rgba(32,201,151,${0.12 + a * 0.7})` : v ? `rgba(242,107,117,${0.12 + a * 0.8})` : "#19243A" }}>{v}</td>;
              })}</tr>
          ))}</tbody>
        </table>
      </div>
    </Card>
  );
}

function CasesBrowser({ runId }: { runId: number }) {
  const [outcome, setOutcome] = useState<"" | "failed" | "passed">("failed");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const cases = useAsync(() => api.cases(runId, { outcome: outcome || undefined, q: q || undefined, limit: 20, offset }), [runId, outcome, q, offset]);
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 md:flex-row">
        <Select value={outcome} onChange={(v) => { setOffset(0); setOutcome(v as any); }} className="md:w-48"><option value="failed">Failed cases</option><option value="passed">Passed cases</option><option value="">All cases</option></Select>
        <div className="relative flex-1"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-faint" /><input className={inputCls + " pl-9"} placeholder="Search case ID, input, outputs, metadata" value={q} onChange={(e) => { setOffset(0); setQ(e.target.value); }} /></div>
        <div className="flex items-center gap-2 text-xs text-fg-muted">
          {cases.data && `${int(cases.data.total ? offset + 1 : 0)}–${int(Math.min(offset + 20, cases.data.total))} of ${int(cases.data.total)}`}
          <Button size="sm" variant="ghost" aria-label="Previous page" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - 20))}><ChevronLeft className="h-4 w-4" /></Button>
          <Button size="sm" variant="ghost" aria-label="Next page" disabled={!cases.data || offset + 20 >= cases.data.total} onClick={() => setOffset((o) => o + 20)}><ChevronRight className="h-4 w-4" /></Button>
        </div>
      </div>
      {cases.loading && !cases.data ? <Spinner /> : cases.error ? <ErrorState error={cases.error} /> : cases.data!.items.map((c) => <CaseCard key={c.index} c={c} />)}
    </div>
  );
}

export function CompareRuns() {
  const [params] = useSearchParams();
  const a = Number(params.get("a")), b = Number(params.get("b"));
  const cmp = useAsync(() => api.compare(a, b), [a, b], !!a && !!b);
  if (!a || !b) return <EmptyState title="Choose two runs to compare" action={<LinkButton to="/evaluations">Go to evaluations</LinkButton>} />;
  if (cmp.loading && !cmp.data) return <Spinner label="Comparing runs" />;
  if (cmp.error) return <ErrorState error={cmp.error} onRetry={cmp.reload} />;
  const c = cmp.data!;
  const overallRows = c.metrics.filter((m) => m.scope === "overall");
  const improved = c.error_rate_test?.significant && (c.run_b.error_rate ?? 0) < (c.run_a.error_rate ?? 0);
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={<Link to="/evaluations" className="hover:underline">Evaluations</Link>} title={`Run #${c.run_a.id} → Run #${c.run_b.id}`} description={`${c.run_a.label} vs ${c.run_b.label}`} />
      <Notice tone={improved ? "ok" : c.error_rate_test?.significant ? "error" : "info"} title={c.verdict}>
        {c.error_rate_test && <>Two-proportion z-test on failure rates: z = {c.error_rate_test.z.toFixed(2)}, p = {pval(c.error_rate_test.p_value)}.</>}
      </Notice>
      {c.notes.map((n) => <Notice key={n} tone="warn">{n}</Notice>)}
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Overall metrics" />
          <table className="w-full text-sm">
            <thead className="text-xs text-fg-muted"><tr className="border-b border-line"><th className="px-5 py-2 text-left">Metric</th><th className="px-3 py-2 text-right">Run #{c.run_a.id}</th><th className="px-3 py-2 text-right">Run #{c.run_b.id}</th><th className="px-5 py-2 text-right">Change</th></tr></thead>
            <tbody className="divide-y divide-line">{overallRows.map((m) => (
              <tr key={m.name}><td className="px-5 py-2 text-fg-muted">{metricLabel(m.name)}</td><td className="px-3 py-2 text-right font-mono">{num(m.run_a, 4)}</td><td className="px-3 py-2 text-right font-mono">{num(m.run_b, 4)}</td>
                <td className={clsx("px-5 py-2 text-right font-mono", m.direction === "improved" && "text-ok", m.direction === "declined" && "text-bad")}>{m.delta == null ? "—" : `${m.delta > 0 ? "+" : ""}${m.delta.toFixed(4)}`}</td></tr>
            ))}</tbody>
          </table>
        </Card>
        <Card>
          <CardHeader title="Failure groups from the baseline, re-measured" subtitle={`Each rule from run #${c.run_a.id} applied to run #${c.run_b.id}'s data`} />
          <div className="h-80 p-4">{c.groups.length === 0 ? <div className="grid h-full place-items-center text-sm text-fg-muted">The baseline run has no failure groups.</div> : (
            <ResponsiveContainer>
              <BarChart data={c.groups.map((g) => ({ name: g.name.length > 30 ? g.name.slice(0, 29) + "…" : g.name, before: g.run_a_error_rate, after: g.run_b_error_rate }))} layout="vertical">
                <CartesianGrid stroke={C.grid} horizontal={false} /><XAxis type="number" {...axisProps} domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} /><YAxis type="category" dataKey="name" {...axisProps} width={200} />
                <Tooltip content={<ChartTooltip formatter={(v) => pct(v)} />} cursor={{ fill: "#ffffff08" }} />
                <Bar dataKey="before" name={`Run #${c.run_a.id}`} fill={C.bad} radius={[0, 4, 4, 0]} /><Bar dataKey="after" name={`Run #${c.run_b.id}`} fill={C.ok} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>)}
          </div>
        </Card>
      </div>
    </div>
  );
}
