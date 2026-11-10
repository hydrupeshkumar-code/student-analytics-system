import { Link } from "react-router-dom";
import { download } from "../../lib/api";
import { fmt, pct, useFetch } from "../../lib/hooks";
import type { RiskLevel } from "../../lib/types";
import { Card, Empty, ErrorBox, Meter, PageHead, ResultBadge, RiskBadge, Spinner, Stat, useToast } from "../../components/ui";

interface RiskSignal {
  risk_level: RiskLevel | null;
  risk_index: number | null;
  value_pct: number | null;
  target_pct: number;
  summary: string;
  actions: string[];
}
interface FeedbackItem {
  skill: string;
  priority: "high" | "medium" | "low";
  why: string;
  action: string;
  internship_link: string;
  recommended_books?: string[];
  course_code?: string;
  course_name?: string;
}
interface ReportCourse {
  id: number;
  code: string;
  name: string;
  semester: number;
  academic_year: string;
  credits: number;
  faculty: string | null;
  components: Record<string, number | null>;
  cp_pct: number | null;
  ncp_pct: number | null;
  final_pct: number | null;
  grade: string | null;
  passed: boolean | null;
  attendance_pct: number | null;
  internals_pct: number | null;
  attendance_risk: RiskSignal;
  internal_risk: RiskSignal;
  overall_risk: RiskLevel | null;
  assessments_released: number;
  flags: string[];
  internship_feedback: FeedbackItem[];
}
interface Report {
  student: { name: string; email: string; roll_no: string | null; program: string | null; batch: string | null; semester: number | null; section: string | null };
  summary: { courses_enrolled: number; courses_completed: number; average_internal_pct: number | null; average_attendance_pct: number | null; average_final_pct: number | null; attendance_at_risk: number; internals_at_risk: number; overall_ml_at_risk: number };
  courses: ReportCourse[];
  internship_feedback: FeedbackItem[];
  attendance_min_pct: number;
  internal_target_pct: number;
  generated_at: string;
}

function RiskIndex({ signal }: { signal: RiskSignal }) {
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="spread">
        <RiskBadge level={signal.risk_level} />
        <strong className="num">{signal.risk_index === null ? "—" : `${fmt(signal.risk_index, 0)}/100`}</strong>
      </div>
      <Meter value={signal.risk_index} color={signal.risk_level === "high" ? "var(--serious)" : undefined} />
      <p className="small text-2">{signal.summary}</p>
      {signal.actions.length > 0 && <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{signal.actions.map((a) => <li key={a}>{a}</li>)}</ul>}
    </div>
  );
}

export default function StudentReport() {
  const { data, error, loading, reload } = useFetch<Report>("/me/academic-report");
  const toast = useToast();
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;
  const s = data.summary;

  return (
    <>
      <PageHead
        crumbs={<Link to="/">My performance</Link>}
        title="My Academic Report"
        subtitle={`Individual academic progress and internship-readiness plan · ${data.student.roll_no ?? data.student.email}`}
        actions={<button className="btn btn-primary" onClick={() => download("/me/report.pdf").catch((e) => toast((e as Error).message, "error"))}>↓ Download report PDF</button>}
      />
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <Stat label="Subjects" value={s.courses_enrolled} sub={`${s.courses_completed} with final grades`} tone="violet" />
        <Stat label="Average attendance" value={s.average_attendance_pct === null ? "—" : fmt(s.average_attendance_pct, 1)} unit={s.average_attendance_pct === null ? undefined : "%"} sub={`Required: ${fmt(data.attendance_min_pct, 0)}%`} tone="blue" />
        <Stat label="Internal average" value={s.average_internal_pct === null ? "—" : fmt(s.average_internal_pct, 1)} unit={s.average_internal_pct === null ? undefined : "%"} sub={`Improvement target: ${fmt(data.internal_target_pct, 0)}%`} tone="amber" />
        <Stat label="Final average" value={s.average_final_pct === null ? "—" : fmt(s.average_final_pct, 1)} unit={s.average_final_pct === null ? undefined : "%"} sub="Published final results only" tone="green" />
      </div>

      <Card title="Separate risk predictions" subtitle="Attendance risk and internal-assessment risk are calculated independently. Risk index is a transparent 0–100 guidance score, not a probability." pad={false}>
        {!data.courses.length ? <Empty title="No enrolled subjects yet" /> : (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Subject</th><th>Attendance</th><th>Attendance risk</th><th>Internal average</th><th>Internal risk</th><th>Overall ML risk</th></tr></thead>
            <tbody>{data.courses.map((c) => (
              <tr key={c.id}>
                <td><Link to={`/my/courses/${c.id}`}><strong>{c.code}</strong> {c.name}</Link><div className="small muted">{c.academic_year} · Sem {c.semester}</div></td>
                <td className="num">{pct(c.attendance_pct, 1)}</td>
                <td><RiskBadge level={c.attendance_risk.risk_level} /><div className="small muted">Index {c.attendance_risk.risk_index === null ? "—" : fmt(c.attendance_risk.risk_index, 0)}/100</div></td>
                <td className="num">{pct(c.internals_pct, 1)}</td>
                <td><RiskBadge level={c.internal_risk.risk_level} /><div className="small muted">Index {c.internal_risk.risk_index === null ? "—" : fmt(c.internal_risk.risk_index, 0)}/100</div></td>
                <td><RiskBadge level={c.overall_risk} /></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        <div className="small muted" style={{ padding: "10px 14px", borderTop: "1px solid var(--rule)" }}>
          Current counters: {s.attendance_at_risk} subject(s) need attendance attention · {s.internals_at_risk} subject(s) need internal-mark attention · {s.overall_ml_at_risk} subject(s) flagged by the existing overall ML model.
        </div>
      </Card>

      <div className="section-title" style={{ marginTop: 18 }}><h2>Separate warnings and improvement actions</h2></div>
      <p className="text-2" style={{ marginTop: -8, marginBottom: 14 }}>Each subject has its own attendance and internal-marks warning, with practical next steps. A warning in one area does not automatically mean risk in the other.</p>
      {!data.courses.length ? null : <div className="grid grid-2">
        {data.courses.map((c) => (
          <Card key={`signals-${c.id}`} title={`${c.code} · ${c.name}`} subtitle="Independent attendance and internal assessment review">
            <div className="grid grid-2">
              <div className="stack" style={{ gap: 8 }}>
                <strong>Attendance</strong>
                <RiskIndex signal={c.attendance_risk} />
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <strong>Internal marks</strong>
                <RiskIndex signal={c.internal_risk} />
              </div>
            </div>
          </Card>
        ))}
      </div>}

      <Card title="Placement preparation checklist" subtitle="Small, consistent actions help turn academic progress into evidence employers can review.">
        <ul className="small" style={{ margin: 0, paddingLeft: 20 }}>
          <li>Build one project related to a course you enjoy. Add a short guide, pictures, a few checks, and a note about the work you did.</li>
          <li>Practise coding questions each week. Explain how you solved them and try to improve your answers.</li>
          <li>Prepare a one-page resume. Practise describing a project, introducing yourself, and answering questions about your experience.</li>
          <li>Track internships in a simple list and update your resume for each role.</li>
        </ul>
      </Card>

      <Card title="Subject-wise academic report" subtitle="Released results only. Attendance and internal scores are presented separately from the overall CP/NCP result." pad={false}>
        {!data.courses.length ? <Empty title="No academic results yet" /> : (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Subject</th><th>Quiz</th><th>Assignment</th><th>Practical</th><th>Attendance</th><th>Internals avg</th><th className="r">CP</th><th className="r">NCP</th><th className="r">Final</th><th>Grade</th><th>Result</th></tr></thead>
            <tbody>{data.courses.map((c) => (
              <tr key={c.id}>
                <td><Link to={`/my/courses/${c.id}`}><strong>{c.code}</strong><div>{c.name}</div></Link></td>
                <td className="num">{pct(c.components.quiz, 1)}</td>
                <td className="num">{pct(c.components.assignment, 1)}</td>
                <td className="num">{pct(c.components.practical, 1)}</td>
                <td className="num">{pct(c.attendance_pct, 1)}</td>
                <td className="num"><strong>{pct(c.internals_pct, 1)}</strong></td>
                <td className="r num">{pct(c.cp_pct, 1)}</td>
                <td className="r num">{pct(c.ncp_pct, 1)}</td>
                <td className="r num">{pct(c.final_pct, 1)}</td>
                <td><strong>{c.grade ?? "—"}</strong></td>
                <td><ResultBadge passed={c.passed} /></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>

      <div className="section-title" style={{ marginTop: 18 }}><h2>Internship readiness plan</h2></div>
      <p className="text-2" style={{ marginTop: -8, marginBottom: 14 }}>These actions connect your current academic signals to skills you can demonstrate during internship applications. They are preparation guidance, not a guarantee of selection.</p>
      {!data.internship_feedback.length ? <Card><Empty title="No suggestions available yet">As more subject marks are released, this plan will become more personalised.</Empty></Card> : (
        <div className="grid grid-2">
          {data.internship_feedback.map((f, i) => (
            <Card key={`${f.skill}-${f.course_code ?? i}`} title={f.skill} subtitle={`${f.course_code ? `${f.course_code} · ` : ""}${f.priority === "high" ? "Priority action" : f.priority === "low" ? "Strong performance · stretch goal" : "Build on your progress"}`}>
              <p className="small text-2" style={{ marginTop: 0 }}>{f.why}</p>
              <div className="alert alert-info" style={{ margin: "10px 0" }}><strong>Action:</strong> {f.action}</div>
              {f.recommended_books?.length ? <p className="small"><strong>Recommended books:</strong> {f.recommended_books.join(" · ")}</p> : null}
              <p className="small muted" style={{ marginBottom: 0 }}><strong>Internship relevance:</strong> {f.internship_link}</p>
            </Card>
          ))}
        </div>
      )}
      <p className="small muted" style={{ marginTop: 14 }}>Generated {new Date(data.generated_at).toLocaleString()} · Risk indexes are threshold-based; only the overall risk indicator uses the separately trained early-warning model when available.</p>
    </>
  );
}
