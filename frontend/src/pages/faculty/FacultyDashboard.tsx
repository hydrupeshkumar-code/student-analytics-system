import { Link } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { dateStr, pct, useFetch } from "../../lib/hooks";
import { Card, Empty, ErrorBox, Hero, Meter, Spinner, Stat } from "../../components/ui";
import { IconAlert, IconBook, IconClipboard, IconUsers } from "../../components/icons";
import { StudyIllustration } from "../../components/Illustrations";

interface CourseStat {
  id: number; code: string; name: string; academic_year: string; semester: number; section: string; students: number;
  cp_average: number | null; pass_rate: number | null; high_risk: number; medium_risk: number; assessments: number;
  marking_open: number; ncp_entered: number;
}
interface Overview {
  courses: CourseStat[];
  at_risk: { student_id: number; name: string; roll_no: string | null; course_id: number; course: string; probability: number; reasons: string[] }[];
  marking: { course_id: number; course: string; assessment_id: number; title: string; graded: number; students: number; due_date: string | null }[];
}

export default function FacultyDashboard() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useFetch<Overview>("/faculty/overview");
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;
  const students = data.courses.reduce((a, c) => a + c.students, 0);
  const highRisk = data.courses.reduce((a, c) => a + c.high_risk, 0);

  return (
    <>
      <Hero title={`Hi ${user?.name.split(" ").slice(-1)[0]}! 👋`}
        subtitle={data.marking.length ? `You have ${data.marking.length} assessment${data.marking.length > 1 ? "s" : ""} open for marking and ${highRisk} student${highRisk === 1 ? "" : "s"} flagged for attention.` : "All marking is up to date. Check the early-warning list for students who need support."}
        actions={<><Link className="btn" to="/courses">Open my courses</Link><Link className="btn btn-ghost" to="/rubrics">Rubric library</Link></>}
        art={<StudyIllustration />} />
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <Stat label="Active courses" value={data.courses.length} icon={<IconBook />} tone="violet" />
        <Stat label="Enrolments" value={students} icon={<IconUsers />} tone="blue" />
        <Stat label="Marking open" value={data.marking.length} icon={<IconClipboard />} tone="amber" />
        <Stat label="High-risk students" value={highRisk} icon={<IconAlert />} tone="coral" />
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <Card title="My courses" subtitle="CP average so far and early-warning counts" pad={false}>
          {data.courses.length === 0 ? <Empty title="No courses assigned">Ask the administrator to assign you as course faculty.</Empty> : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Course</th><th className="r">Students</th><th>CP avg</th><th className="r">At risk</th></tr></thead>
              <tbody>{data.courses.map((c) => (
                <tr key={c.id}>
                  <td><Link to={`/courses/${c.id}`}><strong>{c.code}</strong></Link> <span className="text-2">{c.name}</span>
                    <div className="small muted">{c.academic_year} · Sem {c.semester} · Sec {c.section}</div></td>
                  <td className="r num">{c.students}</td>
                  <td style={{ minWidth: 130 }}><div className="row" style={{ flexWrap: "nowrap" }}><Meter value={c.cp_average} /><span className="small num">{pct(c.cp_average, 0)}</span></div></td>
                  <td className="r">{c.high_risk ? <span className="badge badge-bad">{c.high_risk} high</span> : <span className="muted small">none</span>}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>

        <div className="stack">
          <Card title="Marking in progress" pad={false}>
            {data.marking.length === 0 ? <Empty title="Nothing to mark">Open marking on an assessment to see it here.</Empty> : (
              <div className="table-wrap"><table className="table">
                <thead><tr><th>Assessment</th><th>Progress</th><th>Due</th><th /></tr></thead>
                <tbody>{data.marking.map((m) => (
                  <tr key={m.assessment_id}>
                    <td><strong>{m.title}</strong><div className="small muted">{m.course}</div></td>
                    <td style={{ minWidth: 120 }}><Meter value={m.graded} max={m.students || 1} /><div className="small muted num">{m.graded}/{m.students} scored</div></td>
                    <td className="small nowrap">{dateStr(m.due_date)}</td>
                    <td className="r"><Link className="btn btn-sm" to={`/courses/${m.course_id}/marks/${m.assessment_id}`}>Enter marks</Link></td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
          </Card>
          <Card title="Students needing attention" subtitle="Highest predicted risk of failing" pad={false}>
            {data.at_risk.length === 0 ? <Empty title="No high-risk students">Predictions refresh when you recompute risk in a course.</Empty> : (
              <div className="table-wrap"><table className="table">
                <thead><tr><th>Student</th><th>Course</th><th className="r">Risk</th></tr></thead>
                <tbody>{data.at_risk.slice(0, 8).map((r) => (
                  <tr key={`${r.course_id}-${r.student_id}`}>
                    <td><strong>{r.name}</strong><div className="small muted">{r.reasons[0] ?? r.roll_no}</div></td>
                    <td><Link to={`/courses/${r.course_id}/risk`}>{r.course}</Link></td>
                    <td className="r num"><span className="badge badge-bad">{Math.round(r.probability * 100)}%</span></td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
