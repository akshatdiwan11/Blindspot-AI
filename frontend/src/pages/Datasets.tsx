import { ChevronLeft, ChevronRight, Database, Play, Search, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { MappingEditor } from "../components/MappingEditor";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, Field, inputCls, Modal, Notice, PageHeader, Select, Spinner, SyntheticBadge, Tabs } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";
import type { ColumnMapping } from "../types/api";
import { ago, bytes, dateTime, int } from "../utils/format";
import { ReviewStep } from "./NewProject";

export function DatasetsList() {
  const { projects, projectId } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const [filterProject, setFilterProject] = useState<string>(params.get("upload") ?? (projectId ? String(projectId) : ""));
  const [q, setQ] = useState("");
  const list = useAsync(() => api.datasets({ project_id: filterProject ? Number(filterProject) : undefined, q: q || undefined }), [filterProject, q]);
  const [uploadOpen, setUploadOpen] = useState(!!params.get("upload"));
  const navigate = useNavigate();
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Datasets" title="Dataset explorer" description="Uploaded evaluation sets, their versions and data-quality profile."
        actions={<Button onClick={() => setUploadOpen(true)} disabled={!projects.length}><Upload className="h-4 w-4" /> Upload dataset</Button>} />
      <div className="flex flex-col gap-3 md:flex-row">
        <Select ariaLabel="Filter by project" value={filterProject} onChange={setFilterProject} className="md:w-72">
          <option value="">All projects</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </Select>
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-faint" />
          <input className={inputCls + " pl-9"} placeholder="Search datasets by name" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {list.loading && !list.data ? <Spinner /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : list.data!.items.length === 0 ? (
        <EmptyState icon={<Database className="h-6 w-6" />} title="No datasets" action={projects.length ? <Button onClick={() => setUploadOpen(true)}>Upload a dataset</Button> : <Link className="text-accent" to="/projects/new">Create a project first</Link>}>
          Upload a CSV, JSON or JSONL file with expected and actual model outputs.
        </EmptyState>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-fg-muted"><tr className="border-b border-line"><th className="px-5 py-3">Dataset</th><th className="px-3 py-3">Project</th><th className="px-3 py-3">Records</th><th className="px-3 py-3">Columns</th><th className="px-3 py-3">Missing</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Uploaded</th></tr></thead>
            <tbody className="divide-y divide-line">
              {list.data!.items.map((d) => {
                const missing = d.columns.reduce((a, c) => a + c.missing, 0);
                return (
                  <tr key={d.id} className="cursor-pointer hover:bg-ink-700/30" onClick={() => navigate(`/datasets/${d.id}`)}>
                    <td className="px-5 py-3"><div className="flex items-center gap-2"><span className="font-medium">{d.name}</span><Badge>v{d.version}</Badge>{d.is_synthetic && <SyntheticBadge />}</div><div className="text-xs text-fg-faint">{d.original_filename} · {bytes(d.size_bytes)}</div></td>
                    <td className="px-3 py-3 text-fg-muted">{projects.find((p) => p.id === d.project_id)?.name ?? `#${d.project_id}`}</td>
                    <td className="px-3 py-3">{int(d.row_count)}</td>
                    <td className="px-3 py-3">{d.columns.length}</td>
                    <td className="px-3 py-3">{int(missing)}</td>
                    <td className="px-3 py-3">{d.status === "ready" ? <Badge tone="ok">mapped</Badge> : <Badge tone="warn">needs mapping</Badge>}</td>
                    <td className="px-3 py-3 text-xs text-fg-faint">{ago(d.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
      <UploadModal open={uploadOpen} defaultProject={filterProject || (projectId ? String(projectId) : "")} onClose={() => { setUploadOpen(false); params.delete("upload"); setParams(params, { replace: true }); }}
        onDone={(id) => navigate(`/datasets/${id}`)} />
    </div>
  );
}

function UploadModal({ open, onClose, onDone, defaultProject }: { open: boolean; onClose: () => void; onDone: (id: number) => void; defaultProject: string }) {
  const { projects } = useWorkspace();
  const [pid, setPid] = useState(defaultProject);
  const [file, setFile] = useState<File>();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string>();
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => setPid(defaultProject || (projects[0] ? String(projects[0].id) : "")), [defaultProject, projects, open]);
  const submit = async () => {
    if (!pid || !file) { setErr("Choose a project and a file."); return; }
    setBusy(true); setErr(undefined);
    try { const ds = await api.upload(Number(pid), file, name || undefined); onDone(ds.id); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title="Upload dataset" footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={submit}>Upload</Button></>}>
      <div className="space-y-4">
        <Field label="Project" required><Select value={pid} onChange={setPid}>{projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
        <Field label="File" required hint="CSV, JSON or JSONL. Content is parsed as data and never executed.">
          <div className="flex items-center gap-3">
            <Button variant="secondary" type="button" onClick={() => ref.current?.click()}>Choose file</Button>
            <span className="truncate text-sm text-fg-muted">{file ? `${file.name} (${bytes(file.size)})` : "No file chosen"}</span>
            <input ref={ref} type="file" accept=".csv,.json,.jsonl,.ndjson" className="hidden" onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])} />
          </div>
        </Field>
        <Field label="Dataset name" hint="Uploading again with the same name creates a new version."><input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder={file?.name.replace(/\.[^.]+$/, "") ?? "Defaults to the file name"} /></Field>
        {err && <Notice tone="error">{err}</Notice>}
      </div>
    </Modal>
  );
}

export function DatasetDetail() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const ds = useAsync(() => api.dataset(id), [id]);
  const [tab, setTab] = useState<"preview" | "profile" | "mapping" | "versions">("preview");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const preview = useAsync(() => api.preview(id, { limit: 25, offset, q: q || undefined }), [id, offset, q]);
  const versions = useAsync(() => (ds.data ? api.datasets({ project_id: ds.data.project_id }) : Promise.resolve(undefined)), [ds.data?.project_id]);
  const [mapping, setMapping] = useState<ColumnMapping>();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string>();
  const [ok, setOk] = useState<string>();
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    if (!ds.data) return;
    const m = ds.data.column_mapping ?? ds.data.profile?.suggested_mapping;
    if (m) setMapping({ input_column: m.input_column ?? null, expected_column: m.expected_column ?? "", actual_column: m.actual_column ?? "", case_id_column: m.case_id_column ?? null, metadata_columns: m.metadata_columns ?? [] });
    if (ds.data.status === "needs_mapping") setTab("mapping");
  }, [ds.data]);

  if (ds.loading && !ds.data) return <Spinner />;
  if (ds.error) return <ErrorState error={ds.error} onRetry={ds.reload} />;
  const d = ds.data!;

  const saveMapping = async () => {
    if (!mapping) return;
    setBusy(true); setErr(undefined); setOk(undefined);
    try { await api.setMapping(d.id, mapping); ds.reload(); preview.reload(); setOk("Mapping saved. The dataset is ready to evaluate."); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const runEval = async () => {
    setBusy(true); setErr(undefined);
    try { const run = await api.runEvaluation(d.id, { label: `${d.name} v${d.version}` }); navigate(`/evaluations/${run.id}`); } catch (e) { setErr((e as Error).message); setBusy(false); }
  };
  const remove = async () => {
    try { await api.deleteDataset(d.id); navigate("/datasets"); } catch (e) { setErr((e as Error).message); }
  };
  const sameName = (versions.data?.items ?? []).filter((v) => v.name === d.name);
  const cols = Object.keys(preview.data?.sample_rows[0] ?? {}).filter((c) => c !== "_row");

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={<Link to="/datasets" className="hover:underline">Datasets</Link>} title={<>{d.name} <span className="text-fg-faint">v{d.version}</span></>}
        description={<>{int(d.row_count)} records · {d.columns.length} columns · {d.file_format.toUpperCase()} · {bytes(d.size_bytes)} · uploaded {dateTime(d.created_at)}</>}
        actions={<>{d.is_synthetic && <SyntheticBadge />}
          <Button variant="danger" onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" /></Button>
          <Button onClick={runEval} loading={busy} disabled={d.status !== "ready"} title={d.status !== "ready" ? "Map the columns first" : undefined}><Play className="h-4 w-4" /> Run evaluation</Button></>} />
      {err && <Notice tone="error">{err}</Notice>}
      {ok && <Notice tone="ok">{ok}</Notice>}
      {d.status !== "ready" && <Notice tone="warn" title="Map the columns before evaluating">Tell Blindspot AI which columns hold the expected and actual outputs.</Notice>}
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "preview", label: "Preview" }, { value: "profile", label: "Data quality" }, { value: "mapping", label: "Column mapping" }, { value: "versions", label: "Versions", count: sameName.length }]} />

      {tab === "preview" && (
        <Card>
          <div className="flex flex-col gap-3 border-b border-line p-4 md:flex-row md:items-center md:justify-between">
            <div className="relative md:w-96">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-faint" />
              <input className={inputCls + " pl-9"} placeholder="Filter rows containing…" value={q} onChange={(e) => { setOffset(0); setQ(e.target.value); }} />
            </div>
            <div className="flex items-center gap-2 text-xs text-fg-muted">
              {preview.data && <>{int(preview.data.total ? offset + 1 : 0)}–{int(Math.min(offset + 25, preview.data.total))} of {int(preview.data.total)}</>}
              <Button size="sm" variant="ghost" aria-label="Previous page" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - 25))}><ChevronLeft className="h-4 w-4" /></Button>
              <Button size="sm" variant="ghost" aria-label="Next page" disabled={!preview.data || offset + 25 >= preview.data.total} onClick={() => setOffset((o) => o + 25)}><ChevronRight className="h-4 w-4" /></Button>
            </div>
          </div>
          <div className="max-h-[560px] overflow-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-ink-900 text-fg-muted"><tr><th className="px-3 py-2">#</th>{cols.map((c) => <th key={c} className="px-3 py-2 font-medium">{c}</th>)}</tr></thead>
              <tbody className="divide-y divide-line">
                {(preview.data?.sample_rows ?? []).map((r) => <tr key={String(r._row)} className="hover:bg-ink-700/30"><td className="px-3 py-2 text-fg-faint">{r._row}</td>{cols.map((c) => <td key={c} className="max-w-[320px] truncate px-3 py-2" title={String(r[c] ?? "")}>{r[c] ?? <span className="text-fg-faint">—</span>}</td>)}</tr>)}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {tab === "profile" && d.profile && preview.data && <Card className="p-5"><ReviewStep review={{ ...preview.data, profile: d.profile }} /></Card>}
      {tab === "mapping" && mapping && (
        <Card className="p-5">
          <MappingEditor columns={d.columns} mapping={mapping} onChange={setMapping} />
          {d.profile?.mapping_check?.warnings?.map((w) => <Notice key={w} tone="warn" className="mt-3">{w}</Notice>)}
          <div className="mt-5 flex justify-end"><Button loading={busy} onClick={saveMapping}>Save mapping</Button></div>
        </Card>
      )}
      {tab === "versions" && (
        <Card>
          <CardHeader title="Upload history" subtitle={`All versions of “${d.name}” in this project`} />
          <ul className="divide-y divide-line">
            {sameName.map((v) => (
              <li key={v.id}><Link to={`/datasets/${v.id}`} className="flex items-center justify-between px-5 py-3 hover:bg-ink-700/40">
                <span className="text-sm">v{v.version} <span className="text-fg-faint">· {v.original_filename} · {int(v.row_count)} records</span></span>
                <span className="flex items-center gap-2">{v.id === d.id && <Badge tone="accent">viewing</Badge>}<span className="text-xs text-fg-faint">{dateTime(v.created_at)}</span></span>
              </Link></li>
            ))}
          </ul>
        </Card>
      )}
      <Modal open={confirm} onClose={() => setConfirm(false)} title="Delete this dataset?" footer={<><Button variant="ghost" onClick={() => setConfirm(false)}>Cancel</Button><Button variant="danger" onClick={remove}>Delete</Button></>}>
        <p className="text-sm text-fg-muted">This deletes the dataset, its stored file and every evaluation run (with failure groups and investigations) built on it.</p>
      </Modal>
    </div>
  );
}
