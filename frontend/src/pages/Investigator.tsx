import clsx from "clsx";
import { AlertTriangle, BadgeCheck, BrainCircuit, CheckCircle2, FileSearch, FlaskConical, Lightbulb, Scale, ShieldAlert, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CaseCard, RuleView, RunPicker } from "../components/domain";
import { Badge, Button, Card, CardHeader, Drawer, EmptyState, ErrorState, LinkButton, Notice, PageHeader, Select, Spinner } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";
import type { EvidenceItem, FailureGroup, Investigation } from "../types/api";
import { dateTime, int, pct, pp, pval } from "../utils/format";

const STATUS: Record<string, { tone: "ok" | "warn" | "error" | "info"; title: string }> = {
  completed: { tone: "ok", title: "Report generated and every reference checked against the evidence package" },
  completed_with_warnings: { tone: "warn", title: "Report generated with validation warnings" },
  insufficient_evidence: { tone: "info", title: "Insufficient evidence to identify a reliable root-cause hypothesis." },
  llm_disabled: { tone: "info", title: "LLM investigation is turned off for this project" },
  llm_not_configured: { tone: "warn", title: "No LLM is configured on the server" },
  llm_error: { tone: "error", title: "The LLM request failed" },
  invalid_output: { tone: "error", title: "The LLM's answer was rejected" },
  budget_exceeded: { tone: "warn", title: "Daily LLM budget reached" },
};

function EvidenceChip({ id, onOpen }: { id: string; onOpen: (id: string) => void }) {
  return <button onClick={() => onOpen(id)} className="rounded-md border border-accent/30 bg-accent/5 px-1.5 py-0.5 font-mono text-[11px] text-[#C3CAFF] hover:bg-accent/20">{id}</button>;
}

export default function Investigator() {
  const { projectId, project, refreshProjects } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const invParam = params.get("investigation") ? Number(params.get("investigation")) : null;
  const preInv = useAsync(() => api.investigation(invParam!), [invParam], !!invParam && !params.get("run"));
  const runId = params.get("run") ? Number(params.get("run")) : preInv.data?.run_id ?? null;
  const setRun = useCallback((id: number) => { if (params.get("run") !== String(id)) { params.set("run", String(id)); params.delete("investigation"); setParams(params, { replace: true }); } }, [params, setParams]);
  const run = useAsync(() => api.run(runId!), [runId], !!runId);
  const groups = useAsync(() => api.failureGroups(runId!), [runId], !!runId);
  const history = useAsync(() => api.investigations({ run_id: runId! }), [runId], !!runId);
  const settings = useAsync(() => api.settings(), []);
  const runProject = useAsync(() => api.project(run.data!.project_id), [run.data?.project_id], !!run.data);
  const [selected, setSelected] = useState<number[]>(() => (params.get("groups") ?? "").split(",").filter(Boolean).map(Number));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string>();
  const [evidenceKey, setEvidenceKey] = useState<string | null>(null);

  const currentId = invParam ?? history.data?.items[0]?.id ?? null;
  const inv = useAsync(() => api.investigation(currentId!), [currentId], !!currentId);
  const evidence = useAsync(() => api.evidence(currentId!), [currentId], !!currentId);

  useEffect(() => {
    if (!selected.length && groups.data) setSelected(groups.data.items.filter((g) => g.reliability === "reliable").slice(0, 3).map((g) => g.id));
  }, [groups.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const startInvestigation = async () => {
    setBusy(true); setErr(undefined);
    try {
      const res = await api.investigate(runId!, selected);
      params.set("investigation", String(res.id)); setParams(params, { replace: true });
      history.reload();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const enableLlm = async () => {
    if (!run.data) return;
    try { await api.updateProject(run.data.project_id, { llm_investigation_enabled: true }); runProject.reload(); await refreshProjects(); } catch (e) { setErr((e as Error).message); }
  };

  const llmOn = runProject.data?.llm_investigation_enabled;
  const configured = settings.data?.llm.configured;
  const focusGroups: FailureGroup[] = useMemo(() => {
    const ids = inv.data?.focus_group_ids ?? [];
    return (groups.data?.items ?? []).filter((g) => ids.includes(g.id)).sort((a, b) => ids.indexOf(a.id) - ids.indexOf(b.id));
  }, [inv.data, groups.data]);
  const groupKey = (gid: number) => `GROUP_${(inv.data?.focus_group_ids ?? []).indexOf(gid) + 1}`;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="AI investigator" title="Root-cause investigation"
        description="An LLM reads verified statistics and real records, then proposes hypotheses that must cite evidence IDs. Facts and hypotheses are labelled separately."
        actions={<RunPicker projectId={run.data?.project_id ?? projectId} value={runId} onChange={setRun} />} />

      {!runId ? (
        <EmptyState icon={<Sparkles className="h-6 w-6" />} title={project ? "No evaluation runs in this project" : "No project selected"} action={<LinkButton to="/projects">Open projects</LinkButton>}>Run an evaluation, then investigate its failure groups here.</EmptyState>
      ) : (
        <>
          <Card>
            <CardHeader title="Start an investigation" subtitle="Choose up to 4 failure groups to focus on" icon={<BrainCircuit className="h-4 w-4" />}
              action={<Button onClick={startInvestigation} loading={busy} disabled={!groups.data}>{llmOn && configured ? "Run AI investigation" : "Build evidence package"}</Button>} />
            <div className="space-y-4 p-5">
              {runProject.data && !llmOn && (
                <Notice tone="info" title="LLM investigation is off for this project">
                  Without it, Blindspot AI builds the evidence package from the statistics engine and sends nothing to an LLM. Turning it on lets an investigation send
                  the package (statistics and up to about 40 dataset excerpts) to {settings.data?.llm.provider ?? "the configured provider"} ({settings.data?.llm.model}).
                  <div className="mt-2"><Button size="sm" variant="secondary" onClick={enableLlm}>Turn on for this project</Button></div>
                </Notice>
              )}
              {llmOn && settings.data && !configured && (
                <Notice tone="warn" title="No LLM API key on the server">Set OPENAI_API_KEY (or LLM_API_KEY for an OpenAI-compatible provider) in the backend environment. Statistical analysis and evidence keep working without it.</Notice>
              )}
              <div className="flex flex-wrap gap-2">
                {(groups.data?.items ?? []).map((g) => {
                  const on = selected.includes(g.id);
                  return (
                    <button key={g.id} onClick={() => setSelected((s) => (on ? s.filter((x) => x !== g.id) : [...s, g.id].slice(-4)))}
                      className={clsx("rounded-lg border px-3 py-2 text-left text-xs", on ? "border-accent bg-accent/10" : "border-line text-fg-muted hover:bg-ink-700")}>
                      <div className="font-medium text-fg">#{g.rank} {g.name}</div>
                      <div className="mt-0.5">{pct(g.error_rate)} errors · n={g.sample_size} · {g.reliability}</div>
                    </button>
                  );
                })}
                {groups.data?.items.length === 0 && <p className="text-sm text-fg-muted">This run has no failure groups, so an investigation will report insufficient evidence.</p>}
              </div>
              {err && <Notice tone="error">{err}</Notice>}
            </div>
          </Card>

          {(history.data?.items.length ?? 0) > 0 && (
            <div className="flex items-center gap-3">
              <span className="text-xs text-fg-muted">Investigation</span>
              <Select value={currentId ?? ""} onChange={(v) => { params.set("investigation", v); setParams(params, { replace: true }); }} className="w-auto">
                {history.data!.items.map((i) => <option key={i.id} value={i.id}>#{i.id} · {i.status.replace(/_/g, " ")} · {dateTime(i.created_at)}</option>)}
              </Select>
            </div>
          )}

          {currentId && (inv.loading && !inv.data ? <Spinner label="Loading investigation" /> : inv.error ? <ErrorState error={inv.error} /> : inv.data && (
            <InvestigationView inv={inv.data} evidence={evidence.data ?? []} focusGroups={focusGroups} groupKey={groupKey} onEvidence={setEvidenceKey} />
          ))}
        </>
      )}
      {evidenceKey && currentId && <EvidenceDrawer investigationId={currentId} evidenceKey={evidenceKey} onClose={() => setEvidenceKey(null)} />}
    </div>
  );
}

function InvestigationView({ inv, evidence, focusGroups, groupKey, onEvidence }: { inv: Investigation; evidence: EvidenceItem[]; focusGroups: FailureGroup[]; groupKey: (id: number) => string; onEvidence: (k: string) => void }) {
  const st = STATUS[inv.status] ?? { tone: "info" as const, title: inv.status };
  const rep = inv.report;
  const v = inv.validation ?? {};
  return (
    <div className="space-y-6">
      <Notice tone={st.tone} title={st.title}>{inv.message && inv.message !== st.title ? inv.message : null}</Notice>
      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Investigation overview" icon={<FileSearch className="h-4 w-4" />} subtitle={`Investigation #${inv.id} · run #${inv.run_id} · ${dateTime(inv.created_at)}`} />
          <div className="space-y-4 p-5">
            {rep?.summary ? <p className="text-[15px] leading-relaxed">{rep.summary}</p> : <p className="text-sm text-fg-muted">No AI summary for this investigation. The verified statistics and evidence below are still available.</p>}
            {rep?.assessment && (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Badge tone={rep.assessment.severity === "critical" ? "bad" : rep.assessment.severity === "high" ? "warn" : "accent"}>severity: {rep.assessment.severity}</Badge>
                <Badge tone="accent">priority: {rep.assessment.priority}</Badge>
                <span className="text-fg-muted">{rep.assessment.rationale}</span>
              </div>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="Run details" />
          <dl className="grid grid-cols-2 gap-3 p-5 text-xs">
            {[["Provider", inv.provider ?? "—"], ["Model", inv.model ?? "—"], ["Evidence items", int(inv.evidence_count)], ["Attempts", int(inv.attempts)],
              ["Tokens in / out", `${int(inv.prompt_tokens)} / ${int(inv.completion_tokens)}`], ["Estimated cost", `$${inv.cost_usd.toFixed(4)}`], ["Latency", inv.latency_ms ? `${(inv.latency_ms / 1000).toFixed(1)} s` : "—"],
              ["Flagged hypotheses", int(v.flagged_hypotheses ?? 0)]].map(([k, val]) => <div key={k}><dt className="text-fg-faint">{k}</dt><dd className="mt-0.5 text-fg">{val}</dd></div>)}
          </dl>
        </Card>
      </div>

      <Card className="border-ok/25">
        <CardHeader title="Verified statistical facts" icon={<BadgeCheck className="h-4 w-4 text-ok" />} subtitle="Computed by the engine from your data. The LLM did not produce these numbers." />
        <div className="divide-y divide-line">
          {focusGroups.length === 0 && <div className="px-5 py-4 text-sm text-fg-muted">No failure groups were in focus.</div>}
          {focusGroups.map((g) => (
            <div key={g.id} className="grid gap-3 px-5 py-4 md:grid-cols-[110px_1fr_auto] md:items-center">
              <span className="font-mono text-xs text-fg-faint">{groupKey(g.id)}</span>
              <div className="min-w-0"><RuleView conditions={g.conditions} compact /></div>
              <div className="text-xs tabular-nums text-fg-muted"><span className="text-bad">{pct(g.error_rate)}</span> vs {pct(g.baseline_error_rate)} ({pp(g.difference)}) · n={g.sample_size} · CI {pct(g.ci_low)}–{pct(g.ci_high)} · q={pval(g.q_value)}</div>
            </div>
          ))}
        </div>
      </Card>

      {rep?.main_pattern && (
        <Card>
          <CardHeader title="Detected pattern" icon={<Scale className="h-4 w-4" />} subtitle="The LLM's reading of the statistics" action={<Badge tone="violet">LLM interpretation</Badge>} />
          <div className="space-y-3 p-5"><p className="text-sm leading-relaxed">{rep.main_pattern.description}</p>
            <div className="flex flex-wrap gap-1.5">{rep.main_pattern.failure_groups.map((g) => <Badge key={g}>{g}</Badge>)}{rep.main_pattern.evidence_ids.map((e) => <EvidenceChip key={e} id={e} onOpen={onEvidence} />)}</div></div>
        </Card>
      )}

      {rep && rep.hypotheses.length > 0 && (
        <div className="space-y-4">
          <h2 className="flex items-center gap-2 font-display text-2xl"><Lightbulb className="h-5 w-5 text-accent-2" /> Root-cause hypotheses</h2>
          {rep.hypotheses.map((h, i) => (
            <Card key={i} className={clsx(h.validation_status === "flagged" ? "border-warn/40" : "border-accent-2/25")}>
              <div className="flex flex-col gap-2 border-b border-line px-5 py-4 md:flex-row md:items-center md:justify-between">
                <div className="font-medium">{i + 1}. {h.title}</div>
                <div className="flex flex-wrap gap-1.5"><Badge tone="violet">hypothesis · untested</Badge><Badge>{h.confidence} plausibility</Badge>
                  {h.validation_status === "flagged" ? <Badge tone="warn"><AlertTriangle className="h-3 w-3" /> flagged by validation</Badge> : <Badge tone="ok"><CheckCircle2 className="h-3 w-3" /> references verified</Badge>}</div>
              </div>
              <div className="grid gap-5 p-5 lg:grid-cols-2">
                <div className="space-y-3 lg:col-span-2"><p className="text-sm leading-relaxed text-fg">{h.explanation}</p>
                  {h.invalid_references && h.invalid_references.length > 0 && <Notice tone="warn">Removed references that do not exist: {h.invalid_references.join(", ")}</Notice>}</div>
                <div>
                  <div className="mb-2 text-xs font-medium uppercase tracking-wider text-ok">Supporting evidence</div>
                  {h.supporting_evidence.length === 0 ? <p className="text-sm text-fg-muted">No valid supporting evidence. Treat this hypothesis as unsupported.</p> :
                    <ul className="space-y-2">{h.supporting_evidence.map((e, k) => <li key={k} className="flex gap-2 text-sm"><EvidenceChip id={e.evidence_id} onOpen={onEvidence} /><span className="text-fg-muted">{e.explanation}</span></li>)}</ul>}
                </div>
                <div>
                  <div className="mb-2 text-xs font-medium uppercase tracking-wider text-warn">Counter-evidence</div>
                  {h.counter_evidence.length === 0 ? <p className="text-sm text-fg-muted">None cited.</p> :
                    <ul className="space-y-2">{h.counter_evidence.map((e, k) => <li key={k} className="flex gap-2 text-sm"><EvidenceChip id={e.evidence_id} onOpen={onEvidence} /><span className="text-fg-muted">{e.explanation}</span></li>)}</ul>}
                </div>
                <div className="rounded-lg border border-line bg-ink-900 p-3 text-sm lg:col-span-2"><span className="text-fg-faint">How to test: </span>{h.how_to_test}</div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {rep && rep.experiments.length > 0 && (
        <Card>
          <CardHeader title="Recommended experiments" icon={<FlaskConical className="h-4 w-4" />} subtitle="Added to the Experiment Lab as recommendations. Nothing is claimed until results are measured."
            action={<LinkButton to="/experiments" variant="secondary">Open Experiment Lab</LinkButton>} />
          <div className="grid gap-4 p-5 lg:grid-cols-2">
            {rep.experiments.map((e, i) => (
              <div key={i} className="rounded-lg border border-line p-4 text-sm">
                <div className="flex items-start justify-between gap-2"><div className="font-medium">{e.title}</div><Badge>{e.target_group}</Badge></div>
                <dl className="mt-3 space-y-2 text-fg-muted">
                  <div><dt className="text-[11px] uppercase tracking-wider text-fg-faint">Proposed change</dt><dd>{e.proposed_change}</dd></div>
                  <div><dt className="text-[11px] uppercase tracking-wider text-fg-faint">Test</dt><dd>{e.test_procedure}</dd></div>
                  <div><dt className="text-[11px] uppercase tracking-wider text-fg-faint">Measure</dt><dd>{e.measurement}</dd></div>
                  <div><dt className="text-[11px] uppercase tracking-wider text-fg-faint">Success criterion</dt><dd>{e.success_criterion}</dd></div>
                  <div><dt className="text-[11px] uppercase tracking-wider text-fg-faint">Expected outcome (unverified)</dt><dd>{e.expected_outcome}</dd></div>
                </dl>
                <div className="mt-3 flex flex-wrap gap-1">{e.evidence_ids.map((k) => <EvidenceChip key={k} id={k} onOpen={onEvidence} />)}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        {rep && rep.limitations.length > 0 && (
          <Card><CardHeader title="Limitations and uncertainty" icon={<ShieldAlert className="h-4 w-4" />} />
            <ul className="list-inside list-disc space-y-1 p-5 text-sm text-fg-muted">{rep.limitations.map((l) => <li key={l}>{l}</li>)}</ul></Card>
        )}
        {(v.issues?.length ?? 0) > 0 && (
          <Card className="border-warn/30"><CardHeader title="Validation report" icon={<AlertTriangle className="h-4 w-4 text-warn" />} subtitle="Checks run on the LLM output before it was saved" />
            <ul className="space-y-1.5 p-5 text-sm">{v.issues!.map((x, i) => <li key={i} className="flex gap-2"><Badge tone={x.severity === "error" ? "bad" : "warn"}>{x.severity}</Badge><span className="text-fg-muted">{x.where}: {x.message}</span></li>)}</ul>
            {(v.unverified_numbers?.length ?? 0) > 0 && <p className="px-5 pb-5 text-xs text-fg-faint">Numbers not found in the evidence: {v.unverified_numbers!.join("; ")}</p>}
          </Card>
        )}
      </div>

      <Card>
        <CardHeader title="Evidence package" subtitle="Everything the investigator was allowed to see. Click an item to open the record." />
        <div className="grid gap-2 p-5 md:grid-cols-2">
          {evidence.map((e) => (
            <button key={e.evidence_id} onClick={() => onEvidence(e.evidence_id)} className="flex items-start gap-3 rounded-lg border border-line px-3 py-2 text-left hover:bg-ink-700/40">
              <span className="font-mono text-[11px] text-[#C3CAFF]">{e.evidence_id}</span>
              <span className="min-w-0 flex-1"><span className="block truncate text-sm">{e.title}</span><span className="text-[11px] text-fg-faint">{e.kind.replace(/_/g, " ")}</span></span>
              {["subgroup_statistic", "metrics", "cluster", "dataset"].includes(e.kind) ? <Badge tone="ok">statistic</Badge> : <Badge>record</Badge>}
            </button>
          ))}
        </div>
      </Card>
      <p className="text-xs text-fg-faint">Report exports for this run are on the <Link className="text-accent hover:underline" to={`/reports?run=${inv.run_id}`}>Reports</Link> page.</p>
    </div>
  );
}

function EvidenceDrawer({ investigationId, evidenceKey, onClose }: { investigationId: number; evidenceKey: string; onClose: () => void }) {
  const item = useAsync(() => api.evidenceItem(investigationId, evidenceKey), [investigationId, evidenceKey]);
  return (
    <Drawer open onClose={onClose} title={evidenceKey} subtitle={item.data?.title}>
      {item.loading && !item.data ? <Spinner /> : item.error ? <ErrorState error={item.error.message.includes("not part") ? `${evidenceKey} does not exist in this investigation's evidence package.` : item.error} /> : (
        <div className="space-y-4">
          <Badge>{item.data!.kind.replace(/_/g, " ")}</Badge>
          {item.data!.record ? <CaseCard c={item.data!.record} defaultOpen /> : null}
          <div><div className="mb-1 text-[11px] uppercase tracking-wider text-fg-faint">Content as given to the investigator</div>
            <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-ink-900 p-3 font-mono text-[11.5px] text-fg-muted">{JSON.stringify(item.data!.content, null, 2)}</pre></div>
        </div>
      )}
    </Drawer>
  );
}
