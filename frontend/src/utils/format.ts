export const pct = (x: number | null | undefined, digits = 1) => (x === null || x === undefined || Number.isNaN(x) ? "—" : `${(x * 100).toFixed(digits)}%`);
export const pp = (x: number | null | undefined) => (x === null || x === undefined ? "—" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)} pp`);
export const num = (x: number | null | undefined, digits = 3) => (x === null || x === undefined || Number.isNaN(x) ? "—" : Number.isInteger(x) ? x.toLocaleString() : x.toFixed(digits));
export const int = (x: number | null | undefined) => (x === null || x === undefined ? "—" : x.toLocaleString());
export const bytes = (b: number) => (b < 1024 ? `${b} B` : b < 1024 * 1024 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`);
export const pval = (p: number) => (p < 0.0001 ? "< 0.0001" : p.toFixed(4));

export function ago(iso: string): string {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  const s = Math.round((Date.now() - d.getTime()) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  if (s < 86400 * 30) return `${Math.round(s / 86400)} d ago`;
  return d.toLocaleDateString();
}

export const dateTime = (iso: string) => {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
};

export const titleCase = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const metricLabel = (name: string) =>
  ({
    accuracy: "Accuracy", failure_rate: "Failure rate", precision: "Precision", recall: "Recall", f1: "F1", precision_macro: "Precision (macro)",
    recall_macro: "Recall (macro)", f1_macro: "Macro F1", precision_weighted: "Precision (weighted)", recall_weighted: "Recall (weighted)",
    f1_weighted: "Weighted F1", exact_match: "Exact match", normalized_exact_match: "Normalized exact match", token_precision: "Token precision",
    token_recall: "Token recall", token_f1: "Token F1", lexical_similarity: "Lexical similarity", semantic_similarity: "Semantic similarity",
    exact_json_match: "Exact JSON match", field_accuracy: "Field accuracy", invalid_json_rate: "Invalid JSON rate", missing_fields: "Missing fields",
    extra_fields: "Extra fields", incorrect_field_values: "Incorrect field values", schema_violation_rate: "Schema violation rate",
    binary_precision: "Precision (positive class)", binary_recall: "Recall (positive class)", binary_f1: "F1 (positive class)",
    false_positives: "False positives", false_negatives: "False negatives",
  } as Record<string, string>)[name] ?? titleCase(name);

export const TASK_LABEL: Record<string, string> = { classification: "Classification", text: "Text / QA / extraction", json: "Structured JSON" };
export const CATEGORY_LABEL: Record<string, string> = {
  classification: "Classification model", text_generation: "Text generation model", question_answering: "Question answering",
  structured_extraction: "Structured extraction", llm_application: "LLM-powered application",
};
