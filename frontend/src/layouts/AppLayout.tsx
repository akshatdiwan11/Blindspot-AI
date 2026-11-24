import clsx from "clsx";
import {
  Bell, Beaker, BookOpenText, ChevronDown, Database, FileBarChart2, FlaskConical, FolderKanban, Gauge, LayoutDashboard, Menu, Microscope,
  Search, Settings, Sparkles, SquareFunction, X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import { useAsync } from "../hooks/useAsync";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";
import type { SearchResult } from "../types/api";
import { ago } from "../utils/format";

const NAV = [
  { to: "/overview", label: "Overview", icon: LayoutDashboard },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/datasets", label: "Datasets", icon: Database },
  { to: "/evaluations", label: "Evaluations", icon: Gauge },
  { to: "/failures", label: "Failure Discovery", icon: Microscope },
  { to: "/investigator", label: "AI Investigator", icon: Sparkles },
  { to: "/experiments", label: "Experiments", icon: FlaskConical },
  { to: "/reports", label: "Reports", icon: FileBarChart2 },
  { to: "/settings", label: "Settings", icon: Settings },
];

function useOutside(ref: React.RefObject<HTMLElement>, onOut: () => void) {
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onOut(); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [ref, onOut]);
}

function ProjectSelector() {
  const { projects, project, setProjectId } = useWorkspace();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useOutside(ref, () => setOpen(false));
  const navigate = useNavigate();
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((o) => !o)} className="flex h-9 max-w-[240px] items-center gap-2 rounded-lg border border-line bg-ink-800 px-3 text-sm hover:bg-ink-700" aria-haspopup="listbox">
        <FolderKanban className="h-4 w-4 shrink-0 text-accent" />
        <span className="truncate">{project?.name ?? "No project yet"}</span>
        <ChevronDown className="h-4 w-4 shrink-0 text-fg-faint" />
      </button>
      {open && (
        <div className="absolute left-0 z-40 mt-2 w-72 rounded-lg border border-line bg-ink-800 p-1 shadow-2xl" role="listbox">
          {projects.map((p) => (
            <button key={p.id} onClick={() => { setProjectId(p.id); setOpen(false); }}
              className={clsx("flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm hover:bg-ink-700", p.id === project?.id && "bg-ink-700")}>
              <span className="truncate">{p.name}</span>
              {p.is_demo && <span className="ml-2 text-[10px] text-[#B49AFB]">demo</span>}
            </button>
          ))}
          <div className="my-1 border-t border-line" />
          <button onClick={() => { setOpen(false); navigate("/projects/new"); }} className="w-full rounded-md px-3 py-2 text-left text-sm text-accent hover:bg-ink-700">+ New project</button>
        </div>
      )}
    </div>
  );
}

function WorkspaceSelector() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useOutside(ref, () => setOpen(false));
  return (
    <div ref={ref} className="relative hidden lg:block">
      <button onClick={() => setOpen((o) => !o)} className="flex h-9 items-center gap-2 rounded-lg px-2 text-sm text-fg-muted hover:bg-ink-700 hover:text-fg">
        <span className="grid h-5 w-5 place-items-center rounded bg-accent-2/20 text-[10px] font-bold text-[#B49AFB]">L</span>
        Local workspace <ChevronDown className="h-4 w-4 text-fg-faint" />
      </button>
      {open && (
        <div className="absolute left-0 z-40 mt-2 w-72 rounded-lg border border-line bg-ink-800 p-3 text-xs text-fg-muted shadow-2xl">
          <div className="mb-1 font-medium text-fg">Local workspace</div>
          This deployment has a single workspace. All projects, datasets and reports on this server live here.
          Multi-workspace support with access control is listed under known limitations.
          <Link to="/settings" onClick={() => setOpen(false)} className="mt-2 block text-accent hover:underline">Workspace settings</Link>
        </div>
      )}
    </div>
  );
}

function GlobalSearch() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  useOutside(ref, () => setOpen(false));
  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); return; }
    const t = setTimeout(() => { api.search(q.trim()).then(setResults).catch(() => setResults([])); }, 200);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); inputRef.current?.focus(); } };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);
  return (
    <div ref={ref} className="relative w-full max-w-sm">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-faint" />
      <input ref={inputRef} value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
        placeholder="Search projects, datasets, failure groups…" aria-label="Search"
        className="h-9 w-full rounded-lg border border-line bg-ink-800 pl-9 pr-12 text-sm placeholder:text-fg-faint focus:border-accent focus:outline-none" />
      <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border border-line px-1.5 text-[10px] text-fg-faint sm:block">⌘K</kbd>
      {open && q.trim().length >= 2 && (
        <div className="absolute z-40 mt-2 w-full rounded-lg border border-line bg-ink-800 p-1 shadow-2xl">
          {results.length === 0 ? <div className="px-3 py-2 text-xs text-fg-muted">No matches for “{q}”.</div> : results.map((r, i) => (
            <button key={i} onClick={() => { setOpen(false); setQ(""); navigate(r.link); }} className="flex w-full flex-col rounded-md px-3 py-2 text-left hover:bg-ink-700">
              <span className="truncate text-sm">{r.title}</span>
              <span className="text-[11px] text-fg-faint">{r.type.replace("_", " ")} · {r.subtitle}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const SEEN_KEY = "blindspot.notificationsSeen";

function Notifications() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useOutside(ref, () => setOpen(false));
  const loc = useLocation();
  const feed = useAsync(() => api.activity(12), [loc.pathname]);
  const [seen, setSeen] = useState<number>(() => { try { return Number(localStorage.getItem(SEEN_KEY) ?? 0); } catch { return 0; } });
  const unread = (feed.data ?? []).filter((a) => a.id > seen).length;
  const markSeen = () => {
    const top = feed.data?.[0]?.id ?? seen;
    setSeen(top);
    try { localStorage.setItem(SEEN_KEY, String(top)); } catch { /* ignore */ }
  };
  return (
    <div ref={ref} className="relative">
      <button onClick={() => { setOpen((o) => !o); if (!open) markSeen(); }} aria-label="Notifications" className="relative grid h-9 w-9 place-items-center rounded-lg text-fg-muted hover:bg-ink-700 hover:text-fg">
        <Bell className="h-4 w-4" />
        {unread > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-bad" />}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 rounded-lg border border-line bg-ink-800 p-1 shadow-2xl">
          <div className="px-3 py-2 text-xs font-medium text-fg-muted">Recent activity</div>
          {(feed.data ?? []).length === 0 && <div className="px-3 pb-3 text-xs text-fg-faint">Nothing yet.</div>}
          {(feed.data ?? []).map((a) => (
            <Link key={a.id} to={a.link ?? "/overview"} onClick={() => setOpen(false)} className="block rounded-md px-3 py-2 hover:bg-ink-700">
              <div className="text-xs leading-snug">{a.message}</div>
              <div className="mt-0.5 text-[10px] text-fg-faint">{ago(a.created_at)}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function ProfileMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useOutside(ref, () => setOpen(false));
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((o) => !o)} aria-label="Profile menu" className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-accent to-accent-2 text-xs font-semibold text-white">You</button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-60 rounded-lg border border-line bg-ink-800 p-1 text-sm shadow-2xl">
          <div className="px-3 py-2 text-xs text-fg-muted">Signed in as the local user. This deployment has no accounts.</div>
          <Link to="/settings" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-md px-3 py-2 hover:bg-ink-700"><Settings className="h-4 w-4" /> Settings</Link>
          <a href="/api/docs" target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-md px-3 py-2 hover:bg-ink-700"><SquareFunction className="h-4 w-4" /> API documentation</a>
          <Link to="/" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-md px-3 py-2 hover:bg-ink-700"><BookOpenText className="h-4 w-4" /> Product home</Link>
        </div>
      )}
    </div>
  );
}

export default function AppLayout() {
  const [mobile, setMobile] = useState(false);
  const loc = useLocation();
  useEffect(() => setMobile(false), [loc.pathname]);
  const nav = useMemo(() => NAV, []);
  const sidebar = (
    <nav className="flex h-full flex-col gap-1 p-3">
      <Link to="/" className="mb-4 flex items-center gap-2 px-2 py-2"><Logo /></Link>
      {nav.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} className={({ isActive }) => clsx(
          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
          isActive ? "bg-ink-700 text-fg shadow-[inset_2px_0_0_#6275FF]" : "text-fg-muted hover:bg-ink-800 hover:text-fg")}>
          <Icon className="h-4 w-4" /> {label}
        </NavLink>
      ))}
      <div className="mt-auto rounded-lg border border-line bg-ink-800/60 p-3 text-[11px] leading-relaxed text-fg-faint">
        <div className="mb-1 flex items-center gap-1.5 font-medium text-fg-muted"><Beaker className="h-3.5 w-3.5" /> Facts vs. hypotheses</div>
        Numbers come from the statistics engine. AI output is labelled as hypotheses and must cite evidence.
      </div>
    </nav>
  );
  return (
    <div className="min-h-screen bg-ink">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-line bg-ink-900 lg:block">{sidebar}</aside>
      {mobile && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobile(false)} />
          <aside className="relative h-full w-64 border-r border-line bg-ink-900">
            <button className="absolute right-3 top-4 p-1 text-fg-muted" onClick={() => setMobile(false)} aria-label="Close menu"><X className="h-5 w-5" /></button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-ink/85 px-4 backdrop-blur md:px-6">
          <button className="p-1 text-fg-muted lg:hidden" onClick={() => setMobile(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
          <WorkspaceSelector />
          <ProjectSelector />
          <div className="flex flex-1 justify-end gap-2 md:justify-center"><GlobalSearch /></div>
          <Notifications />
          <ProfileMenu />
        </header>
        <main className="mx-auto max-w-[1400px] px-4 py-6 md:px-8 md:py-8">
          <TemporaryStorageBanner />
          <Outlet />
        </main>
      </div>
    </div>
  );
}

/** Shown when a production server runs without a database URL and keeps data in a temporary SQLite file. */
function TemporaryStorageBanner() {
  const s = useAsync(() => api.settings(), []);
  if (s.data?.database !== "sqlite" || s.data.environment !== "production") return null;
  return (
    <div className="mb-6 rounded-lg border border-warn/30 bg-warn/10 px-4 py-3 text-sm text-fg-muted">
      <span className="font-medium text-warn">Temporary storage.</span> This server has no database connected, so projects and
      uploads are cleared whenever it restarts. Set <code className="font-mono text-xs text-fg">DATABASE_URL</code> to a PostgreSQL
      database to keep them.
    </div>
  );
}
