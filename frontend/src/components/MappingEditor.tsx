import clsx from "clsx";
import { Check } from "lucide-react";
import type { ColumnMapping, ColumnProfile } from "../types/api";
import { Field, Select } from "./ui";

export function MappingEditor({ columns, mapping, onChange }: { columns: ColumnProfile[]; mapping: ColumnMapping; onChange: (m: ColumnMapping) => void }) {
  const core = [mapping.input_column, mapping.expected_column, mapping.actual_column, mapping.case_id_column];
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        {([["input_column", "Input / context column", false], ["expected_column", "Expected output (ground truth)", true], ["actual_column", "Actual model output", true], ["case_id_column", "Case ID", false]] as const).map(([key, label, req]) => (
          <Field key={key} label={label} required={req}>
            <Select value={(mapping as any)[key] ?? ""} onChange={(v) => onChange({ ...mapping, [key]: v || null, metadata_columns: mapping.metadata_columns.filter((m) => m !== v) } as ColumnMapping)}>
              {!req && <option value="">(none)</option>}
              {req && !(mapping as any)[key] && <option value="">Choose a column…</option>}
              {columns.map((c) => <option key={c.name} value={c.name}>{c.name} ({c.dtype})</option>)}
            </Select>
          </Field>
        ))}
      </div>
      <div>
        <div className="mb-2 text-xs font-medium text-fg-muted">Metadata columns to analyse</div>
        <div className="flex flex-wrap gap-2">
          {columns.filter((c) => !core.includes(c.name)).map((c) => {
            const on = mapping.metadata_columns.includes(c.name);
            return (
              <button key={c.name} type="button" onClick={() => onChange({ ...mapping, metadata_columns: on ? mapping.metadata_columns.filter((m) => m !== c.name) : [...mapping.metadata_columns, c.name] })}
                className={clsx("rounded-lg border px-3 py-1.5 text-xs", on ? "border-accent bg-accent/10" : "border-line text-fg-muted hover:bg-ink-700")}>
                {on && <Check className="mr-1 inline h-3 w-3" />}{c.name} <span className="text-fg-faint">· {c.dtype}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
