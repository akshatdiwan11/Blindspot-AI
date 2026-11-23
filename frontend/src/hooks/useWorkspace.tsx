import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../services/api";
import type { Project } from "../types/api";

interface Workspace {
  projects: Project[];
  projectId: number | null;
  project: Project | null;
  setProjectId: (id: number | null) => void;
  refreshProjects: () => Promise<void>;
  loading: boolean;
}

const Ctx = createContext<Workspace | null>(null);
const KEY = "blindspot.projectId";

function readStored(): number | null {
  try {
    const v = localStorage.getItem(KEY);
    return v ? Number(v) : null;
  } catch {
    return null;
  }
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setPid] = useState<number | null>(readStored);
  const [loading, setLoading] = useState(true);

  const setProjectId = useCallback((id: number | null) => {
    setPid(id);
    try { id === null ? localStorage.removeItem(KEY) : localStorage.setItem(KEY, String(id)); } catch { /* storage unavailable */ }
  }, []);

  const refreshProjects = useCallback(async () => {
    try {
      const page = await api.projects();
      setProjects(page.items);
      setPid((cur) => (cur !== null && page.items.some((p) => p.id === cur) ? cur : page.items[0]?.id ?? null));
    } catch {
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refreshProjects(); }, [refreshProjects]);

  const value = useMemo(() => ({
    projects, projectId, project: projects.find((p) => p.id === projectId) ?? null, setProjectId, refreshProjects, loading,
  }), [projects, projectId, setProjectId, refreshProjects, loading]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWorkspace(): Workspace {
  const v = useContext(Ctx);
  if (!v) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return v;
}
