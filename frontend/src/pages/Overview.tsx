import { Activity as ActivityIcon, ArrowRight, Boxes, FlaskConical, FolderKanban, Gauge, Microscope, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisProps, C, ChartTooltip } from "../components/charts/theme";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LinkButton, PageHeader, Spinner, Stat, SyntheticBadge } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useDemo } from "../hooks/useDemo";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";
import { ago, pct, titleCase } from "../utils/format";

export default function Overview() {
  const { projectId, project } = useWorkspace();
  // Scope everything to the selected project, so runs of different models are never mixed in one trend.
  const scope = projectId ?? undefined;
  const ov = useAsync(() => api.overview(scope), [scope]);
  const feed = useAsync(() => api.activity(12, scope), [scope]);
  const demo = useDemo();

  if (ov.loading && !ov.data) return <Spinner />;
  if (ov.error) return <ErrorState error={ov.error} onRetry={ov.reload} />;
  const d = ov.data!;
  const hasData = d.evaluation_runs > 0;
  const syntheticOnly = hasData && d.trend.every((t) => t.synthetic);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Overview" title="Model health at a glance"
        description={project ? `Every number on this page is computed from the evaluation runs of ${project.name}.` : "Every number on this page is computed from evaluation runs stored in this workspace."}
        actions={<><LinkButton to="/projects/new" variant="primary">New investigation</LinkButton></>} />

      {!hasData ? (
        <EmptyState icon={<Gauge className="h-6 w-6" />} title="No evaluation runs yet"
          action={<div className="flex flex-wrap justify-center gap-2"><LinkButton to="/projects/new">Create a project</LinkButton>
            <Button variant="secondary" loading={demo.pending === "deadline_extraction"} onClick={() => demo.open()}>Load synthetic demo</Button></div>}>
          Create a project and upload an evaluation dataset, or load the synthetic demo to see Blindspot AI find planted failure patterns.
        </EmptyState>
      ) : (
        <>
          {syntheticOnly && <div className="flex items-center gap-2 text-xs text-fg-muted"><SyntheticBadge /> All runs shown are on synthetic benchmark data.</div>}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
            <Stat label="Projects" value={d.projects} icon={<FolderKanban className="h-4 w-4" />} hint={d.demo_projects ? `${d.demo_projects} synthetic demo` : undefined} />
            <Stat label="Evaluation runs" value={d.evaluation_runs} icon={<Gauge className="h-4 w-4" />} />
            <Stat label="Latest error rate" value={pct(d.latest_run?.error_rate)} tone={(d.latest_run?.error_rate ?? 0) > 0.1 ? "warn" : "ok"}
              hint={d.latest_run ? <Link className="hover:text-fg" to={`/evaluations/${d.latest_run.id}`}>run #{d.latest_run.id} · {d.latest_run.analysis_status}</Link> : undefined} />
            <Stat label="Failure groups" value={d.failure_groups} icon={<Microscope className="h-4 w-4" />} hint={`${d.reliable_failure_groups} statistically reliable`} />
            <Stat label="Investigations" value={d.investigations_completed} icon={<Sparkles className="h-4 w-4" />} hint={`${d.investigations_total} started`} />
            <Stat label="Pending experiments" value={d.pending_experiments} icon={<FlaskConical className="h-4 w-4" />} hint={`${d.experiments.completed ?? 0} completed`} />
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader title="Model performance trend" subtitle="Failure rate of each completed evaluation run, oldest to newest" />
              {d.trend.length < 2 ? (
                <div className="flex h-64 flex-col items-center justify-center gap-1 p-6 text-center text-sm text-fg-muted">
                  <div className="font-display text-4xl text-fg">{pct(d.trend[0]?.error_rate)}</div>
                  <div>failure rate in the only run so far.</div>
                  <div className="text-xs text-fg-faint">Run the evaluation again after a change (a new prompt or model version) to see a trend.</div>
                </div>
              ) : (
              <div className="h-64 p-4">
                <ResponsiveContainer>
                  <LineChart data={d.trend.map((t) => ({ name: `#${t.run_id}`, error: t.error_rate, groups: t.failure_groups, label: t.label }))}>
                    <CartesianGrid stroke={C.grid} vertical={false} />
                    <XAxis dataKey="name" {...axisProps} />
                    <YAxis {...axisProps} tickFormatter={(v) => `${Math.round(v * 100)}%`} width={40} />
                    <Tooltip content={<ChartTooltip formatter={(v, n) => (n === "Failure rate" ? pct(v) : String(v))} />} />
                    <Line type="linear" dataKey="error" name="Failure rate" stroke={C.bad} strokeWidth={2} dot={{ r: 3, fill: C.bad }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              )}
            </Card>
            <Card>
              <CardHeader title="Error distribution" subtitle={d.latest_run ? `Failure types in run #${d.latest_run.id}` : ""} />
              <div className="h-64 p-4">
                <ResponsiveContainer>
                  <BarChart data={Object.entries(d.latest_error_types).map(([k, v]) => ({ name: titleCase(k), count: v }))} layout="vertical" margin={{ left: 10 }}>
                    <CartesianGrid stroke={C.grid} horizontal={false} />
                    <XAxis type="number" {...axisProps} allowDecimals={false} />
                    <YAxis type="category" dataKey="name" {...axisProps} width={110} />
                    <Tooltip content={<ChartTooltip />} cursor={{ fill: "#ffffff08" }} />
                    <Bar dataKey="count" name="Failures" fill={C.violet} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader title="Failure group comparison" subtitle={d.latest_run ? `Error rate of each group in run #${d.latest_run.id} vs. the overall rate` : ""}
                action={d.latest_run && <Link to={`/failures?run=${d.latest_run.id}`} className="flex items-center gap-1 text-xs text-accent hover:underline">Open <ArrowRight className="h-3 w-3" /></Link>} />
              <div className="h-72 p-4">
                {d.latest_groups.length === 0 ? <div className="grid h-full place-items-center text-sm text-fg-muted">No failure groups in the latest run.</div> : (
                  <ResponsiveContainer>
                    <BarChart data={d.latest_groups.map((g) => ({ name: g.name.length > 34 ? g.name.slice(0, 33) + "…" : g.name, group: g.error_rate, overall: g.baseline, reliability: g.reliability }))} layout="vertical" margin={{ left: 10 }}>
                      <CartesianGrid stroke={C.grid} horizontal={false} />
                      <XAxis type="number" {...axisProps} tickFormatter={(v) => `${Math.round(v * 100)}%`} domain={[0, 1]} />
                      <YAxis type="category" dataKey="name" {...axisProps} width={220} />
                      <Tooltip content={<ChartTooltip formatter={(v) => pct(v)} />} cursor={{ fill: "#ffffff08" }} />
                      <Legend verticalAlign="top" align="right" height={24} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, color: C.text }} />
                      <Bar dataKey="group" name="Group error rate (grey = tentative)" fill={C.bad} radius={[0, 4, 4, 0]}>
                        {d.latest_groups.map((g) => <Cell key={g.id} fill={g.reliability === "reliable" ? C.bad : C.axis} />)}
                      </Bar>
                      <Bar dataKey="overall" name="Overall error rate" fill={C.accent} radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Card>
            <Card>
              <CardHeader title="Recent activity" icon={<ActivityIcon className="h-4 w-4" />} />
              <ul className="max-h-72 divide-y divide-line overflow-y-auto">
                {(feed.data ?? []).map((a) => (
                  <li key={a.id}>
                    <Link to={a.link ?? "/overview"} className="block px-5 py-3 hover:bg-ink-700/50">
                      <div className="text-sm leading-snug">{a.message}</div>
                      <div className="mt-1 flex items-center gap-2 text-[11px] text-fg-faint"><Badge>{a.kind}</Badge>{ago(a.created_at)}</div>
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <Card>
            <CardHeader title="Evaluation run comparison" subtitle="Failure rate and number of failure groups for recent runs" icon={<Boxes className="h-4 w-4" />}
              action={<Link to="/evaluations" className="text-xs text-accent hover:underline">Compare two runs</Link>} />
            <div className="h-64 p-4">
              <ResponsiveContainer>
                <BarChart data={d.trend.map((t) => ({ name: projectId ? `#${t.run_id} ${t.label.slice(0, 22)}` : `#${t.run_id} ${t.project.slice(0, 18)}`, error: t.error_rate, groups: t.failure_groups }))}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="name" {...axisProps} />
                  <YAxis yAxisId="l" {...axisProps} tickFormatter={(v) => `${Math.round(v * 100)}%`} width={40} />
                  <YAxis yAxisId="r" orientation="right" {...axisProps} allowDecimals={false} width={30} />
                  <Tooltip content={<ChartTooltip formatter={(v, n) => (n === "Failure rate" ? pct(v) : String(v))} />} cursor={{ fill: "#ffffff08" }} />
                  <Legend verticalAlign="top" align="right" height={24} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, color: C.text }} />
                  <Bar yAxisId="l" dataKey="error" name="Failure rate" fill={C.bad} radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="r" dataKey="groups" name="Failure groups" fill={C.accent} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
