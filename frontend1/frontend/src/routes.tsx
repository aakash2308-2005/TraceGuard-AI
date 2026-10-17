import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Loading } from "./components/common";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { CaseListPage } from "./pages/CaseListPage";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { InvestigatePage } from "./pages/InvestigatePage";

// Heavier routes are code-split so the first paint stays fast. GraphPage pulls
// in cytoscape (~800 kB); the investigation views are also deferred.
const GraphPage = lazy(() =>
  import("./pages/GraphPage").then((m) => ({ default: m.GraphPage })),
);
const InvestigationPage = lazy(() =>
  import("./pages/InvestigationPage").then((m) => ({ default: m.InvestigationPage })),
);
const ReportReviewPage = lazy(() =>
  import("./pages/ReportReviewPage").then((m) => ({ default: m.ReportReviewPage })),
);
const CaseTimelinePage = lazy(() =>
  import("./pages/CaseTimelinePage").then((m) => ({ default: m.CaseTimelinePage })),
);
const AuditPage = lazy(() => import("./pages/AuditPage").then((m) => ({ default: m.AuditPage })));
const AdminPage = lazy(() => import("./pages/AdminPage").then((m) => ({ default: m.AdminPage })));
const StatusesHelpPage = lazy(() =>
  import("./pages/StatusesHelpPage").then((m) => ({ default: m.StatusesHelpPage })),
);

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    path: "/app",
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "investigate", element: <InvestigatePage /> },
      { path: "cases", element: <CaseListPage /> },
      { path: "cases/:caseId", element: <CaseDetailPage /> },
      {
        path: "cases/:caseId/graph",
        element: (
          <Suspense fallback={<Loading label="Loading graph…" />}>
            <GraphPage />
          </Suspense>
        ),
      },
      {
        path: "cases/:caseId/timeline",
        element: (
          <Suspense fallback={<Loading label="Loading timeline…" />}>
            <CaseTimelinePage />
          </Suspense>
        ),
      },
      {
        path: "cases/:caseId/audit",
        element: (
          <Suspense fallback={<Loading label="Loading audit…" />}>
            <AuditPage />
          </Suspense>
        ),
      },
      {
        path: "investigations/:investigationId",
        element: (
          <Suspense fallback={<Loading label="Loading investigation…" />}>
            <InvestigationPage />
          </Suspense>
        ),
      },
      {
        path: "reports/:reportId",
        element: (
          <Suspense fallback={<Loading label="Loading report…" />}>
            <ReportReviewPage />
          </Suspense>
        ),
      },
      {
        path: "admin",
        element: (
          <Suspense fallback={<Loading label="Loading admin…" />}>
            <AdminPage />
          </Suspense>
        ),
      },
      {
        path: "audit-help",
        element: (
          <Suspense fallback={<Loading label="Loading…" />}>
            <StatusesHelpPage />
          </Suspense>
        ),
      },
    ],
  },
  { path: "/", element: <Navigate to="/app" replace /> },
  { path: "*", element: <Navigate to="/app" replace /> },
]);
