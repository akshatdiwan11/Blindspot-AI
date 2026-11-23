import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import FailureDiscovery from "../pages/FailureDiscovery";
import { WorkspaceProvider } from "../hooks/useWorkspace";

const group = {
  id: 1, run_id: 2, rank: 1, name: "date_mentions ≥ 3", method: "single", conditions: [{ feature: "date_mentions", op: "between", low: 3, high: null }],
  rule_text: "date_mentions ≥ 3", sample_size: 176, failures: 90, error_rate: 0.511, baseline_error_rate: 0.174, complement_error_rate: 0.09,
  difference: 0.337, lift: 2.93, ci_low: 0.438, ci_high: 0.584, p_value: 1e-30, q_value: 1e-28, reliability: "reliable", severity: "critical", severity_score: 59.3, notes: [],
};

vi.mock("../services/api", () => ({
  api: {
    projects: vi.fn(async () => ({ items: [{ id: 2, name: "Demo", is_demo: true }], total: 1 })),
    runs: vi.fn(async () => ({ items: [{ id: 2, label: "Baseline", error_rate: 0.174, created_at: "2026-11-23T05:56:00Z", status: "completed" }], total: 1 })),
    run: vi.fn(async () => ({
      id: 2, project_id: 2, label: "Baseline", error_rate: 0.174, failure_count: 157, evaluated_records: 900, dataset_name: "demo", dataset_version: 1,
      discovery_summary: { hypotheses_tested: 166, fdr_alpha: 0.05, features_used: [], features_excluded: [], safeguards: ["Benjamini-Hochberg correction."] },
      clustering_summary: { skipped: "Too few failures to cluster." }, is_synthetic: true,
    })),
    failureGroups: vi.fn(async () => ({ items: [group], total: 1 })),
    clusters: vi.fn(async () => []),
  },
  ApiError: class extends Error {},
}));

describe("Failure discovery page", () => {
  it("shows engine statistics for each group with the rule and sample size", async () => {
    render(
      <MemoryRouter initialEntries={["/failures?run=2"]}>
        <WorkspaceProvider><FailureDiscovery /></WorkspaceProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByText("Hidden failure groups")).toBeInTheDocument();
    expect((await screen.findAllByText("51.1%")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("date_mentions ≥ 3").length).toBeGreaterThan(0);
    expect(screen.getByText("166")).toBeInTheDocument();
    expect(screen.getAllByText(/statistically reliable/).length).toBeGreaterThan(0);
  });
});
