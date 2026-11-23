import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Info, Loader2, X } from "lucide-react";
import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router-dom";

export function Button({ variant = "primary", size = "md", loading, className, children, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md"; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-8 px-3 text-xs" : "h-10 px-4 text-sm",
        variant === "primary" && "bg-accent text-white hover:bg-[#5163f0]",
        variant === "secondary" && "border border-line bg-ink-700 text-fg hover:bg-ink-600",
        variant === "ghost" && "text-fg-muted hover:bg-ink-700 hover:text-fg",
        variant === "danger" && "border border-bad/40 bg-bad/10 text-bad hover:bg-bad/20",
        className,
      )}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function LinkButton({ to, variant = "primary", children, className }: { to: string; variant?: "primary" | "secondary" | "ghost"; children: ReactNode; className?: string }) {
  return (
    <Link to={to} className={clsx(
      "inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors",
      variant === "primary" && "bg-accent text-white hover:bg-[#5163f0]",
      variant === "secondary" && "border border-line bg-ink-700 text-fg hover:bg-ink-600",
      variant === "ghost" && "text-fg-muted hover:bg-ink-700 hover:text-fg",
      className,
    )}>{children}</Link>
  );
}

export function Card({ className, children, ...rest }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div {...rest} className={clsx("rounded-xl border border-line bg-ink-800 shadow-card", className)}>{children}</div>;
}

export function CardHeader({ title, subtitle, action, icon }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
      <div className="flex min-w-0 items-start gap-3">
        {icon && <div className="mt-0.5 text-accent">{icon}</div>}
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-fg">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-fg-muted">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

export function Badge({ tone = "neutral", children, className, title }: { tone?: "neutral" | "accent" | "ok" | "warn" | "bad" | "violet"; children: ReactNode; className?: string; title?: string }) {
  return (
    <span title={title} className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset", {
      "bg-ink-700 text-fg-muted ring-line": tone === "neutral",
      "bg-accent/10 text-[#9AA6FF] ring-accent/30": tone === "accent",
      "bg-ok/10 text-ok ring-ok/30": tone === "ok",
      "bg-warn/10 text-warn ring-warn/30": tone === "warn",
      "bg-bad/10 text-bad ring-bad/30": tone === "bad",
      "bg-accent-2/10 text-[#B49AFB] ring-accent-2/30": tone === "violet",
    }, className)}>{children}</span>
  );
}

export const SEVERITY_TONE = { critical: "bad", high: "warn", medium: "accent", low: "neutral" } as const;

export function SeverityBadge({ severity }: { severity: string }) {
  return <Badge tone={(SEVERITY_TONE as any)[severity] ?? "neutral"}>{severity}</Badge>;
}

export function ReliabilityBadge({ reliability }: { reliability: string }) {
  return reliability === "reliable"
    ? <Badge tone="ok" title="Significant after multiple-comparison correction, with adequate sample size">statistically reliable</Badge>
    : <Badge tone="neutral" title="Not significant after correction, small, or uncertain. Treat as a lead.">tentative lead</Badge>;
}

export function SyntheticBadge() {
  return <Badge tone="violet" title="Generated benchmark data with deliberately planted failure patterns">synthetic demo data</Badge>;
}

export function Stat({ label, value, hint, tone, icon }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "ok" | "warn" | "bad"; icon?: ReactNode }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between text-xs text-fg-muted">
        <span>{label}</span>
        {icon && <span className="text-fg-faint">{icon}</span>}
      </div>
      <div className={clsx("mt-2 font-display text-[32px] leading-none tracking-tight", tone === "ok" && "text-ok", tone === "warn" && "text-warn", tone === "bad" && "text-bad")}>{value}</div>
      {hint && <div className="mt-2 text-xs text-fg-faint">{hint}</div>}
    </Card>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-fg-muted" role="status">
      <Loader2 className="h-4 w-4 animate-spin text-accent" /> {label}…
    </div>
  );
}

export function Notice({ tone = "info", title, children, className }: { tone?: "info" | "warn" | "error" | "ok"; title?: ReactNode; children?: ReactNode; className?: string }) {
  const Icon = tone === "ok" ? CheckCircle2 : tone === "info" ? Info : AlertTriangle;
  return (
    <div role={tone === "error" ? "alert" : undefined} className={clsx("flex gap-3 rounded-lg border px-4 py-3 text-sm", {
      "border-accent/30 bg-accent/5 text-fg": tone === "info",
      "border-warn/30 bg-warn/5 text-fg": tone === "warn",
      "border-bad/40 bg-bad/5 text-fg": tone === "error",
      "border-ok/30 bg-ok/5 text-fg": tone === "ok",
    }, className)}>
      <Icon className={clsx("mt-0.5 h-4 w-4 shrink-0", { "text-accent": tone === "info", "text-warn": tone === "warn", "text-bad": tone === "error", "text-ok": tone === "ok" })} />
      <div className="min-w-0 space-y-1">
        {title && <div className="font-medium">{title}</div>}
        {children && <div className="text-fg-muted">{children}</div>}
      </div>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error | string; onRetry?: () => void }) {
  return (
    <Notice tone="error" title="Something went wrong">
      <span>{typeof error === "string" ? error : error.message}</span>
      {onRetry && <button onClick={onRetry} className="ml-2 font-medium text-accent hover:underline">Try again</button>}
    </Notice>
  );
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line px-6 py-14 text-center">
      {icon && <div className="mb-3 rounded-full bg-ink-700 p-3 text-accent">{icon}</div>}
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <div className="mt-1 max-w-md text-sm text-fg-muted">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: ReactNode; title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-accent">{eyebrow}</div>}
        <h1 className="font-display text-[34px] leading-tight tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-fg-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Drawer({ open, onClose, title, subtitle, children, wide }: { open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className={clsx("relative flex h-full w-full flex-col border-l border-line bg-ink-800 shadow-2xl animate-fade-up", wide ? "max-w-4xl" : "max-w-2xl")}>
        <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
          <div className="min-w-0">
            <div className="text-base font-semibold">{title}</div>
            {subtitle && <div className="mt-0.5 text-xs text-fg-muted">{subtitle}</div>}
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-fg-muted hover:bg-ink-700 hover:text-fg"><X className="h-5 w-5" /></button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

export function Modal({ open, onClose, title, children, footer }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <Card className="relative w-full max-w-lg animate-fade-up">
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div className="font-semibold">{title}</div>
          <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-fg-muted hover:bg-ink-700"><X className="h-4 w-4" /></button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </Card>
    </div>
  );
}

export function Field({ label, hint, children, required }: { label: string; hint?: ReactNode; children: ReactNode; required?: boolean }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-fg-muted">{label}{required && <span className="text-bad"> *</span>}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-fg-faint">{hint}</span>}
    </label>
  );
}

export const inputCls = "w-full rounded-lg border border-line bg-ink-900 px-3 py-2 text-sm text-fg placeholder:text-fg-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/50";

export function Select({ value, onChange, children, className, ariaLabel }: { value: string | number; onChange: (v: string) => void; children: ReactNode; className?: string; ariaLabel?: string }) {
  return (
    <select aria-label={ariaLabel} value={value} onChange={(e) => onChange(e.target.value)} className={clsx(inputCls, "cursor-pointer pr-8", className)}>
      {children}
    </select>
  );
}

export function Tabs<T extends string>({ value, onChange, tabs }: { value: T; onChange: (v: T) => void; tabs: { value: T; label: ReactNode; count?: number }[] }) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-lg border border-line bg-ink-900 p-1" role="tablist">
      {tabs.map((t) => (
        <button key={t.value} role="tab" aria-selected={value === t.value} onClick={() => onChange(t.value)}
          className={clsx("whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors", value === t.value ? "bg-ink-700 text-fg" : "text-fg-muted hover:text-fg")}>
          {t.label}{t.count !== undefined && <span className="ml-1.5 text-fg-faint">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <code className={clsx("font-mono text-[12px] text-[#C3CAFF]", className)}>{children}</code>;
}

export function ProgressBar({ value, tone = "accent", marker }: { value: number; tone?: "accent" | "bad" | "ok" | "warn"; marker?: number }) {
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-ink-600">
      <div className={clsx("h-full rounded-full transition-[width] duration-700", { "bg-accent": tone === "accent", "bg-bad": tone === "bad", "bg-ok": tone === "ok", "bg-warn": tone === "warn" })}
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
      {marker !== undefined && <div className="absolute top-0 h-full w-0.5 bg-fg" style={{ left: `${marker * 100}%` }} title="Overall error rate" />}
    </div>
  );
}
