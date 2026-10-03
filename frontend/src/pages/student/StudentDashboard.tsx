import { Link } from "react-router-dom";
import { download } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmt, pct, useFetch } from "../../lib/hooks";
import type { RiskLevel } from "../../lib/types";
import { Card, Empty, ErrorBox, Hero, Meter, ResultBadge, RiskBadge, Spinner, Stat, useToast } from "../../components/ui";
import { IconBook, IconCap, IconStar, IconTrend } from "../../components/icons";
import { StudyIllustration } from "../../components/Illustrations";

interface MyCourse {
  id: number; code: string; name: string; semester: number; academic_year: string; credits: number; faculty: string | null;
  cp_pct: number | null; ncp_pct: number | null; final_pct: number | null; grade: string | null; passed: boolean | null;
  components: Record<string, number | null>; assessments_released: number; flags: string[]; risk_level: RiskLevel | null;
}

export default function StudentDashboard() {
  const { user } = useAuth();
  const toast = useToast();
  const { data, error, loading, reload } = useFetch<{ courses: MyCourse[]; gpa_estimate: number | null }>("/me/courses");
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;
  const current = data.courses.filter((c) => c.grade === null);
  const done = data.courses.filter((c) => c.grade !== null);
  const flags = data.courses.flatMap((c) => c.flags.map((f) => `${c.code}: ${f}`));
  const avgCp = current.filter((c) => c.cp_pct !== null);

  return (
    <>
      <Hero title={`Hi ${user?.name.split(" ")[0]}! 👋`}
        subtitle={flags.length ? `You have ${flags.length} thing${flags.length > 1 ? "s" : ""} to act on this semester — see below. Keep going, you've got this!` : "You're on track this semester. Check your marks, rubric feedback and course outcome progress any time."}
        actions={<button className="btn" onClick={() => download("/me/report.pdf").catch((e) => toast(e.message, "error"))}>↓ Download my report</button>}
        art={<StudyIllustration />} />
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <Stat label="Current courses" value={current.length} icon={<IconBook />} tone="violet" />
        <Stat label="Average CP this semester" icon={<IconTrend />} accent value={avgCp.length ? fmt(avgCp.reduce((a, c) => a + (c.cp_pct ?? 0), 0) / avgCp.length) : "—"} unit={avgCp.length ? "%" : undefined} />
        <Stat label="Completed courses" value={done.length} icon={<IconCap />} tone="blue" sub={done.length ? `${done.filter((c) => c.passed).length} passed` : undefined} />
        <Stat label="GPA (completed)" icon={<IconStar />} tone="amber" value={data.gpa_estimate === null ? "—" : data.gpa_estimate.toFixed(2)} sub="credit-weighted, 10-point scale" />
      </div>
      {flags.length > 0 && <div className="alert alert-warn" style={{ marginBottom: 16 }}><div><strong>Things to act on</strong><ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{flags.map((f) => <li key={f}>{f}</li>)}</ul></div></div>}

      {!data.courses.length ? <Card><Empty title="You are not enrolled in any course yet" /></Card> : (
        <div className="stack">
          {current.length > 0 && <div className="section-title"><h2>This semester</h2></div>}
          <div className="grid grid-3">
            {current.map((c) => (
              <Link key={c.id} to={`/my/courses/${c.id}`} className="card course-card">
                <div className="spread" style={{ alignItems: "flex-start" }}>
                  <span className="code">{c.code}</span>
                  <RiskBadge level={c.risk_level} />
                </div>
                <h3>{c.name}</h3>
                <div className="spread" style={{ alignItems: "flex-end" }}>
                  <span className="kicker">CP so far</span>
                  <span className="pct">{fmt(c.cp_pct)}<span className="muted" style={{ fontSize: 13 }}>%</span></span>
                </div>
                <Meter value={c.cp_pct} />
                <dl className="kv" style={{ gridTemplateColumns: "repeat(4, auto)", justifyContent: "space-between", gap: "2px 12px" }}>
                  {(["quiz", "assignment", "practical", "attendance"] as const).map((k) => (
                    <div key={k}><dt>{k.slice(0, 5)}</dt><dd className="mono">{c.components[k] === null ? "—" : `${fmt(c.components[k], 0)}%`}</dd></div>
                  ))}
                </dl>
                <div className="small muted" style={{ borderTop: "1px solid var(--rule)", paddingTop: 10 }}>{c.assessments_released} assessments released · {c.faculty ?? ""}</div>
              </Link>
            ))}
          </div>
          {done.length > 0 && <>
            <div className="section-title" style={{ marginTop: 12 }}><h2>Completed courses</h2></div>
            <Card pad={false}>
              <div className="table-wrap"><table className="table">
                <thead><tr><th>Course</th><th>Year</th><th className="r">CP</th><th className="r">NCP</th><th className="r">Final</th><th className="c">Grade</th><th>Result</th></tr></thead>
                <tbody>{done.map((c) => (
                  <tr key={c.id}><td><Link to={`/my/courses/${c.id}`}><strong>{c.code}</strong> {c.name}</Link></td><td>{c.academic_year}</td>
                    <td className="r num">{pct(c.cp_pct)}</td><td className="r num">{pct(c.ncp_pct)}</td><td className="r num"><strong>{pct(c.final_pct)}</strong></td>
                    <td className="c"><strong>{c.grade}</strong></td><td><ResultBadge passed={c.passed} /></td></tr>
                ))}</tbody>
              </table></div>
            </Card>
          </>}
        </div>
      )}
    </>
  );
}
