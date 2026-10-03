import { createBrowserRouter, Navigate, RouterProvider, useRouteError, type RouteObject } from "react-router-dom";
import { useAuth } from "./lib/auth";
import type { Role } from "./lib/types";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import Login from "./pages/Login";
import Account, { ForcePasswordChange } from "./pages/Account";
import FacultyDashboard from "./pages/faculty/FacultyDashboard";
import Courses from "./pages/faculty/Courses";
import CourseWorkspace from "./pages/faculty/CourseWorkspace";
import CourseOverview from "./pages/faculty/CourseOverview";
import Assessments from "./pages/faculty/Assessments";
import MarksEntry, { MarksPicker } from "./pages/faculty/MarksEntry";
import NcpEntry from "./pages/faculty/NcpEntry";
import Gradebook from "./pages/faculty/Gradebook";
import Outcomes from "./pages/faculty/Outcomes";
import Attainment from "./pages/faculty/Attainment";
import Risk from "./pages/faculty/Risk";
import Students from "./pages/faculty/Students";
import Rubrics from "./pages/faculty/Rubrics";
import StudentDashboard from "./pages/student/StudentDashboard";
import StudentCourse from "./pages/student/StudentCourse";
import AdminDashboard from "./pages/admin/AdminDashboard";
import Users from "./pages/admin/Users";
import Programs from "./pages/admin/Programs";
import ProgramAttainment from "./pages/admin/ProgramAttainment";
import MLModels from "./pages/admin/MLModels";
import Settings from "./pages/admin/Settings";
import AuditLog from "./pages/admin/AuditLog";

function RouteError() {
  const err = useRouteError() as { status?: number; message?: string };
  return (
    <div className="center" style={{ minHeight: "60vh", textAlign: "center" }}>
      <div>
        <h1>{err?.status === 404 ? "Page not found" : "Something went wrong"}</h1>
        <p className="text-2" style={{ margin: "8px 0 16px" }}>{err?.status === 404 ? "The page you opened does not exist." : err?.message ?? "Please reload the page."}</p>
        <a className="btn btn-primary" href="/">Go to dashboard</a>
      </div>
    </div>
  );
}

const courseRoutes: RouteObject = {
  path: "courses/:courseId",
  element: <CourseWorkspace />,
  children: [
    { index: true, element: <CourseOverview /> },
    { path: "assessments", element: <Assessments /> },
    { path: "marks", element: <MarksPicker /> },
    { path: "marks/:assessmentId", element: <MarksEntry /> },
    { path: "ncp", element: <NcpEntry /> },
    { path: "gradebook", element: <Gradebook /> },
    { path: "outcomes", element: <Outcomes /> },
    { path: "attainment", element: <Attainment /> },
    { path: "risk", element: <Risk /> },
    { path: "students", element: <Students /> },
  ],
};

const byRole: Record<Role, RouteObject[]> = {
  admin: [
    { index: true, element: <AdminDashboard /> },
    { path: "courses", element: <Courses /> },
    courseRoutes,
    { path: "programs", element: <Programs /> },
    { path: "attainment", element: <ProgramAttainment /> },
    { path: "rubrics", element: <Rubrics /> },
    { path: "users", element: <Users /> },
    { path: "ml", element: <MLModels /> },
    { path: "settings", element: <Settings /> },
    { path: "audit", element: <AuditLog /> },
  ],
  faculty: [
    { index: true, element: <FacultyDashboard /> },
    { path: "courses", element: <Courses /> },
    courseRoutes,
    { path: "rubrics", element: <Rubrics /> },
  ],
  student: [
    { index: true, element: <StudentDashboard /> },
    { path: "my/courses/:courseId", element: <StudentCourse /> },
  ],
};

const routerCache = new Map<string, ReturnType<typeof createBrowserRouter>>();
function routerFor(role: Role) {
  if (!routerCache.has(role)) {
    routerCache.set(role, createBrowserRouter([{
      path: "/", element: <Layout />, errorElement: <RouteError />,
      children: [...byRole[role], { path: "account", element: <Account /> }, { path: "*", element: <Navigate to="/" replace /> }],
    }]));
  }
  return routerCache.get(role)!;
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Login />;
  if (user.must_change_password) return <ForcePasswordChange />;
  return <RouterProvider key={user.role} router={routerFor(user.role)} />;
}
