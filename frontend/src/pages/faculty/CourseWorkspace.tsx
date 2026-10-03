import { Link, NavLink, Outlet, useOutletContext, useParams } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/hooks";
import type { Course } from "../../lib/types";
import { ErrorBox, Spinner } from "../../components/ui";

export interface CourseCtx { course: Course; reloadCourse: () => void; canEdit: boolean }
export const useCourse = () => useOutletContext<CourseCtx>();

const TABS = [
  ["", "Overview"], ["assessments", "Assessments"], ["marks", "Marks entry"], ["ncp", "Semester-end (NCP)"],
  ["gradebook", "Consolidated result"], ["outcomes", "COs & mapping"], ["attainment", "CO/PO attainment"],
  ["risk", "Early warning"], ["students", "Students"],
];

export default function CourseWorkspace() {
  const { courseId } = useParams();
  const { user } = useAuth();
  const { data: course, error, loading, reload } = useFetch<Course>(`/courses/${courseId}`);
  if (loading && !course) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!course) return null;
  const canEdit = user?.role === "admin" || course.faculty_id === user?.id;

  return (
    <>
      <div className="crumbs"><Link to="/courses">Courses</Link> / {course.code}</div>
      <div className="row" style={{ marginBottom: 16, gap: 12 }}><span className="course-chip">{course.code}</span><h1>{course.name}</h1></div>
      <dl className="ledger-strip">
        <div><dt>Academic year</dt><dd>{course.academic_year}</dd></div>
        <div><dt>Semester · Section</dt><dd>{course.semester} · {course.section}</dd></div>
        <div><dt>Students</dt><dd className="mono">{course.student_count}</dd></div>
        <div><dt>Faculty</dt><dd>{course.faculty_name ?? <span className="muted">Unassigned</span>}</dd></div>
        <div><dt>CP / NCP</dt><dd className="mono">{course.cp_weight} / {course.ncp_weight}</dd></div>
        <div><dt>Results</dt><dd>{course.ncp_published ? <span className="badge badge-good">Published</span> : <span className="badge">Not published</span>}</dd></div>
      </dl>
      <nav className="tabs" aria-label="Course sections">
        {TABS.map(([to, label]) => (
          <NavLink key={to} to={to ? `/courses/${course.id}/${to}` : `/courses/${course.id}`} end={!to}
            className={({ isActive }) => (isActive ? "active" : "")}>{label}</NavLink>
        ))}
      </nav>
      <Outlet context={{ course, reloadCourse: reload, canEdit } satisfies CourseCtx} />
    </>
  );
}
