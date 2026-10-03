import { Link } from "react-router-dom";
import { fmt, pct, titleCase, useFetch } from "../../lib/hooks";
import { BarList, Columns, CorrelationScatter } from "../../components/charts";
import { Card, Empty, ErrorBox, Spinner, Stat, StatusBadge } from "../../components/ui";
import type { AStatus } from "../../lib/types";
import { useCourse } from "./CourseWorkspace";

interface Analytics {
  students: number; cp_average: number | null; ncp_average: number | null; final_average: number | null; pass_rate: number | null;
  components: Record<string, number | null>;
  assessments: { id: number; title: string; component: string; status: AStatus; graded: number; average: number | null; min: number | null; max: number | null; below_pass: number }[];
  distribution: { basis: string; bins: { band: string; count: number }[] };
  grades: { grade: string; count: number }[];
  correlation: { pearson_r: number | null; fit: { slope: number; intercept: number } | null; n: number; points: { name: string; cp: number; ncp: number }[] };
  risk_counts: { high: number; medium: number; low: number };
  leaderboard: { student_id: number; name: string; roll_no: string; score: number }[];
}

function strength(r: number) {
  const a = Math.abs(r);
  return a >= 0.7 ? "strong" : a >= 0.4 ? "moderate" : a >= 0.2 ? "weak" : "negligible";
}

export default function CourseOverview() {
  const { course } = useCourse();
  const { data, error, loading, reload } = useFetch<Analytics>(`/courses/${course.id}/analytics`);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;
  const hasFinal = data.final_average !== null;

  return (
    <div className="stack">
      <div className="grid grid-4">
        <Stat label="CP average" value={fmt(data.cp_average)} unit="%" accent sub={`${data.students} students · weighted across released assessments`} />
        <Stat label="NCP average" value={fmt(data.ncp_average)} unit={data.ncp_average === null ? undefined : "%"} sub={data.ncp_average === null ? "Semester-end marks not entered" : "Semester-end examination"} />
        <Stat label="Pass rate" value={data.pass_rate === null ? "—" : fmt(data.pass_rate, 0)} unit={data.pass_rate === null ? undefined : "%"} sub={hasFinal ? `Final average ${pct(data.final_average)}` : "Available after NCP entry"} />
        <Stat label="Early warning" value={data.risk_counts.high} sub={<><Link to="risk">{data.risk_counts.high} high · {data.risk_counts.medium} medium risk</Link></>} />
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <Card title="Component-wise class average" subtitle="Percentage across all assessments of each CP component">
          <BarList threshold={40} rows={(["quiz", "assignment", "practical", "attendance", "other"] as const)
            .filter((k) => data.components[k] !== null).map((k) => ({ label: titleCase(k), value: data.components[k] }))} />
          {Object.values(data.components).every((v) => v === null) && <Empty title="No marks yet">Open marking on an assessment and enter scores.</Empty>}
        </Card>
        <Card title={`Score distribution (${data.distribution.basis === "final_pct" ? "final %" : "CP %"})`} subtitle="Number of students per percentage band">
          <Columns data={data.distribution.bins} x="band" y="count" name="Students" />
        </Card>
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <Card title="CP–NCP correlation" subtitle={data.correlation.pearson_r === null
          ? "Appears once semester-end marks are entered for at least 3 students"
          : `Pearson r = ${data.correlation.pearson_r.toFixed(2)} (${strength(data.correlation.pearson_r)}) across ${data.correlation.n} students — dashed line is the least-squares fit`}>
          {data.correlation.points.length ? <CorrelationScatter points={data.correlation.points} fit={data.correlation.fit} />
            : <Empty title="No paired data yet">Continuous scores will be plotted against semester-end results here.</Empty>}
        </Card>
        <Card title="Assessment summary" pad={false}>
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Assessment</th><th>Status</th><th className="r">Scored</th><th className="r">Avg</th><th className="r">Range</th><th className="r">&lt; pass</th></tr></thead>
            <tbody>{data.assessments.map((a) => (
              <tr key={a.id}>
                <td><strong>{a.title}</strong><div className="small muted">{titleCase(a.component)}</div></td>
                <td><StatusBadge status={a.status} /></td>
                <td className="r num">{a.graded}</td>
                <td className="r num">{pct(a.average)}</td>
                <td className="r num small">{a.min === null ? "—" : `${a.min.toFixed(0)}–${a.max?.toFixed(0)}`}</td>
                <td className="r num">{a.below_pass || <span className="muted">0</span>}</td>
              </tr>
            ))}</tbody>
          </table></div>
          {!data.assessments.length && <Empty title="No released assessments" action={<Link className="btn btn-primary" to="assessments">Create an assessment</Link>} />}
        </Card>
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <Card title="Top performers" subtitle={hasFinal ? "By final percentage" : "By CP percentage so far"} pad={false}>
          <div className="table-wrap"><table className="table">
            <tbody>{data.leaderboard.map((s, i) => (
              <tr key={s.student_id}><td className="num muted" style={{ width: 36 }}>{i + 1}</td><td><strong>{s.name}</strong> <span className="small muted">{s.roll_no}</span></td><td className="r num">{s.score.toFixed(1)}%</td></tr>
            ))}</tbody>
          </table></div>
        </Card>
        {hasFinal && (
          <Card title="Grade distribution">
            <Columns data={data.grades} x="grade" y="count" name="Students" />
          </Card>
        )}
      </div>
    </div>
  );
}
