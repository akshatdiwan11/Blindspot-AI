import clsx from "clsx";
import {
  ArrowRight, Boxes, BrainCircuit, ChartNoAxesColumn, CheckCircle2, Database, FileCheck2, FlaskConical, GitCompareArrows, Layers3,
  Microscope, Quote, ScanSearch, ShieldCheck, Sparkles, Split,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Logo } from "../components/Logo";
import { Badge, Notice } from "../components/ui";
import { useDemo } from "../hooks/useDemo";

/* Numbers in the hero visual are the engine's actual output on the bundled synthetic
   deadline-extraction benchmark (900 records, seed 20251123). They are labelled as such. */
const OVERALL = 0.826;
const SEGMENTS = [
  { rule: "date_mentions ≥ 3", acc: 0.489, n: 176 },
  { rule: "language = Hindi", acc: 0.603, n: 121 },
  { rule: "input_format = mostly_uppercase", acc: 0.66, n: 50 },
  { rule: "page_count ≥ 5", acc: 0.689, n: 103 },
  { rule: "all other cases", acc: 0.97, n: 526, rest: true },
];

function HeroVisual() {
  const [split, setSplit] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSplit(true), 1400);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="relative rounded-2xl border border-line bg-ink-800/80 p-5 shadow-card md:p-6" onMouseEnter={() => setSplit(true)}>
      <div className="mb-4 flex items-center justify-between">
        <div className="text-xs font-medium uppercase tracking-[0.14em] text-fg-faint">Deadline extraction model</div>
        <button onClick={() => setSplit((s) => !s)} className="rounded-md border border-line px-2 py-1 text-[11px] text-fg-muted hover:bg-ink-700">
          {split ? "Show overall" : "Reveal blind spots"}
        </button>
      </div>
      <div className={clsx("transition-all duration-700", split ? "opacity-40" : "opacity-100")}>
        <div className="flex items-baseline justify-between">
          <span className="text-sm text-fg-muted">Overall accuracy</span>
          <span className="font-display text-4xl">{(OVERALL * 100).toFixed(1)}%</span>
        </div>
        <div className="mt-2 h-3 overflow-hidden rounded-full bg-ink-600"><div className="h-full rounded-full bg-ok" style={{ width: `${OVERALL * 100}%` }} /></div>
      </div>
      <div className="mt-5 space-y-2.5">
        {SEGMENTS.map((s, i) => (
          <div key={s.rule} className="transition-all duration-700" style={{ opacity: split ? 1 : 0, transform: split ? "none" : "translateY(-8px)", transitionDelay: `${i * 90}ms` }}>
            <div className="mb-1 flex items-center justify-between gap-3 text-xs">
              <code className={clsx("truncate font-mono", s.rest ? "text-fg-faint" : "text-[#C3CAFF]")}>{s.rule}</code>
              <span className="shrink-0 tabular-nums text-fg-muted">{s.n} cases · <span className={s.acc < 0.75 ? "text-bad" : "text-ok"}>{(s.acc * 100).toFixed(1)}%</span></span>
            </div>
            <div className="relative h-2 overflow-hidden rounded-full bg-ink-600">
              <div className={clsx("h-full rounded-full", s.acc < 0.75 ? "bg-bad" : "bg-ok")} style={{ width: split ? `${s.acc * 100}%` : "0%", transition: "width 900ms ease" }} />
              <div className="absolute top-0 h-full w-px bg-fg/70" style={{ left: `${OVERALL * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-5 text-[11px] leading-relaxed text-fg-faint">
        Engine output on the bundled <span className="text-[#B49AFB]">synthetic benchmark</span> (900 generated records with planted failure patterns). White line: overall accuracy.
      </p>
    </div>
  );
}

const STEPS = [
  { icon: Database, title: "Upload an evaluation set", text: "CSV, JSON or JSONL with inputs, expected outputs, actual model outputs and any metadata. Map the columns; nothing is executed." },
  { icon: ChartNoAxesColumn, title: "Measure, deterministically", text: "Python computes accuracy, F1, token overlap or field-level JSON accuracy. No LLM touches a metric." },
  { icon: Microscope, title: "Discover hidden failure groups", text: "Subgroup search and shallow decision trees find slices that fail far more than the average, with FDR-corrected significance." },
  { icon: Sparkles, title: "Investigate and experiment", text: "An LLM reads the verified evidence, proposes hypotheses that cite evidence IDs, and suggests experiments you can measure." },
];

const CAPABILITIES = [
  { icon: Split, title: "Interpretable failure rules", text: "Rules like “language = Hindi AND date_mentions ≥ 3”, with sample size, Wilson intervals and q-values." },
  { icon: ShieldCheck, title: "Statistical safeguards", text: "Minimum group sizes, Benjamini–Hochberg correction, held-out validation for tree rules, leakage and overlap checks." },
  { icon: Boxes, title: "Failure clustering", text: "TF-IDF mistake signatures and k-means group similar errors, with silhouette-based model selection and honest skips." },
  { icon: ScanSearch, title: "Evidence retrieval", text: "Representative failures, similar failures outside the rule and look-alike successes, each with a stable evidence ID." },
  { icon: BrainCircuit, title: "Grounded AI investigator", text: "Strict Pydantic schemas, evidence-ID validation, number checks and prompt-injection fencing for untrusted data." },
  { icon: FlaskConical, title: "Experiment lab", text: "Track proposed changes and measure them by re-applying the failure rule to a new run. No result, no claim." },
];

const FEATURES = [
  { icon: Layers3, title: "Three task types", text: "Classification (macro/weighted F1, confusion matrix), text generation and QA (exact, normalized, token F1), structured JSON (field accuracy, invalid JSON, schema checks)." },
  { icon: GitCompareArrows, title: "Run comparison", text: "Compare any two runs with a two-proportion test, metric deltas, and per-segment error rates on the new run." },
  { icon: FileCheck2, title: "Exportable reports", text: "PDF, Markdown, JSON and per-case CSV exports stamped with run ID and timestamp." },
];

export default function Landing() {
  const demo = useDemo();
  return (
    <div className="min-h-screen overflow-x-hidden bg-ink text-fg">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[620px] bg-[radial-gradient(ellipse_at_top,rgba(98,117,255,0.16),transparent_60%)]" />
      <header className="relative mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <Logo />
        <nav className="hidden items-center gap-7 text-sm text-fg-muted md:flex">
          <a href="#how" className="hover:text-fg">How it works</a>
          <a href="#capabilities" className="hover:text-fg">Capabilities</a>
          <a href="#example" className="hover:text-fg">Example</a>
          <a href="#architecture" className="hover:text-fg">Architecture</a>
        </nav>
        <Link to="/overview" className="rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-ink-700">Open app</Link>
      </header>

      <section className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-10 md:grid-cols-[1.1fr_1fr] md:pt-16">
        <div className="animate-fade-up">
          <Badge tone="accent" className="mb-5">Model investigation platform</Badge>
          <h1 className="font-display text-[52px] leading-[1.02] tracking-tight md:text-[68px]">
            Your AI looks accurate.<br /><span className="italic text-fg-muted">But what is it missing?</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-fg-muted">
            Discover hidden failure patterns, investigate model weaknesses, and uncover opportunities to improve your AI systems.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/projects/new" className="inline-flex h-11 items-center gap-2 rounded-lg bg-accent px-5 text-sm font-medium text-white hover:bg-[#5163f0]">
              Start Investigation <ArrowRight className="h-4 w-4" />
            </Link>
            <button onClick={() => demo.open()} disabled={!!demo.pending} className="inline-flex h-11 items-center gap-2 rounded-lg border border-line bg-ink-800 px-5 text-sm font-medium hover:bg-ink-700 disabled:opacity-60">
              {demo.pending ? "Loading demo…" : "Explore Demo"}
            </button>
          </div>
          {demo.error && <Notice tone="error" className="mt-4 max-w-xl">{demo.error}</Notice>}
          <p className="mt-4 text-xs text-fg-faint">The demo uses synthetic benchmark data with deliberately planted failure patterns.</p>
        </div>
        <HeroVisual />
      </section>

      <section id="how" className="relative border-t border-line bg-ink-900/60 py-20">
        <div className="mx-auto max-w-6xl px-5">
          <SectionTitle eyebrow="How it works" title="From one accuracy number to a list of testable fixes" />
          <ol className="mt-10 grid gap-5 md:grid-cols-4">
            {STEPS.map((s, i) => (
              <li key={s.title} className="rounded-xl border border-line bg-ink-800 p-5">
                <div className="mb-4 flex items-center justify-between">
                  <s.icon className="h-5 w-5 text-accent" />
                  <span className="font-mono text-xs text-fg-faint">0{i + 1}</span>
                </div>
                <h3 className="font-medium">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-fg-muted">{s.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="capabilities" className="py-20">
        <div className="mx-auto max-w-6xl px-5">
          <SectionTitle eyebrow="Main capabilities" title="Statistics find the failures. The LLM explains, carefully." />
          <div className="mt-10 grid gap-px overflow-hidden rounded-xl border border-line bg-line md:grid-cols-3">
            {CAPABILITIES.map((c) => (
              <div key={c.title} className="bg-ink-800 p-6">
                <c.icon className="h-5 w-5 text-accent" />
                <h3 className="mt-4 font-medium">{c.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-fg-muted">{c.text}</p>
              </div>
            ))}
          </div>
          <div className="mt-6 grid gap-5 md:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-xl border border-line p-5">
                <div className="flex items-center gap-2 text-sm font-medium"><f.icon className="h-4 w-4 text-accent-2" /> {f.title}</div>
                <p className="mt-2 text-sm leading-relaxed text-fg-muted">{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="example" className="border-y border-line bg-ink-900/60 py-20">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 md:grid-cols-[1fr_1.2fr]">
          <div>
            <SectionTitle eyebrow="Example investigation" title="Facts and hypotheses, clearly separated" />
            <p className="mt-4 text-sm leading-relaxed text-fg-muted">
              The engine reports where failures concentrate. The investigator may only cite evidence IDs that exist in the package; anything else is
              removed and flagged. Every explanation stays a hypothesis until an experiment measures it.
            </p>
            <ul className="mt-6 space-y-3 text-sm text-fg-muted">
              {["Metrics and group statistics are computed in Python", "Each claim about an example cites EVIDENCE_###", "Counter-evidence is shown next to support", "Experiments start as recommendations, never results"].map((t) => (
                <li key={t} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" /> {t}</li>
              ))}
            </ul>
          </div>
          <div className="space-y-3">
            <div className="text-[11px] uppercase tracking-[0.14em] text-fg-faint">Illustrative report layout</div>
            <div className="rounded-xl border border-line bg-ink-800 p-5">
              <div className="mb-2 flex items-center gap-2"><Badge tone="ok">verified statistic</Badge><span className="text-xs text-fg-faint">from the engine</span></div>
              <code className="font-mono text-sm text-[#C3CAFF]">document_type = scholarship AND date_mentions ≥ 2</code>
              <p className="mt-2 text-sm text-fg-muted">Sample size, failures, error rate vs. baseline, 95% interval and q-value appear here, computed from your data.</p>
            </div>
            <div className="rounded-xl border border-accent-2/30 bg-accent-2/5 p-5">
              <div className="mb-2 flex items-center gap-2"><Badge tone="violet">hypothesis · untested</Badge><span className="text-xs text-fg-faint">from the LLM</span></div>
              <p className="text-sm"><Quote className="mr-1 inline h-3.5 w-3.5 text-fg-faint" />The model may be selecting the first date in the document rather than the application deadline.</p>
              <div className="mt-3 flex flex-wrap gap-1.5">{["EVIDENCE_001", "EVIDENCE_004", "EVIDENCE_009"].map((e) => <span key={e} className="rounded border border-line px-1.5 py-0.5 font-mono text-[11px] text-fg-muted">{e}</span>)}</div>
            </div>
            <div className="rounded-xl border border-line bg-ink-800 p-5">
              <div className="mb-2 flex items-center gap-2"><Badge tone="accent">recommended experiment</Badge></div>
              <p className="text-sm text-fg-muted">Add explicit date-role instructions to the prompt, re-run the same cases, and compare deadline accuracy in the failure group before and after.</p>
            </div>
          </div>
        </div>
      </section>

      <section id="architecture" className="py-20">
        <div className="mx-auto max-w-6xl px-5">
          <SectionTitle eyebrow="Architecture overview" title="A deterministic core with an optional AI layer" />
          <div className="mt-10 grid items-stretch gap-4 md:grid-cols-5">
            {[
              ["React + TypeScript", "Vite, Tailwind, Recharts. Every page reads the API."],
              ["FastAPI", "Validated requests and responses, OpenAPI docs, clean errors."],
              ["Analysis engine", "pandas, NumPy, SciPy, scikit-learn: metrics, discovery, clustering."],
              ["Evidence + LLM", "Evidence IDs, provider abstraction, strict schemas, validation."],
              ["PostgreSQL", "SQLAlchemy models and Alembic migrations. Results persist."],
            ].map(([t, d], i) => (
              <div key={t} className="relative rounded-xl border border-line bg-ink-800 p-4">
                <div className="font-mono text-[10px] text-fg-faint">layer {i + 1}</div>
                <div className="mt-1 text-sm font-medium">{t}</div>
                <p className="mt-1 text-xs leading-relaxed text-fg-muted">{d}</p>
                {i < 4 && <ArrowRight className="absolute -right-3.5 top-1/2 hidden h-4 w-4 -translate-y-1/2 text-fg-faint md:block" />}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-line bg-ink-900/60 py-20">
        <div className="mx-auto max-w-3xl px-5 text-center">
          <h2 className="font-display text-4xl tracking-tight md:text-5xl">Get started</h2>
          <p className="mx-auto mt-4 max-w-xl text-fg-muted">Create a project and upload your evaluation set, or open the synthetic demo to see a full investigation in under a minute.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link to="/projects/new" className="inline-flex h-11 items-center gap-2 rounded-lg bg-accent px-5 text-sm font-medium text-white hover:bg-[#5163f0]">Start Investigation <ArrowRight className="h-4 w-4" /></Link>
            <button onClick={() => demo.open()} disabled={!!demo.pending} className="inline-flex h-11 items-center rounded-lg border border-line bg-ink-800 px-5 text-sm font-medium hover:bg-ink-700 disabled:opacity-60">{demo.pending ? "Loading demo…" : "Explore Demo"}</button>
          </div>
        </div>
      </section>
      <footer className="border-t border-line py-8 text-center text-xs text-fg-faint">Blindspot AI · Find the failures your overall metrics hide.</footer>
    </div>
  );
}

function SectionTitle({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-[0.14em] text-accent">{eyebrow}</div>
      <h2 className="mt-2 max-w-3xl font-display text-[38px] leading-tight tracking-tight">{title}</h2>
    </div>
  );
}
