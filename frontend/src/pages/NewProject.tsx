import clsx from "clsx";
import { Check, FileUp, Play, UploadCloud } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MappingEditor } from "../components/MappingEditor";
import { Badge, Button, Card, Field, inputCls, Notice, PageHeader, Select } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";
import type { ColumnMapping, Dataset, DatasetPreview, ModelCategory, Project, TaskType } from "../types/api";
import { bytes, CATEGORY_LABEL, int, TASK_LABEL } from "../utils/format";

const STEPS = ["Project details", "Evaluation type", "Upload dataset", "Map columns", "Review dataset", "Configure evaluation", "Start analysis"];
const DEFAULT_TASK: Record<ModelCategory, TaskType> = { classification: "classification", text_generation: "text", question_answering: "text", structured_extraction: "json", llm_application: "text" };
const CATEGORY_HELP: Record<ModelCategory, string> = {
  classification: "Predicts one label per input (spam, intent, sentiment…).",
  text_generation: "Generates free text such as summaries or answers.",
  question_answering: "Answers questions, often from a context or retrieved documents.",
  structured_extraction: "Pulls fields out of documents, as text or JSON.",
  llm_application: "Any LLM-powered feature evaluated against reference outputs.",
};

export function Stepper({ step }: { step: number }) {
  return (
    <ol className="flex flex-wrap gap-2">
      {STEPS.map((s, i) => (
        <li key={s} className={clsx("flex items-center gap-2 rounded-full border px-3 py-1 text-xs", i < step ? "border-ok/30 text-ok" : i === step ? "border-accent bg-accent/10 text-fg" : "border-line text-fg-faint")}>
          <span className={clsx("grid h-4 w-4 place-items-center rounded-full text-[10px]", i < step ? "bg-ok/20" : i === step ? "bg-accent text-white" : "bg-ink-700")}>{i < step ? <Check className="h-3 w-3" /> : i + 1}</span>
          {s}
        </li>
      ))}
    </ol>
  );
}

export default function NewProject() {
  const navigate = useNavigate();
  const { refreshProjects, setProjectId } = useWorkspace();
  const settings = useAsync(() => api.settings(), []);
  const [step, setStep] = useState(0);
  const [err, setErr] = useState<string>();
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<ModelCategory>("structured_extraction");
  const [task, setTask] = useState<TaskType>("text");
  const [llm, setLlm] = useState(false);
  const [project, setProject] = useState<Project>();
  const [file, setFile] = useState<File>();
  const [dataset, setDataset] = useState<Dataset>();
  const [mapping, setMapping] = useState<ColumnMapping>();
  const [review, setReview] = useState<DatasetPreview>();
  const uploaded = useRef<File>();
  const [cfg, setCfg] = useState({ label: "Baseline", match: "normalized_exact", threshold: 0.8, positive_label: "", criterion: "exact", field_threshold: 1, schema: "", min_group_size: 20, clustering: true });

  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setErr(undefined);
    try { await fn(); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  const next = () => act(async () => {
    if (step === 0) {
      if (!name.trim()) throw new Error("Give the project a name.");
      setTask(DEFAULT_TASK[category]);
    }
    if (step === 1) {
      const p = project ? await api.updateProject(project.id, { name, description, llm_investigation_enabled: llm })
        : await api.createProject({ name: name.trim(), description, model_category: category, evaluation_task: task, llm_investigation_enabled: llm });
      setProject(p);
      await refreshProjects();
      setProjectId(p.id);
    }
    if (step === 2) {
      if (!file) throw new Error("Choose a CSV, JSON or JSONL file to upload.");
      if (dataset && uploaded.current === file) { setStep(3); return; }  // already uploaded this file
      const ds = await api.upload(project!.id, file);
      uploaded.current = file;
      setDataset(ds);
      const s = ds.profile!.suggested_mapping;
      setMapping({ input_column: s.input_column ?? null, expected_column: s.expected_column ?? "", actual_column: s.actual_column ?? "", case_id_column: s.case_id_column ?? null, metadata_columns: s.metadata_columns ?? [] });
    }
    if (step === 3) {
      if (!mapping?.expected_column || !mapping.actual_column) throw new Error("Choose the expected-output and actual-output columns.");
      setReview(await api.setMapping(dataset!.id, mapping));
    }
    setStep((s) => s + 1);
  });

  const start = () => act(async () => {
    let schema: unknown = null;
    if (task === "json" && cfg.schema.trim()) {
      try { schema = JSON.parse(cfg.schema); } catch { throw new Error("The JSON schema is not valid JSON."); }
    }
    const config: Record<string, unknown> = {
      task_type: task, label: cfg.label,
      text: { match: cfg.match, threshold: cfg.threshold },
      classification: { positive_label: cfg.positive_label || null },
      json: { criterion: cfg.criterion, field_threshold: cfg.field_threshold, json_schema: schema },
      discovery: { min_group_size: cfg.min_group_size },
      clustering: { enabled: cfg.clustering },
    };
    if (project && project.evaluation_task !== task) setProject(await api.updateProject(project.id, { evaluation_task: task }));
    const run = await api.runEvaluation(dataset!.id, config);
    await refreshProjects();
    navigate(`/evaluations/${run.id}`);
  });

  const columns = dataset?.columns ?? [];
  const limits = settings.data?.limits;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader eyebrow="New investigation" title="Create a project" description="Seven short steps from a raw evaluation file to discovered failure groups." />
      <Stepper step={step} />
      <Card className="p-6">
        {step === 0 && (
          <div className="grid gap-5">
            <Field label="Project name" required><input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Scholarship deadline extractor" maxLength={120} autoFocus /></Field>
            <Field label="Description"><textarea className={clsx(inputCls, "min-h-[80px]")} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What does the model do? What are you worried about?" maxLength={2000} /></Field>
            <div>
              <div className="mb-2 text-xs font-medium text-fg-muted">Model category</div>
              <div className="grid gap-3 md:grid-cols-3">
                {(Object.keys(CATEGORY_LABEL) as ModelCategory[]).map((c) => (
                  <button key={c} onClick={() => setCategory(c)} className={clsx("rounded-lg border p-4 text-left transition-colors", category === c ? "border-accent bg-accent/10" : "border-line hover:bg-ink-700")}>
                    <div className="text-sm font-medium">{CATEGORY_LABEL[c]}</div>
                    <div className="mt-1 text-xs text-fg-muted">{CATEGORY_HELP[c]}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="grid gap-6">
            <div>
              <div className="mb-2 text-xs font-medium text-fg-muted">How should outputs be compared?</div>
              <div className="grid gap-3 md:grid-cols-3">
                {(["classification", "text", "json"] as TaskType[]).map((t) => (
                  <button key={t} onClick={() => setTask(t)} className={clsx("rounded-lg border p-4 text-left", task === t ? "border-accent bg-accent/10" : "border-line hover:bg-ink-700")}>
                    <div className="text-sm font-medium">{TASK_LABEL[t]}</div>
                    <div className="mt-1 text-xs text-fg-muted">{t === "classification" ? "Accuracy, precision, recall, macro/weighted F1, confusion matrix." : t === "text" ? "Exact and normalized match, token precision/recall/F1." : "Exact JSON match, field-level accuracy, missing/extra fields, invalid JSON."}</div>
                  </button>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-line p-4">
              <label className="flex cursor-pointer items-start gap-3">
                <input type="checkbox" checked={llm} onChange={(e) => setLlm(e.target.checked)} className="mt-1 h-4 w-4 accent-[#6275FF]" />
                <div>
                  <div className="text-sm font-medium">Allow AI investigation with an external LLM</div>
                  <p className="mt-1 text-xs leading-relaxed text-fg-muted">
                    Off by default. When on, and only when you start an investigation, a package of statistics and up to about 40 excerpts from your dataset is sent to the configured LLM provider
                    ({settings.data?.llm.provider ?? "OpenAI"}, model {settings.data?.llm.model ?? "—"}). Metrics and failure discovery never use an LLM. You can change this later in project settings.
                  </p>
                  {settings.data && !settings.data.llm.configured && <p className="mt-2 text-xs text-warn">No LLM API key is configured on this server yet, so investigations will show evidence only.</p>}
                </div>
              </label>
            </div>
          </div>
        )}

        {step === 2 && <UploadStep file={file} setFile={setFile} limits={limits} />}

        {step === 3 && mapping && dataset && (
          <div className="grid gap-5">
            <Notice tone="info">We suggested a mapping from your column names. Check it: the expected and actual outputs are required, everything else is optional.</Notice>
            <MappingEditor columns={columns} mapping={mapping} onChange={setMapping} />
            <p className="text-xs text-fg-faint">Text features such as input length, date mentions, script and layout are also derived automatically from the input column.</p>
          </div>
        )}

        {(step === 4 || step === 5) && review?.mapping_check?.suggested_task && review.mapping_check.suggested_task.task !== task && (
          <Notice tone="warn">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>This file looks like a <b>{TASK_LABEL[review.mapping_check.suggested_task.task]}</b> task, but <b>{TASK_LABEL[task]}</b> is selected. {review.mapping_check.suggested_task.reason}</span>
              <Button size="sm" variant="secondary" onClick={() => setTask(review.mapping_check!.suggested_task!.task)}>Switch to {TASK_LABEL[review.mapping_check.suggested_task.task]}</Button>
            </div>
          </Notice>
        )}
        {step === 4 && review && <ReviewStep review={review} />}

        {step === 5 && (
          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Run label"><input className={inputCls} value={cfg.label} onChange={(e) => setCfg({ ...cfg, label: e.target.value })} maxLength={120} /></Field>
            <Field label="Minimum failure-group size" hint="Smaller subgroups are not tested, to avoid unreliable findings.">
              <input type="number" min={5} className={inputCls} value={cfg.min_group_size} onChange={(e) => setCfg({ ...cfg, min_group_size: Number(e.target.value) })} />
            </Field>
            {task === "text" && <>
              <Field label="A case is correct when…">
                <Select value={cfg.match} onChange={(v) => setCfg({ ...cfg, match: v })}>
                  <option value="normalized_exact">Normalized exact match (case, punctuation, articles ignored)</option>
                  <option value="exact">Exact match</option>
                  <option value="token_f1">Token F1 ≥ threshold</option>
                  <option value="similarity">Similarity ≥ threshold (semantic if available)</option>
                </Select>
              </Field>
              {(cfg.match === "token_f1" || cfg.match === "similarity") && (
                <Field label={`Threshold: ${cfg.threshold.toFixed(2)}`} hint={cfg.match === "similarity" ? "Similarity is not proof of factual correctness." : undefined}>
                  <input type="range" min={0.3} max={1} step={0.05} value={cfg.threshold} onChange={(e) => setCfg({ ...cfg, threshold: Number(e.target.value) })} className="w-full accent-[#6275FF]" />
                </Field>
              )}
            </>}
            {task === "classification" && (
              <Field label="Positive label (optional)" hint="Adds binary precision/recall for one class, for example Fraud.">
                <input className={inputCls} value={cfg.positive_label} onChange={(e) => setCfg({ ...cfg, positive_label: e.target.value })} />
              </Field>
            )}
            {task === "json" && <>
              <Field label="A case is correct when…">
                <Select value={cfg.criterion} onChange={(v) => setCfg({ ...cfg, criterion: v })}>
                  <option value="exact">The JSON matches exactly</option>
                  <option value="field_accuracy">Field accuracy ≥ threshold</option>
                </Select>
              </Field>
              {cfg.criterion === "field_accuracy" && <Field label={`Field threshold: ${cfg.field_threshold.toFixed(2)}`}><input type="range" min={0.3} max={1} step={0.05} value={cfg.field_threshold} onChange={(e) => setCfg({ ...cfg, field_threshold: Number(e.target.value) })} className="w-full accent-[#6275FF]" /></Field>}
              <div className="md:col-span-2"><Field label="Expected JSON schema (optional)" hint="type, required, properties, enum and items are checked.">
                <textarea className={clsx(inputCls, "min-h-[100px] font-mono text-xs")} value={cfg.schema} onChange={(e) => setCfg({ ...cfg, schema: e.target.value })} placeholder='{"type": "object", "required": ["total"]}' />
              </Field></div>
            </>}
            <label className="flex items-center gap-2 text-sm md:col-span-2"><input type="checkbox" checked={cfg.clustering} onChange={(e) => setCfg({ ...cfg, clustering: e.target.checked })} className="accent-[#6275FF]" /> Cluster similar failures</label>
          </div>
        )}

        {step === 6 && dataset && (
          <div className="space-y-4 text-sm">
            <p className="text-fg-muted">Ready to analyse <span className="text-fg">{dataset.name}</span> ({int(review?.mapping_check?.valid_records ?? dataset.row_count)} evaluable records) as a <span className="text-fg">{TASK_LABEL[task]}</span> task.</p>
            <ul className="list-inside list-disc space-y-1 text-fg-muted">
              <li>Metrics are computed deterministically in Python.</li>
              <li>Failure discovery tests single conditions, pairs and shallow decision-tree rules with multiple-comparison correction.</li>
              <li>{cfg.clustering ? "Failures are clustered when there are enough of them." : "Clustering is turned off."}</li>
              <li>No data is sent to an LLM by this step.</li>
            </ul>
          </div>
        )}

        {err && <Notice tone="error" className="mt-5">{err}</Notice>}
        <div className="mt-6 flex justify-between border-t border-line pt-5">
          <Button variant="ghost" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0 || busy}>Back</Button>
          {step < 6 ? <Button onClick={next} loading={busy}>Continue</Button> : <Button onClick={start} loading={busy}><Play className="h-4 w-4" /> Start analysis</Button>}
        </div>
      </Card>
    </div>
  );
}

function UploadStep({ file, setFile, limits }: { file?: File; setFile: (f: File) => void; limits?: { max_upload_mb: number; max_rows: number } }) {
  const ref = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  return (
    <div>
      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) setFile(f); }}
        onClick={() => ref.current?.click()}
        className={clsx("flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-14 text-center transition-colors", drag ? "border-accent bg-accent/5" : "border-line hover:border-fg-faint")}>
        <UploadCloud className="h-8 w-8 text-accent" />
        <div className="mt-3 text-sm font-medium">{file ? file.name : "Drop a file here or click to browse"}</div>
        <div className="mt-1 text-xs text-fg-muted">{file ? bytes(file.size) : `CSV, JSON or JSONL · up to ${limits?.max_upload_mb ?? "—"} MB and ${int(limits?.max_rows)} rows`}</div>
        <input ref={ref} type="file" accept=".csv,.json,.jsonl,.ndjson" className="hidden" data-testid="file-input" onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])} />
      </div>
      <p className="mt-3 text-xs text-fg-faint"><FileUp className="mr-1 inline h-3 w-3" />Uploaded content is treated as untrusted data: it is parsed as text, never executed, and never used as instructions.</p>
    </div>
  );
}

export function ReviewStep({ review }: { review: DatasetPreview }) {
  const p = review.profile;
  const check = review.mapping_check;
  const cols = useMemo(() => Object.keys(review.sample_rows[0] ?? {}).filter((c) => c !== "_row"), [review]);
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[["Records", int(p.total_records)], ["Columns", int(p.total_columns)], ["Missing values", int(p.missing_values)], ["Duplicate records", int(p.duplicate_records)], ["Invalid records", int(p.invalid_records)]].map(([k, v]) => (
          <div key={k} className="rounded-lg border border-line bg-ink-900 p-3"><div className="text-xs text-fg-muted">{k}</div><div className="mt-1 font-display text-2xl">{v}</div></div>
        ))}
      </div>
      {check && (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2 text-xs"><Badge tone="ok">{int(check.valid_records)} evaluable</Badge>{check.excluded_records > 0 && <Badge tone="warn">{check.excluded_records} excluded</Badge>}{check.missing_actual > 0 && <Badge tone="warn">{check.missing_actual} empty outputs</Badge>}</div>
          {check.warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
        </div>
      )}
      {p.invalid_rows.length > 0 && <Notice tone="warn" title={`${p.invalid_records} row(s) could not be read and were skipped`}>{p.invalid_rows.slice(0, 5).map((r) => `line ${r.line}: ${r.reason}`).join(" · ")}</Notice>}
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full text-left text-xs">
          <thead className="bg-ink-900 text-fg-muted"><tr><th className="px-3 py-2">Column</th><th className="px-3 py-2">Type</th><th className="px-3 py-2">Missing</th><th className="px-3 py-2">Unique</th><th className="px-3 py-2">Most common</th></tr></thead>
          <tbody className="divide-y divide-line">
            {p.columns.map((c) => (
              <tr key={c.name}><td className="px-3 py-2 font-mono text-[#C3CAFF]">{c.name}</td><td className="px-3 py-2"><Badge>{c.dtype}</Badge></td><td className="px-3 py-2">{int(c.missing)}</td><td className="px-3 py-2">{int(c.unique)}</td>
                <td className="max-w-xs truncate px-3 py-2 text-fg-muted">{(c.top_values ?? []).slice(0, 3).map((t) => `${t.value} (${t.count})`).join(", ")}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div>
        <div className="mb-2 text-xs font-medium text-fg-muted">Sample rows</div>
        <div className="max-h-80 overflow-auto rounded-lg border border-line">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-ink-900 text-fg-muted"><tr><th className="px-3 py-2">#</th>{cols.map((c) => <th key={c} className="px-3 py-2">{c}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {review.sample_rows.slice(0, 10).map((r) => (
                <tr key={String(r._row)}><td className="px-3 py-2 text-fg-faint">{r._row}</td>{cols.map((c) => <td key={c} className="max-w-[260px] truncate px-3 py-2" title={String(r[c] ?? "")}>{r[c] ?? <span className="text-fg-faint">—</span>}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
