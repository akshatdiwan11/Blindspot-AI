import type { TooltipProps } from "recharts";

export const C = { grid: "#24314A", axis: "#6B778C", text: "#98A4B8", accent: "#6275FF", violet: "#8B5CF6", ok: "#20C997", warn: "#F5B942", bad: "#F26B75", fg: "#F4F6FC" };
export const axisProps = { stroke: C.grid, tick: { fill: C.text, fontSize: 11 }, tickLine: false, axisLine: { stroke: C.grid } };

export function ChartTooltip({ active, payload, label, formatter }: TooltipProps<number, string> & { formatter?: (v: number, name: string) => string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line bg-ink-800 px-3 py-2 text-xs shadow-xl">
      {label !== undefined && <div className="mb-1 font-medium text-fg">{String(label)}</div>}
      {payload.map((p) => (
        <div key={String(p.dataKey)} className="flex items-center gap-2 text-fg-muted">
          <span className="h-2 w-2 rounded-full" style={{ background: (p.color as string) ?? C.accent }} />
          {p.name}: <span className="text-fg">{formatter ? formatter(Number(p.value), String(p.name)) : String(p.value)}</span>
        </div>
      ))}
    </div>
  );
}
