import clsx from "clsx";
import { CheckCircle2, XCircle } from "lucide-react";
import { useEffect } from "react";
import type { CaseRecord, Condition, RunSummary } from "../types/api";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import { pct, dateTime } from "../utils/format";
import { Badge, Mono, Select } from "./ui";

const fmt = (x: number | null | undefined) => (x === null || x === undefined ? "?" : Number.isInteger(x) ? String(x) : x.toFixed(2));

export function conditionText(c: Condition): string {
  if (c.op === "==") return `${c.feature} = ${c.value}`;
  if (c.op === "!=") return `${c.feature} ≠ ${c.value}`;
  if (c.op === "is_missing") return `${c.feature} is missing`;
  if (c.low == null) return `${c.feature} < ${fmt(c.high)}`;
  if (c.high == null) return `${c.feature} ≥ ${fmt(c.low)}`;
  return `${fmt(c.low)} ≤ ${c.feature} < ${fmt(c.high)}`;
}

export function RuleView({ conditions, compact }: { conditions: Condition[]; compact?: boolean }) {
  return (
    <div className={clsx("flex flex-wrap items-center gap-1.5", compact && "gap-1")}>
      {conditions.map((c, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span className="text-[10px] font-semibold tracking-widest text-fg-faint">AND</span>}
          <span className="rounded-md border border-accent/25 bg-accent/5 px-2 py-0.5 font-mono text-[12px] text-[#C3CAFF]">{conditionText(c)}</span>
        </span>
      ))}
    </div>
  );
}

function Block({ label, text, tone }: { label: string; text: string | null; tone?: "ok" | "bad" }) {
  return (
    <div className="min-w-0">
      <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-fg-faint">{label}</div>
      <div className={clsx("whitespace-pre-wrap break-words rounded-md border px-3 py-2 font-mono text-[12.5px] leading-relaxed",
        tone === "ok" && "border-ok/30 bg-ok/5", tone === "bad" && "border-bad/30 bg-bad/5", !tone && "border-line bg-ink-900 text-fg-muted")}>
        {text === null || text === "" ? <span className="italic text-fg-faint">(empty)</span> : text}
      </div>
    </div>
  );
}

export function CaseCard({ c, defaultOpen, label }: { c: CaseRecord; defaultOpen?: boolean; label?: string }) {
  return (
    <details open={defaultOpen} className="group rounded-lg border border-line bg-ink-800/60 open:bg-ink-800">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3">
        {c.correct ? <CheckCircle2 className="h-4 w-4 shrink-0 text-ok" /> : <XCircle className="h-4 w-4 shrink-0 text-bad" />}
        <Mono className="shrink-0">{c.case_id}</Mono>
        {label && <Badge tone="accent">{label}</Badge>}
        {c.representative && <Badge tone="accent">representative</Badge>}
        {!c.correct && c.error_type && <Badge tone="bad">{c.error_type.replace(/_/g, " ")}</Badge>}
        <span className="min-w-0 flex-1 truncate text-xs text-fg-muted">
          expected <span className="text-fg">{(c.expected ?? "").slice(0, 60)}</span> · got <span className={c.correct ? "text-ok" : "text-bad"}>{(c.actual ?? "(empty)").slice(0, 60)}</span>
        </span>
      </summary>
      <div className="space-y-3 border-t border-line px-4 py-4">
        {c.input !== null && <Block label="Input" text={c.input} />}
        <div className="grid gap-3 md:grid-cols-2">
          <Block label="Expected output" text={c.expected} tone="ok" />
          <Block label="Actual output" text={c.actual} tone={c.correct ? "ok" : "bad"} />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(c.metadata).map(([k, v]) => <Badge key={k}>{k}: {v ?? "—"}</Badge>)}
          {Object.entries(c.details).filter(([, v]) => typeof v === "number" || typeof v === "string").slice(0, 4).map(([k, v]) =>
            <Badge key={k} tone="neutral">{k.replace(/_/g, " ")}: {typeof v === "number" ? v.toFixed(3) : String(v)}</Badge>)}
          {["missing_fields", "wrong_fields", "extra_fields"].map((k) => (Array.isArray(c.details[k]) && c.details[k].length ? <Badge key={k} tone="warn">{k.replace(/_/g, " ")}: {c.details[k].join(", ")}</Badge> : null))}
        </div>
      </div>
    </details>
  );
}

export function RunPicker({ projectId, value, onChange, label = "Evaluation run" }: { projectId: number | null; value: number | null; onChange: (id: number) => void; label?: string }) {
  const runs = useAsync(() => (projectId ? api.runs(projectId) : Promise.resolve({ items: [] as RunSummary[], total: 0, limit: 0, offset: 0 })), [projectId]);
  const items = (runs.data?.items ?? []).filter((r) => r.status === "completed");
  useEffect(() => {
    if (items.length && (value === null || !items.some((r) => r.id === value))) onChange(items[0].id);
  }, [items, value, onChange]);
  if (!items.length) return null;
  return (
    <Select ariaLabel={label} value={value ?? ""} onChange={(v) => onChange(Number(v))} className="w-auto min-w-[260px]">
      {items.map((r) => <option key={r.id} value={r.id}>Run #{r.id} · {r.label} · {pct(r.error_rate)} errors · {dateTime(r.created_at)}</option>)}
    </Select>
  );
}
