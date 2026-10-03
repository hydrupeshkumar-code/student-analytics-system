import { Fragment, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { dateStr, fmt, pct, titleCase, useFetch } from "../../lib/hooks";
import type { RiskLevel } from "../../lib/types";
import { PairedColumns } from "../../components/charts";
import { Card, Empty, ErrorBox, Meter, PageHead, ResultBadge, RiskBadge, Spinner } from "../../components/ui";

interface RubricView {
  title: string;
  levels: { id: number; label: string; points: number }[];
  criteria: { id: number; name: string; description: string | null; weight: number; descriptors: string[] | null; selected_level_id: number | null }[];
}
interface Item {
  id: number; title: string; component: string; max_marks: number; weightage: number; due_date: string | null;
  marks: number | null; pct: number | null; absent: boolean; attended: number | null; sessions_held: number | null;
  feedback: string | null; class_average: number | null; rubric: RubricView | null;
}
interface Detail {
  course: { id: number; code: string; name: string; semester: number; academic_year: string; credits: number; faculty: string | null; cp_weight: number; ncp_weight: number; ncp_max_marks: number; ncp_published: boolean };
  assessments: Item[]; components: Record<string, number | null>; cp_pct: number | null; cp_weight_covered: number; class_cp_average: number | null;
  ncp_marks: number | null; ncp_pct: number | null; ncp_absent: boolean; final_pct: number | null; grade: string | null; passed: boolean | null;
  flags: string[]; result_pending: boolean; cos: { code: string; description: string; pct: number | null; target: number; attained: boolean | null }[];
  risk: { risk_level: RiskLevel; reasons: string[]; suggestions: string[] } | null;
  requirements: { pass_mark_pct: number; ncp_min_pct: number; attendance_min_pct: number };
}

function RubricFeedback({ r }: { r: RubricView }) {
  return (
    <div className="table-wrap" style={{ marginTop: 8 }}>
      <div className="rubric-grid" style={{ gridTemplateColumns: `minmax(140px,1.2fr) repeat(${r.levels.length}, minmax(100px,1fr))`, minWidth: 520 }}>
        <div className="rh">Criterion</div>
        {r.levels.map((l) => <div key={l.id} className="rh">{l.label}</div>)}
        {r.criteria.map((c) => (
          <div key={c.id} style={{ display: "contents" }}>
            <div><strong>{c.name}</strong> <span className="muted">({c.weight})</span></div>
            {r.levels.map((l, i) => {
              const sel = c.selected_level_id === l.id;
              return <div key={l.id} className={sel ? "rubric-cell selected" : ""} aria-current={sel || undefined}>{sel && "✓ "}{c.descriptors?.[i] || (sel ? l.label : "")}</div>;
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function StudentCourse() {
  const { courseId } = useParams();
  const { data, error, loading, reload } = useFetch<Detail>(`/me/courses/${courseId}`);
  const [open, setOpen] = useState<number | null>(null);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;
  const c = data.course;
  const chart = data.assessments.filter((a) => a.pct !== null).map((a) => ({ name: a.title, you: a.pct, cls: a.class_average }));

  return (
    <>
      <PageHead crumbs={<Link to="/">My performance</Link>} title={<>{c.code} · {c.name}</>}
        subtitle={<>{c.academic_year} · Semester {c.semester} · {c.credits} credits · {c.faculty ?? ""} · CP {c.cp_weight}% + NCP {c.ncp_weight}%</>} />

      <section className="reportcard" aria-label="Result summary">
        <div>
          <div className="stat-label">Continuous (CP)</div>
          <div className="big">{fmt(data.cp_pct)}{data.cp_pct !== null && <small>%</small>}</div>
          <div className="sub">Class average {pct(data.class_cp_average)} · counted over {data.cp_weight_covered}% of CP</div>
        </div>
        <div>
          <div className="stat-label">Semester-end (NCP)</div>
          <div className="big">{c.ncp_published ? (data.ncp_absent ? "AB" : fmt(data.ncp_pct)) : "—"}{c.ncp_published && data.ncp_pct !== null && !data.ncp_absent && <small>%</small>}</div>
          <div className="sub">{c.ncp_published ? (data.ncp_marks !== null ? `${data.ncp_marks} of ${c.ncp_max_marks} marks` : "Not entered") : "Results not yet published"}</div>
        </div>
        <div>
          <div className="stat-label">Final · CP {c.cp_weight} + NCP {c.ncp_weight}</div>
          <div className="big">{fmt(data.final_pct)}{data.final_pct !== null && <small>%</small>}</div>
          <div className="sub">{data.passed !== null ? <ResultBadge passed={data.passed} /> : data.result_pending && c.ncp_published ? "Result pending — CP marking still in progress" : `Pass needs ≥ ${data.requirements.pass_mark_pct}% overall and ≥ ${data.requirements.ncp_min_pct}% in NCP`}</div>
        </div>
        <div className="grade-cell">
          <div className="stat-label">Grade</div>
          <div className="big">{data.grade ?? "—"}</div>
          {data.passed !== null
            ? <div className="sub">Result declared{data.grade ? ` · ${data.passed ? "passed" : "re-appear required"}` : ""}</div>
            : <div className="sub"><RiskBadge level={data.risk?.risk_level} /><div style={{ marginTop: 6 }}>{data.risk ? (data.risk.risk_level === "low" ? "On track — keep it up." : "See the guidance below.") : "Early warning appears once marks are released."}</div></div>}
        </div>
      </section>

      {(data.flags.length > 0 || (data.risk && data.risk.risk_level !== "low")) && (
        <div className="card card-pad guidance" style={{ marginBottom: 16 }}>
          <h3 style={{ marginBottom: 8 }}>Guidance</h3>
          <div className="grid grid-2">
            <div><div className="small muted" style={{ marginBottom: 4 }}>What we noticed</div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>{[...new Set([...data.flags, ...(data.risk?.reasons ?? [])])].map((f) => <li key={f}>{f}</li>)}</ul></div>
            {data.risk?.suggestions.length ? <div><div className="small muted" style={{ marginBottom: 4 }}>Suggested next steps</div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>{data.risk.suggestions.map((s) => <li key={s}>{s}</li>)}</ul></div> : null}
          </div>
        </div>
      )}

      <div className="grid grid-2" style={{ alignItems: "start", marginBottom: 16 }}>
        <Card title="You vs class average" subtitle="Percentage per released assessment">
          {chart.length ? <PairedColumns data={chart} x="name" a={{ key: "you", name: "You" }} b={{ key: "cls", name: "Class average" }} /> : <Empty title="No marks released yet" />}
        </Card>
        <Card title="Course outcome progress" subtitle="Your score on assessments mapped to each CO">
          {!data.cos.length ? <Empty title="Course outcomes not defined" /> : (
            <div className="stack" style={{ gap: 12 }}>{data.cos.map((co) => (
              <div key={co.code}>
                <div className="spread small"><span><strong>{co.code}</strong> <span className="text-2">{co.description}</span></span>
                  <span className="nowrap">{co.attained === null ? <span className="muted">no data</span> : co.attained ? <span className="badge badge-good">✓ {fmt(co.pct, 0)}%</span> : <span className="badge badge-warn">{fmt(co.pct, 0)}% · target {co.target}%</span>}</span></div>
                <Meter value={co.pct} color={co.attained === false ? "var(--serious)" : undefined} />
              </div>
            ))}</div>
          )}
        </Card>
      </div>

      <Card title="Component-wise breakdown" subtitle="Click an assessment to see rubric scoring and feedback" pad={false}>
        {!data.assessments.length ? <Empty title="No assessments released yet">Marks appear here once your faculty completes evaluation.</Empty> : (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Assessment</th><th>Component</th><th>Date</th><th className="r">Marks</th><th className="r">%</th><th className="r">Class avg</th><th className="r">Weight</th><th /></tr></thead>
            <tbody>{data.assessments.map((a) => (
              <Fragment key={a.id}>
                <tr style={{ cursor: a.rubric || a.feedback ? "pointer" : undefined }} onClick={() => setOpen(open === a.id ? null : a.id)}>
                  <td><strong>{a.title}</strong>{a.feedback && <span className="badge badge-info" style={{ marginLeft: 6 }}>feedback</span>}</td>
                  <td>{titleCase(a.component)}</td>
                  <td className="small nowrap">{dateStr(a.due_date)}</td>
                  <td className="r num">{a.absent ? "Absent" : a.component === "attendance" ? `${a.attended ?? "—"} / ${a.sessions_held}` : a.marks === null ? "—" : `${a.marks} / ${a.max_marks}`}</td>
                  <td className="r num" style={{ color: a.pct !== null && a.pct < 40 ? "var(--critical-text)" : undefined }}><strong>{pct(a.pct, 0)}</strong></td>
                  <td className="r num muted">{pct(a.class_average, 0)}</td>
                  <td className="r num">{a.weightage}%</td>
                  <td className="r">{(a.rubric || a.feedback) && <span className="muted">{open === a.id ? "▴" : "▾"}</span>}</td>
                </tr>
                {open === a.id && (a.rubric || a.feedback) && (
                  <tr><td colSpan={8} style={{ background: "var(--surface-2)" }}>
                    {a.feedback && <div className="alert alert-info">💬 {a.feedback}</div>}
                    {a.rubric && <RubricFeedback r={a.rubric} />}
                  </td></tr>
                )}
              </Fragment>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  );
}
