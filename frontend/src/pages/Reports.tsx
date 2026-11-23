import { Download, FileJson, FileSpreadsheet, FileText, FileType2 } from "lucide-react";
import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { RunPicker } from "../components/domain";
import { Card, CardHeader, EmptyState, ErrorState, LinkButton, PageHeader, Select, Spinner } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";
import { dateTime, int, pct } from "../utils/format";

const FORMATS = [
  { f: "pdf" as const, icon: FileType2, title: "PDF investigation report", text: "Printable report: metrics, failure groups, clusters, hypotheses with evidence IDs, experiments." },
  { f: "markdown" as const, icon: FileText, title: "Markdown technical report", text: "The same report as Markdown, ready for a repository, wiki or pull request." },
  { f: "json" as const, icon: FileJson, title: "JSON investigation report", text: "Machine-readable report including the full evidence package and validation results." },
  { f: "csv" as const, icon: FileSpreadsheet, title: "CSV evaluation results", text: "One row per case: outcome, error type, outputs, metadata and failure-group membership." },
];

export default function Reports() {
  const { projectId, project } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const runId = params.get("run") ? Number(params.get("run")) : null;
  const setRun = useCallback((id: number) => { params.set("run", String(id)); setParams(params, { replace: true }); }, [params, setParams]);
  const run = useAsync(() => api.run(runId!), [runId], !!runId);
  const invs = useAsync(() => api.investigations({ run_id: runId! }), [runId], !!runId);
  const invId = params.get("investigation") ?? "";
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Reports" title="Export reports" description="Every export is stamped with its evaluation run ID and timestamp."
        actions={<RunPicker projectId={run.data?.project_id ?? projectId} value={runId} onChange={setRun} />} />
      {!runId ? <EmptyState title={project ? "No evaluation runs yet" : "No project selected"} action={<LinkButton to="/projects">Open projects</LinkButton>}>Reports are generated per evaluation run.</EmptyState>
        : run.loading && !run.data ? <Spinner /> : run.error ? <ErrorState error={run.error} /> : (
          <>
            <Card className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
              <div><div className="font-medium">Run #{run.data!.id} · {run.data!.label}</div>
                <div className="text-xs text-fg-muted">{run.data!.dataset_name} v{run.data!.dataset_version} · {int(run.data!.evaluated_records)} records · {pct(run.data!.error_rate)} errors · {run.data!.failure_group_count} failure groups · {dateTime(run.data!.created_at)}</div></div>
              <div className="flex items-center gap-2"><span className="text-xs text-fg-muted">Investigation</span>
                <Select value={invId} onChange={(v) => { v ? params.set("investigation", v) : params.delete("investigation"); setParams(params, { replace: true }); }} className="w-auto">
                  <option value="">Latest ({invs.data?.items.length ? `#${invs.data.items[0].id}` : "none"})</option>
                  {(invs.data?.items ?? []).map((i) => <option key={i.id} value={i.id}>#{i.id} · {i.status.replace(/_/g, " ")}</option>)}
                </Select></div>
            </Card>
            <div className="grid gap-4 md:grid-cols-2">
              {FORMATS.map(({ f, icon: Icon, title, text }) => (
                <Card key={f}>
                  <CardHeader title={title} icon={<Icon className="h-4 w-4" />} subtitle={text} />
                  <div className="flex gap-2 p-4">
                    <a href={api.reportUrl(runId, f, true, invId ? Number(invId) : undefined)} className="inline-flex h-9 items-center gap-2 rounded-lg bg-accent px-3 text-sm font-medium text-white hover:bg-[#5163f0]"><Download className="h-4 w-4" /> Download</a>
                    {f !== "csv" && <a href={api.reportUrl(runId, f, false, invId ? Number(invId) : undefined)} target="_blank" rel="noreferrer" className="inline-flex h-9 items-center rounded-lg border border-line px-3 text-sm hover:bg-ink-700">Open</a>}
                  </div>
                </Card>
              ))}
            </div>
          </>
        )}
    </div>
  );
}
