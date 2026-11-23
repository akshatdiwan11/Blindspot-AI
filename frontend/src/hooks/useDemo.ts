import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { useWorkspace } from "./useWorkspace";

/** Opens a synthetic demo project, creating it once if it does not exist yet. */
export function useDemo() {
  const navigate = useNavigate();
  const { refreshProjects, setProjectId } = useWorkspace();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string>();

  async function open(key = "deadline_extraction", target: "failures" | "evaluation" = "failures") {
    setPending(key);
    setError(undefined);
    try {
      const demos = await api.demos();
      const spec = demos.find((d) => d.key === key);
      const existing = (await api.projects()).items.find((p) => p.is_demo && p.name === spec?.name && p.latest_run_id);
      let projectId: number, runId: number;
      if (existing && existing.latest_run_id) {
        projectId = existing.id;
        runId = existing.latest_run_id;
      } else {
        const res = await api.loadDemo(key);
        projectId = res.project_id;
        runId = res.run_id;
      }
      await refreshProjects();
      setProjectId(projectId);
      navigate(target === "failures" ? `/failures?run=${runId}` : `/evaluations/${runId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(null);
    }
  }
  return { open, pending, error };
}
