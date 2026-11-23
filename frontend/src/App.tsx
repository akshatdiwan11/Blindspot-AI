import { Navigate, Route, Routes } from "react-router-dom";
import { WorkspaceProvider } from "./hooks/useWorkspace";
import AppLayout from "./layouts/AppLayout";
import { DatasetDetail, DatasetsList } from "./pages/Datasets";
import { CompareRuns, EvaluationDetail, EvaluationsList } from "./pages/Evaluations";
import Experiments from "./pages/Experiments";
import FailureDiscovery from "./pages/FailureDiscovery";
import Investigator from "./pages/Investigator";
import Landing from "./pages/Landing";
import NewProject from "./pages/NewProject";
import NotFound from "./pages/NotFound";
import Overview from "./pages/Overview";
import { ProjectDetail, ProjectsList } from "./pages/Projects";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <WorkspaceProvider>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route element={<AppLayout />}>
          <Route path="/overview" element={<Overview />} />
          <Route path="/projects" element={<ProjectsList />} />
          <Route path="/projects/new" element={<NewProject />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/datasets" element={<DatasetsList />} />
          <Route path="/datasets/:id" element={<DatasetDetail />} />
          <Route path="/evaluations" element={<EvaluationsList />} />
          <Route path="/evaluations/compare" element={<CompareRuns />} />
          <Route path="/evaluations/:id" element={<EvaluationDetail />} />
          <Route path="/failures" element={<FailureDiscovery />} />
          <Route path="/investigator" element={<Investigator />} />
          <Route path="/investigations/:id" element={<InvestigationRedirect />} />
          <Route path="/experiments" element={<Experiments />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/app" element={<Navigate to="/overview" replace />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </WorkspaceProvider>
  );
}

function InvestigationRedirect() {
  const id = window.location.pathname.split("/").pop();
  return <Navigate to={`/investigator?investigation=${id}`} replace />;
}
