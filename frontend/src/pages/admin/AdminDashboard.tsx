import { useState } from "react";
import { Link } from "react-router-dom";
import { pct, useFetch } from "../../lib/hooks";
import type { Metrics } from "../../lib/types";
import { BarList } from "../../components/charts";
import { Card, Empty, ErrorBox, Hero, Meter, Spinner, Stat } from "../../components/ui";
import { IconAlert, IconBook, IconCap, IconTrend } from "../../components/icons";
import { StudyIllustration } from "../../components/Illustrations";

interface Overview {
  users: { admin: number; faculty: number; student: number };
  courses: { id: number; code: string; name: string; academic_year: string; semester: number; section: string; faculty: string | null; program: string | null; students: number; cp_average: number | null; pass_rate: number | null; high_risk: number; medium_risk: number; assessments: number; marking_open: number; ncp_entered: number }[];
  programs: { id: number; code: string; name: string; courses: number; students: number; cp_average: number | null; pass_rate: number | null; high_risk: number }[];
  academic_years: string[];
  totals: { courses: number; enrollments: number; high_risk: number; medium_risk: number; marking_open: number };
  model: { algorithm: string; holdout: Metrics; trained_at: string } | null;
}

export default function AdminDashboard() {
  const [year, setYear] = useState("");
  const { data, error, loading, reload } = useFetch<Overview>(`/admin/overview${year ? `?academic_year=${year}` : ""}`);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;
  const t = data.totals;

  return (
    <>
      <Hero title="Institution overview"
        subtitle="Consolidated CP–NCP analytics across programs and courses, with accreditation reports and early warnings in one place."
        actions={<>
          <select className="input" style={{ width: 190, background: "#fff", color: "#1d2433", border: "none" }} value={year} onChange={(e) => setYear(e.target.value)} aria-label="Academic year">
            <option value="">All academic years</option>{data.academic_years.map((y) => <option key={y}>{y}</option>)}
          </select>
          <Link className="btn btn-ghost" to="/attainment">PO attainment</Link>
        </>}
        art={<StudyIllustration />} />
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <Stat label="Students" value={data.users.student} icon={<IconCap />} tone="violet" sub={`${data.users.faculty} faculty · ${data.users.admin} admins`} />
        <Stat label="Active courses" value={t.courses} icon={<IconBook />} tone="blue" sub={`${t.enrollments} enrolments`} />
        <Stat label="High-risk flags" value={t.high_risk} icon={<IconAlert />} tone="coral" sub={`course enrolments · ${t.medium_risk} more at medium risk`} />
        <Stat label="Early-warning model" accent icon={<IconTrend />} value={data.model ? `${(data.model.holdout.accuracy * 100).toFixed(0)}%` : "—"}
          sub={data.model ? <>accuracy · recall {(data.model.holdout.recall * 100).toFixed(0)}% · <Link to="/ml">details</Link></> : <Link to="/ml">Train a model</Link>} />
      </div>

      <div className="grid grid-2" style={{ alignItems: "start", marginBottom: 16 }}>
        <Card title="Programs" pad={false}>
          {!data.programs.length ? <Empty title="No programs" action={<Link className="btn btn-primary" to="/programs">Add a program</Link>} /> : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Program</th><th className="r">Students</th><th className="r">Courses</th><th className="r">CP avg</th><th className="r">Pass rate</th><th className="r">High risk</th></tr></thead>
              <tbody>{data.programs.map((p) => (
                <tr key={p.id}><td><strong>{p.code}</strong><div className="small muted">{p.name}</div></td><td className="r num">{p.students}</td><td className="r num">{p.courses}</td>
                  <td className="r num">{pct(p.cp_average)}</td><td className="r num">{pct(p.pass_rate)}</td><td className="r num">{p.high_risk}</td></tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>
        <Card title="CP average by course" subtitle="Bars below 40% are highlighted">
          <BarList threshold={40} rows={data.courses.map((c) => ({ label: `${c.code} (${c.academic_year})`, value: c.cp_average }))} />
        </Card>
      </div>

      <Card title="Course monitor" subtitle="Marking progress, NCP entry and early-warning counts" pad={false}>
        <div className="table-wrap"><table className="table">
          <thead><tr><th>Course</th><th>Faculty</th><th className="r">Students</th><th>CP average</th><th className="r">Pass rate</th><th className="r">NCP entered</th><th className="r">Marking open</th><th className="r">Risk (H/M)</th></tr></thead>
          <tbody>{data.courses.map((c) => (
            <tr key={c.id}>
              <td><Link to={`/courses/${c.id}`}><strong>{c.code}</strong> {c.name}</Link><div className="small muted">{c.program ?? "—"} · {c.academic_year} · Sem {c.semester} · Sec {c.section}</div></td>
              <td>{c.faculty ?? <span className="badge badge-warn">Unassigned</span>}</td>
              <td className="r num">{c.students}</td>
              <td style={{ minWidth: 130 }}><div className="row" style={{ flexWrap: "nowrap" }}><Meter value={c.cp_average} /><span className="small num">{pct(c.cp_average, 0)}</span></div></td>
              <td className="r num">{pct(c.pass_rate, 0)}</td>
              <td className="r num">{c.ncp_entered}/{c.students}</td>
              <td className="r num">{c.marking_open}</td>
              <td className="r num">{c.high_risk ? <span className="badge badge-bad">{c.high_risk}</span> : 0} / {c.medium_risk}</td>
            </tr>
          ))}</tbody>
        </table></div>
      </Card>
    </>
  );
}
