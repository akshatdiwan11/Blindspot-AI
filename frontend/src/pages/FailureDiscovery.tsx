import clsx from "clsx";
import { Boxes, FlaskConical, Info, Microscope, ShieldCheck, Sparkles } from "lucide-react";
import { useCallback, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CaseCard, RuleView, RunPicker } from "../components/domain";
import { Badge, Button, Card, CardHeader, Drawer, EmptyState, ErrorState, LinkButton, Notice, PageHeader, ReliabilityBadge, SeverityBadge, Spinner, SyntheticBadge, Tabs } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";
import type { Cluster, FailureGroup } from "../types/api";
import { int, pct, pp, pval } from "../utils/format";

function RateBar({ g }: { g: FailureGroup }) {
  return (
    <div className="relative h-6">
      <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-ink-600" />
      <div className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-bad/30" style={{ left: `${g.ci_low * 100}%`, width: `${(g.ci_high - g.ci_low) * 100}%` }} title={`95% interval ${pct(g.ci_low)} – ${pct(g.ci_high)}`} />
      <div className={clsx("absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink-800", g.reliability === "reliable" ? "bg-bad" : "bg-fg-faint")} style={{ left: `${g.error_rate * 100}%` }} title={`Group error rate ${pct(g.error_rate)}`} />
      <div className="absolute top-0 h-full w-0.5 bg-accent" style={{ left: `${g.baseline_error_rate * 100}%` }} title={`Overall error rate ${pct(g.baseline_error_rate)}`} />
    </div>
  );
}

export default function FailureDiscovery() {
  const { projectId, project } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const runId = params.get("run") ? Number(params.get("run")) : null;
  const setRun = useCallback((id: number) => { params.set("run", String(id)); setParams(params, { replace: true }); }, [params, setParams]);
  const run = useAsync(() => api.run(runId!), [runId], !!runId);
  const groups = useAsync(() => api.failureGroups(runId!), [runId], !!runId);
  const clusters = useAsync(() => api.clusters(runId!), [runId], !!runId);
  const [filter, setFilter] = useState<"all" | "reliable" | "tentative">("all");
  const openGroup = params.get("group") ? Number(params.get("group")) : null;
  const [openCluster, setOpenCluster] = useState<Cluster | null>(null);
  const navigate = useNavigate();

  const items = (groups.data?.items ?? []).filter((g) => filter === "all" || g.reliability === filter);
  const ds = run.data?.discovery_summary;
  const reliable = (groups.data?.items ?? []).filter((g) => g.reliability === "reliable").length;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Failure discovery" title="Hidden failure groups"
        description="Slices of your data where the model fails significantly more than its overall rate. Statistics are computed by the engine; groups are associations, not causes."
        actions={<RunPicker projectId={run.data?.project_id ?? projectId} value={runId} onChange={setRun} />} />
      {!runId ? (
        <EmptyState icon={<Microscope className="h-6 w-6" />} title={project ? "No evaluation runs in this project" : "No project selected"} action={<LinkButton to="/projects">Open projects</LinkButton>}>
          Run an evaluation first; failure discovery runs automatically with it.
        </EmptyState>
      ) : run.loading && !run.data ? <Spinner /> : run.error ? <ErrorState error={run.error} onRetry={run.reload} /> : (
        <>
          <Card className="grid gap-px overflow-hidden bg-line md:grid-cols-5">
            {[
              ["Overall error rate", pct(run.data!.error_rate), `${int(run.data!.failure_count)} of ${int(run.data!.evaluated_records)} records`],
              ["Failure groups", String(groups.data?.total ?? "—"), `${reliable} statistically reliable`],
              ["Hypotheses tested", int(ds?.hypotheses_tested ?? 0), `FDR ${pct(ds?.fdr_alpha ?? 0.05, 0)} (Benjamini–Hochberg)`],
              ["Features analysed", String(ds?.features_used?.length ?? 0), `${ds?.features_excluded?.length ?? 0} excluded`],
              ["Failure clusters", String(clusters.data?.length ?? 0), run.data!.clustering_summary.skipped ? "clustering skipped" : run.data!.clustering_summary.method ?? ""],
            ].map(([k, v, h]) => (
              <div key={k} className="bg-ink-800 p-4"><div className="text-xs text-fg-muted">{k}</div><div className="mt-1 font-display text-3xl">{v}</div><div className="mt-1 text-[11px] text-fg-faint">{h}</div></div>
            ))}
          </Card>
          <div className="flex flex-wrap items-center gap-2">
            {run.data!.dataset_name && <Badge>dataset: {run.data!.dataset_name}</Badge>}
            {project?.is_demo && <SyntheticBadge />}
            {(ds?.warnings ?? []).map((w) => <Notice key={w} tone="warn" className="w-full">{w}</Notice>)}
          </div>

          <Card>
            <CardHeader title="Subgroup error rate vs. overall" subtitle="Dot: group error rate · shaded: 95% Wilson interval · blue line: overall error rate"
              action={<Tabs value={filter} onChange={setFilter} tabs={[{ value: "all", label: "All", count: groups.data?.total }, { value: "reliable", label: "Reliable", count: reliable }, { value: "tentative", label: "Tentative", count: (groups.data?.total ?? 0) - reliable }]} />} />
            {groups.loading && !groups.data ? <Spinner /> : items.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-fg-muted">No failure groups passed the size and significance checks{filter !== "all" ? " for this filter" : ""}. That can be a good sign, or a sign that more metadata is needed.</div>
            ) : (
              <div className="divide-y divide-line">
                {items.map((g) => (
                  <button key={g.id} onClick={() => { params.set("group", String(g.id)); setParams(params, { replace: true }); }} className="grid w-full items-center gap-3 px-5 py-3 text-left hover:bg-ink-700/40 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_auto]">
                    <div className="min-w-0"><RuleView conditions={g.conditions} compact /></div>
                    <RateBar g={g} />
                    <div className="flex items-center gap-3 text-xs tabular-nums"><span className={g.reliability === "reliable" ? "text-bad" : "text-fg-muted"}>{pct(g.error_rate)}</span><span className="text-fg-faint">n={g.sample_size}</span></div>
                  </button>
                ))}
              </div>
            )}
          </Card>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {items.map((g) => (
              <button key={g.id} onClick={() => { params.set("group", String(g.id)); setParams(params, { replace: true }); }}
                className={clsx("group flex flex-col rounded-xl border bg-ink-800 p-5 text-left transition-all hover:-translate-y-0.5 hover:shadow-xl", g.reliability === "reliable" ? "border-line hover:border-bad/50" : "border-dashed border-line")}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-fg-faint">GROUP #{g.rank} · {g.method}</span>
                  <div className="flex gap-1.5"><SeverityBadge severity={g.severity} /><ReliabilityBadge reliability={g.reliability} /></div>
                </div>
                <div className="mt-3 text-sm font-medium leading-snug group-hover:text-fg">{g.name}</div>
                <div className="mt-3"><RuleView conditions={g.conditions} compact /></div>
                <div className="mt-4 flex items-end justify-between">
                  <div><div className="font-display text-4xl text-bad">{pct(g.error_rate)}</div><div className="text-[11px] text-fg-faint">error rate vs {pct(g.baseline_error_rate)} overall</div></div>
                  <div className="text-right"><div className="text-lg font-semibold text-warn">{pp(g.difference)}</div><div className="text-[11px] text-fg-faint">difference</div></div>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2 border-t border-line pt-3 text-center text-xs">
                  <div><div className="text-fg">{int(g.sample_size)}</div><div className="text-fg-faint">records</div></div>
                  <div><div className="text-fg">{int(g.failures)}</div><div className="text-fg-faint">failures</div></div>
                  <div><div className="text-fg">{g.severity_score.toFixed(1)}</div><div className="text-fg-faint">excess failures</div></div>
                </div>
                <div className="mt-3 text-[11px] text-fg-faint">95% CI {pct(g.ci_low)}–{pct(g.ci_high)} · q = {pval(g.q_value)}</div>
              </button>
            ))}
          </div>

          <Card>
            <CardHeader title="Failure clusters" icon={<Boxes className="h-4 w-4" />} subtitle={run.data!.clustering_summary.skipped ?? `${run.data!.clustering_summary.method} · k = ${run.data!.clustering_summary.k} · silhouette ${run.data!.clustering_summary.silhouette?.toFixed(2)}`} />
            {(clusters.data ?? []).length === 0 ? <div className="px-5 py-8 text-sm text-fg-muted">{run.data!.clustering_summary.skipped ?? "No clusters."}</div> : (
              <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
                {clusters.data!.map((c) => (
                  <button key={c.id} onClick={() => setOpenCluster(c)} className="rounded-lg border border-line p-4 text-left hover:border-accent-2/50 hover:bg-ink-700/30">
                    <div className="flex items-center justify-between"><span className="font-mono text-xs text-fg-faint">CLUSTER {c.cluster_index + 1}</span><span className="text-xs text-fg-muted">{c.size} failures · {pct(c.share_of_failures, 0)}</span></div>
                    <div className="mt-2 text-sm font-medium leading-snug">{c.label}</div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ink-600"><div className="h-full bg-accent-2" style={{ width: `${c.share_of_failures * 100}%` }} /></div>
                    <div className="mt-3 flex flex-wrap gap-1">{c.dominant_metadata.filter((d) => d.value).map((d) => <Badge key={d.column} tone="violet">{d.column} = {d.value} ({pct(d.share, 0)})</Badge>)}</div>
                  </button>
                ))}
              </div>
            )}
            {run.data!.clustering_summary.note && <p className="px-5 pb-4 text-xs text-fg-faint">{run.data!.clustering_summary.note}</p>}
          </Card>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader title="Safeguards applied" icon={<ShieldCheck className="h-4 w-4" />} />
              <ul className="space-y-2 p-5 text-sm text-fg-muted">{(ds?.safeguards ?? []).map((s) => <li key={s} className="flex gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" />{s}</li>)}</ul>
              {ds?.note && <p className="px-5 pb-5 text-xs text-fg-faint">{ds.note}</p>}
            </Card>
            <Card>
              <CardHeader title="Features analysed" icon={<Info className="h-4 w-4" />} subtitle="Metadata you mapped plus features derived from the input text" />
              <div className="flex flex-wrap gap-1.5 p-5">
                {(ds?.features_used ?? []).map((f) => <Badge key={f.name} tone={f.origin === "derived" ? "violet" : "accent"} title={f.description}>{f.name} · {f.kind}</Badge>)}
                {(ds?.features_excluded ?? []).map((f) => <Badge key={f.feature} title={f.reason}>excluded: {f.feature}</Badge>)}
              </div>
              {(ds?.features_excluded ?? []).length > 0 && <ul className="space-y-1 px-5 pb-5 text-xs text-fg-faint">{ds!.features_excluded!.map((f) => <li key={f.feature}>{f.feature}: {f.reason}</li>)}</ul>}
            </Card>
          </div>
        </>
      )}
      {openGroup && runId && <GroupDrawer runId={runId} groupId={openGroup} onClose={() => { params.delete("group"); setParams(params, { replace: true }); }}
        onInvestigate={(gid) => navigate(`/investigator?run=${runId}&groups=${gid}`)} onExperiment={(gid) => navigate(`/experiments?new=1&group=${gid}`)} />}
      {openCluster && runId && <ClusterDrawer runId={runId} cluster={openCluster} onClose={() => setOpenCluster(null)} />}
    </div>
  );
}

function GroupDrawer({ runId, groupId, onClose, onInvestigate, onExperiment }: { runId: number; groupId: number; onClose: () => void; onInvestigate: (g: number) => void; onExperiment: (g: number) => void }) {
  const g = useAsync(() => api.failureGroup(runId, groupId), [runId, groupId]);
  const [tab, setTab] = useState<"failures" | "successes">("failures");
  return (
    <Drawer open onClose={onClose} wide title={g.data ? `Group #${g.data.rank}: ${g.data.name}` : "Failure group"} subtitle={g.data ? `${g.data.method} rule · run #${runId}` : undefined}>
      {g.loading && !g.data ? <Spinner /> : g.error ? <ErrorState error={g.error} /> : (() => {
        const d = g.data!;
        return (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2"><SeverityBadge severity={d.severity} /><ReliabilityBadge reliability={d.reliability} /><Badge tone="ok">verified statistics</Badge></div>
            <RuleView conditions={d.conditions} />
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {[["Records", int(d.sample_size)], ["Failures", int(d.failures)], ["Error rate", pct(d.error_rate)], ["Overall", pct(d.baseline_error_rate)], ["Rest of data", pct(d.complement_error_rate)], ["Difference", pp(d.difference)], ["Lift", d.lift ? `${d.lift.toFixed(2)}×` : "—"], ["Excess failures", d.severity_score.toFixed(1)]].map(([k, v]) => (
                <div key={k} className="rounded-lg border border-line bg-ink-900 p-3"><div className="text-[11px] text-fg-muted">{k}</div><div className="mt-0.5 text-lg font-semibold">{v}</div></div>
              ))}
            </div>
            <div className="rounded-lg border border-line p-4 text-sm"><RateBar g={d} />
              <div className="mt-2 text-xs text-fg-muted">95% Wilson interval {pct(d.ci_low)} – {pct(d.ci_high)} · Fisher exact p = {pval(d.p_value)} · BH-adjusted q = {pval(d.q_value)}</div></div>
            {d.notes.length > 0 && <div className="space-y-2">{d.notes.map((n) => <Notice key={n} tone="info">{n}</Notice>)}</div>}
            <Notice tone="warn">This shows where failures concentrate, not why. Use the AI investigator for hypotheses, then test them with an experiment.</Notice>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => onInvestigate(d.id)}><Sparkles className="h-4 w-4" /> Investigate this group</Button>
              <Button variant="secondary" onClick={() => onExperiment(d.id)}><FlaskConical className="h-4 w-4" /> Plan an experiment</Button>
            </div>
            <Tabs value={tab} onChange={setTab} tabs={[{ value: "failures", label: "Failed examples", count: d.examples.length }, { value: "successes", label: "Correct cases in this group", count: d.successes.length }]} />
            <div className="space-y-2">
              {(tab === "failures" ? d.examples : d.successes).map((c, i) => <CaseCard key={c.index} c={c} defaultOpen={i === 0} />)}
              {tab === "successes" && d.successes.length === 0 && <p className="text-sm text-fg-muted">Every case in this group failed.</p>}
            </div>
          </div>
        );
      })()}
    </Drawer>
  );
}

function ClusterDrawer({ runId, cluster, onClose }: { runId: number; cluster: Cluster; onClose: () => void }) {
  const c = useAsync(() => api.cluster(runId, cluster.id), [runId, cluster.id]);
  const errs = cluster.dominant_metadata.find((d) => d.column === "error_type")?.counts as Record<string, number> | undefined;
  return (
    <Drawer open onClose={onClose} wide title={`Cluster ${cluster.cluster_index + 1}: ${cluster.label}`} subtitle={`${cluster.size} failures · ${pct(cluster.share_of_failures)} of all failures · ${cluster.method}`}>
      <div className="space-y-4">
        <div className="flex flex-wrap gap-1.5">{cluster.top_terms.map((t) => <Badge key={t} tone="violet">{t}</Badge>)}{errs && Object.entries(errs).map(([k, v]) => <Badge key={k} tone="bad">{k.replace(/_/g, " ")}: {v}</Badge>)}</div>
        <Notice tone="info">Clusters group failures whose mistakes look alike, so you can read them in batches. They do not explain why the model failed.</Notice>
        {c.loading && !c.data ? <Spinner /> : c.error ? <ErrorState error={c.error} /> : c.data!.examples.map((e, i) => <CaseCard key={e.index} c={e} defaultOpen={i === 0} />)}
        <Link to={`/evaluations/${runId}`} className="text-xs text-accent hover:underline">Open the full run</Link>
      </div>
    </Drawer>
  );
}
