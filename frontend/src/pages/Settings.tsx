import { Database, KeyRound, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, CardHeader, ErrorState, Modal, Notice, PageHeader, Spinner } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";

export default function Settings() {
  const s = useAsync(() => api.settings(), []);
  const { project, refreshProjects } = useWorkspace();
  const [confirm, setConfirm] = useState(false);
  const [err, setErr] = useState<string>();
  const navigate = useNavigate();
  if (s.loading && !s.data) return <Spinner />;
  if (s.error) return <ErrorState error={s.error} onRetry={s.reload} />;
  const d = s.data!;
  const toggle = async () => {
    if (!project) return;
    try { await api.updateProject(project.id, { llm_investigation_enabled: !project.llm_investigation_enabled }); await refreshProjects(); } catch (e) { setErr((e as Error).message); }
  };
  const remove = async () => {
    if (!project) return;
    try { await api.deleteProject(project.id); await refreshProjects(); navigate("/projects"); } catch (e) { setErr((e as Error).message); }
  };
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Settings" title="Workspace settings" description="Server configuration is read from environment variables. Secrets are never shown or stored in the database." />
      {err && <Notice tone="error">{err}</Notice>}
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="LLM provider" icon={<KeyRound className="h-4 w-4" />} action={d.llm.configured ? <Badge tone="ok">API key configured</Badge> : <Badge tone="warn">not configured</Badge>} />
          <dl className="grid grid-cols-2 gap-4 p-5 text-sm">
            {[["Provider", d.llm.provider], ["Model", d.llm.model], ["Endpoint", d.llm.base_url], ["Timeout", `${d.llm.timeout_seconds} s, ${d.llm.max_retries} retries`],
              ["Price per 1M tokens", `$${d.llm.price_per_million_tokens.input} in / $${d.llm.price_per_million_tokens.output} out`], ["Daily budget", d.llm.daily_budget_usd ? `$${d.llm.daily_budget_usd.toFixed(2)} (spent $${d.llm.spent_today_usd.toFixed(4)} today)` : "no cap"]].map(([k, v]) => (
              <div key={k}><dt className="text-xs text-fg-faint">{k}</dt><dd className="mt-0.5 break-all">{v}</dd></div>
            ))}
          </dl>
          {!d.llm.configured && <div className="px-5 pb-5"><Notice tone="info">Set <code className="font-mono">OPENAI_API_KEY</code> in the backend environment (or <code className="font-mono">LLM_PROVIDER=openai_compatible</code>, <code className="font-mono">LLM_BASE_URL</code> and <code className="font-mono">LLM_API_KEY</code>) and restart the API. Everything except AI hypotheses works without a key.</Notice></div>}
        </Card>
        <Card>
          <CardHeader title="Data handling" icon={<ShieldCheck className="h-4 w-4" />} />
          <ul className="space-y-2 p-5 text-sm text-fg-muted">
            <li>Uploads are limited to <span className="text-fg">{d.limits.max_upload_mb} MB</span> and <span className="text-fg">{d.limits.max_rows.toLocaleString()} rows</span>.</li>
            <li>Uploaded content is parsed as text, never executed, and fenced as untrusted data in LLM prompts.</li>
            <li>Data retention: {d.retention_days > 0 ? <span className="text-fg">projects older than {d.retention_days} days are deleted automatically</span> : <span className="text-fg">kept until you delete it</span>} (RETENTION_DAYS).</li>
            <li>Nothing is sent to an LLM unless the project has LLM investigation turned on and you start an investigation.</li>
            <li>Failure discovery: minimum group size {d.analysis.min_group_size}, false discovery rate {Math.round(d.analysis.fdr_alpha * 100)}%. Sentence-transformer embeddings: {d.analysis.embeddings_available ? "available" : "not installed (TF-IDF is used)"}.</li>
          </ul>
        </Card>
      </div>
      <Card>
        <CardHeader title="Current project" icon={<Database className="h-4 w-4" />} subtitle={project ? project.name : "No project selected"} />
        {project ? (
          <div className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
            <div className="text-sm text-fg-muted">AI investigation with an external LLM is <span className={project.llm_investigation_enabled ? "text-ok" : "text-fg"}>{project.llm_investigation_enabled ? "on" : "off"}</span> for this project.</div>
            <div className="flex gap-2"><Button variant="secondary" onClick={toggle}>{project.llm_investigation_enabled ? "Turn off LLM investigation" : "Turn on LLM investigation"}</Button>
              <Button variant="danger" onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" /> Delete project data</Button></div>
          </div>
        ) : <div className="p-5 text-sm text-fg-muted">Select a project from the top bar.</div>}
      </Card>
      <Modal open={confirm} onClose={() => setConfirm(false)} title="Delete all data for this project?" footer={<><Button variant="ghost" onClick={() => setConfirm(false)}>Cancel</Button><Button variant="danger" onClick={remove}>Delete permanently</Button></>}>
        <p className="text-sm text-fg-muted">Deletes {project?.name} with its datasets, stored files, runs, investigations and experiments.</p>
      </Modal>
    </div>
  );
}
