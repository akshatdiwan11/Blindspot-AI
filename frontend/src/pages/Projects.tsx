import { FolderKanban, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LinkButton, Modal, Notice, PageHeader, Spinner, SyntheticBadge } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useDemo } from "../hooks/useDemo";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";
import { ago, CATEGORY_LABEL, dateTime, int, pct, TASK_LABEL } from "../utils/format";

export function ProjectsList() {
  const list = useAsync(() => api.projects(), []);
  const demos = useAsync(() => api.demos(), []);
  const demo = useDemo();
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Projects" title="Investigation projects" description="Each project has its own datasets, evaluation runs, investigations and experiments."
        actions={<LinkButton to="/projects/new"><Plus className="h-4 w-4" /> New project</LinkButton>} />
      {list.loading && !list.data ? <Spinner /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : list.data!.items.length === 0 ? (
        <EmptyState icon={<FolderKanban className="h-6 w-6" />} title="No projects yet" action={<LinkButton to="/projects/new">Create your first project</LinkButton>}>
          Start by creating a project, or load one of the synthetic demos below.
        </EmptyState>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {list.data!.items.map((p) => (
            <Link key={p.id} to={`/projects/${p.id}`} className="group rounded-xl border border-line bg-ink-800 p-5 transition-colors hover:border-accent/40">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0"><div className="truncate font-medium group-hover:text-accent">{p.name}</div><div className="mt-0.5 text-xs text-fg-muted">{CATEGORY_LABEL[p.model_category]} · {TASK_LABEL[p.evaluation_task]}</div></div>
                {p.is_demo && <SyntheticBadge />}
              </div>
              <p className="mt-3 line-clamp-2 min-h-[2.5rem] text-xs text-fg-muted">{p.description || "No description."}</p>
              <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded-lg bg-ink-900 py-2"><div className="font-display text-xl">{p.run_count}</div><div className="text-fg-faint">runs</div></div>
                <div className="rounded-lg bg-ink-900 py-2"><div className="font-display text-xl">{pct(p.latest_error_rate)}</div><div className="text-fg-faint">latest errors</div></div>
                <div className="rounded-lg bg-ink-900 py-2"><div className="font-display text-xl">{p.failure_group_count}</div><div className="text-fg-faint">failure groups</div></div>
              </div>
              <div className="mt-3 text-[11px] text-fg-faint">Updated {ago(p.updated_at)}</div>
            </Link>
          ))}
        </div>
      )}
      <Card>
        <CardHeader title="Synthetic demo projects" subtitle="Generated benchmark datasets with deliberately planted failure patterns, labelled as synthetic everywhere they appear." />
        <div className="grid gap-4 p-5 md:grid-cols-3">
          {(demos.data ?? []).map((d) => (
            <div key={d.key} className="flex flex-col rounded-lg border border-line p-4">
              <div className="text-sm font-medium">{d.name}</div>
              <div className="mt-1 text-xs text-fg-muted">{int(d.records)} records · {TASK_LABEL[d.task]}</div>
              <div className="mt-2 flex flex-wrap gap-1">{d.planted_patterns.map((p) => <Badge key={p} tone="violet">{p.replace(/_/g, " ")}</Badge>)}</div>
              <Button className="mt-4" variant="secondary" size="sm" loading={demo.pending === d.key} onClick={() => demo.open(d.key, "evaluation")}>Open demo</Button>
            </div>
          ))}
        </div>
        {demo.error && <div className="px-5 pb-5"><Notice tone="error">{demo.error}</Notice></div>}
      </Card>
    </div>
  );
}

export function ProjectDetail() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const { refreshProjects, setProjectId } = useWorkspace();
  const project = useAsync(() => api.project(id), [id]);
  const datasets = useAsync(() => api.datasets({ project_id: id }), [id]);
  const runs = useAsync(() => api.runs(id), [id]);
  const invs = useAsync(() => api.investigations({ project_id: id }), [id]);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string>();
  const [pick, setPick] = useState<number[]>([]);

  if (project.loading && !project.data) return <Spinner />;
  if (project.error) return <ErrorState error={project.error} onRetry={project.reload} />;
  const p = project.data!;

  const toggleLlm = async () => {
    setErr(undefined);
    try { project.setData(await api.updateProject(p.id, { llm_investigation_enabled: !p.llm_investigation_enabled })); } catch (e) { setErr((e as Error).message); }
  };
  const remove = async () => {
    setBusy(true);
    try { await api.deleteProject(p.id); await refreshProjects(); navigate("/projects"); } catch (e) { setErr((e as Error).message); setBusy(false); }
  };

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={<Link to="/projects" className="hover:underline">Projects</Link>} title={p.name}
        description={<>{CATEGORY_LABEL[p.model_category]} · {TASK_LABEL[p.evaluation_task]} · created {dateTime(p.created_at)}{p.description && <><br />{p.description}</>}</>}
        actions={<>{p.is_demo && <SyntheticBadge />}<Button variant="secondary" onClick={() => { setProjectId(p.id); navigate("/datasets?upload=" + p.id); }}>Upload dataset</Button>
          <Button variant="danger" onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" /> Delete</Button></>} />
      {err && <Notice tone="error">{err}</Notice>}

      <Card className="flex flex-col gap-3 p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-sm font-medium">AI investigation with an external LLM: {p.llm_investigation_enabled ? <span className="text-ok">on</span> : <span className="text-fg-muted">off</span>}</div>
          <p className="mt-1 max-w-3xl text-xs text-fg-muted">When on, starting an investigation sends verified statistics and up to about 40 dataset excerpts to the configured LLM provider. Metrics and failure discovery never use an LLM.</p>
        </div>
        <Button variant={p.llm_investigation_enabled ? "secondary" : "primary"} onClick={toggleLlm}>{p.llm_investigation_enabled ? "Turn off" : "Turn on"}</Button>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Datasets" subtitle="Versions are kept when you upload a file with the same name" />
          <ul className="divide-y divide-line">
            {(datasets.data?.items ?? []).map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-3 px-5 py-3">
                <Link to={`/datasets/${d.id}`} className="min-w-0 hover:text-accent"><div className="truncate text-sm">{d.name} <span className="text-fg-faint">v{d.version}</span></div><div className="text-xs text-fg-muted">{int(d.row_count)} records · {d.file_format.toUpperCase()} · {ago(d.created_at)}</div></Link>
                {d.status === "ready" ? <Badge tone="ok">mapped</Badge> : <Link to={`/datasets/${d.id}`}><Badge tone="warn">needs mapping</Badge></Link>}
              </li>
            ))}
            {datasets.data?.items.length === 0 && <li className="px-5 py-6 text-sm text-fg-muted">No datasets yet.</li>}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Investigation history" />
          <ul className="divide-y divide-line">
            {(invs.data?.items ?? []).map((i) => (
              <li key={i.id}><Link to={`/investigator?investigation=${i.id}`} className="flex items-center justify-between px-5 py-3 hover:bg-ink-700/40">
                <span className="text-sm">Investigation #{i.id} <span className="text-fg-faint">on run #{i.run_id}</span></span>
                <span className="flex items-center gap-2"><Badge tone={i.status.startsWith("completed") ? "ok" : "neutral"}>{i.status.replace(/_/g, " ")}</Badge><span className="text-xs text-fg-faint">{ago(i.created_at)}</span></span>
              </Link></li>
            ))}
            {invs.data?.items.length === 0 && <li className="px-5 py-6 text-sm text-fg-muted">No investigations yet.</li>}
          </ul>
        </Card>
      </div>

      <Card>
        <CardHeader title="Evaluation runs" subtitle="Select two runs to compare them"
          action={<Button size="sm" variant="secondary" disabled={pick.length !== 2} onClick={() => navigate(`/evaluations/compare?a=${Math.min(...pick)}&b=${Math.max(...pick)}`)}>Compare selected</Button>} />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-fg-muted"><tr className="border-b border-line"><th className="px-5 py-2" /><th className="px-3 py-2">Run</th><th className="px-3 py-2">Dataset</th><th className="px-3 py-2">Records</th><th className="px-3 py-2">Failures</th><th className="px-3 py-2">Error rate</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">When</th></tr></thead>
            <tbody className="divide-y divide-line">
              {(runs.data?.items ?? []).map((r) => (
                <tr key={r.id} className="hover:bg-ink-700/30">
                  <td className="px-5 py-2"><input type="checkbox" aria-label={`Select run ${r.id}`} checked={pick.includes(r.id)} onChange={(e) => setPick((s) => (e.target.checked ? [...s, r.id].slice(-2) : s.filter((x) => x !== r.id)))} className="accent-[#6275FF]" /></td>
                  <td className="px-3 py-2"><Link to={`/evaluations/${r.id}`} className="text-accent hover:underline">#{r.id}</Link> <span className="text-fg-muted">{r.label}</span></td>
                  <td className="px-3 py-2 text-fg-muted">v{r.dataset_version}</td>
                  <td className="px-3 py-2">{int(r.evaluated_records)}</td>
                  <td className="px-3 py-2">{int(r.failure_count)}</td>
                  <td className="px-3 py-2">{pct(r.error_rate)}</td>
                  <td className="px-3 py-2"><Badge tone={r.status === "completed" ? "ok" : "bad"}>{r.status}</Badge></td>
                  <td className="px-3 py-2 text-xs text-fg-faint">{ago(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {runs.data?.items.length === 0 && <div className="px-5 py-6 text-sm text-fg-muted">No runs yet. Map a dataset, then run an evaluation.</div>}
        </div>
      </Card>

      <Modal open={confirm} onClose={() => setConfirm(false)} title="Delete this project?"
        footer={<><Button variant="ghost" onClick={() => setConfirm(false)}>Cancel</Button><Button variant="danger" loading={busy} onClick={remove}>Delete permanently</Button></>}>
        <p className="text-sm text-fg-muted">This permanently deletes <span className="text-fg">{p.name}</span> with all of its datasets, uploaded files, evaluation runs, investigations and experiments. This cannot be undone.</p>
      </Modal>
    </div>
  );
}
