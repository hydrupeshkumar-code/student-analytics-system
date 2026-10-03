import { useMemo, useState } from "react";
import { download } from "../../lib/api";
import { pct, useFetch } from "../../lib/hooks";
import type { Gradebook as GB, GradebookStudent } from "../../lib/types";
import { Card, ErrorBox, Modal, ResultBadge, Spinner } from "../../components/ui";
import { useCourse } from "./CourseWorkspace";

type SortKey = "roll_no" | "name" | "cp_pct" | "ncp_pct" | "final_pct";

export default function Gradebook() {
  const { course } = useCourse();
  const { data, error, loading, reload } = useFetch<GB>(`/courses/${course.id}/gradebook`);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "roll_no", dir: 1 });
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState<GradebookStudent | null>(null);

  const rows = useMemo(() => {
    if (!data) return [];
    const term = q.trim().toLowerCase();
    return data.students
      .filter((s) => !term || s.name.toLowerCase().includes(term) || (s.roll_no ?? "").toLowerCase().includes(term))
      .sort((a, b) => {
        const x = a[sort.key], y = b[sort.key];
        if (x === y) return 0;
        if (x === null) return 1;
        if (y === null) return -1;
        return (x < y ? -1 : 1) * sort.dir;
      });
  }, [data, sort, q]);

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;

  const th = (key: SortKey, label: string, r = false) => (
    <th className={r ? "r" : ""} aria-sort={sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <button className="btn-ghost" style={{ border: 0, background: "none", padding: 0, font: "inherit", color: "inherit", cursor: "pointer", textTransform: "inherit", letterSpacing: "inherit" }}
        onClick={() => setSort({ key, dir: sort.key === key ? (sort.dir === 1 ? -1 : 1) : key === "roll_no" || key === "name" ? 1 : -1 })}>
        {label}{sort.key === key ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );

  return (
    <div className="stack">
      <Card>
        <div className="spread">
          <div>
            <h2>Consolidated CP–NCP result</h2>
            <p className="small text-2" style={{ marginTop: 4 }}>Final % = CP % × {data.cp_weight}% + NCP % × {data.ncp_weight}%. CP % is the weightage-weighted average of released assessments.</p>
          </div>
          <div className="row">
            <input className="input" style={{ width: 220 }} placeholder="Search student" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search student" />
            <button className="btn" onClick={() => download(`/courses/${course.id}/gradebook.xlsx`)}>↓ Excel</button>
          </div>
        </div>
      </Card>
      <Card pad={false}>
        <div className="table-wrap" style={{ maxHeight: "70vh" }}>
          <table className="table sticky compact">
            <thead><tr>
              {th("roll_no", "Roll no")}{th("name", "Student")}
              {data.assessments.map((a) => <th key={a.id} className="r" title={`${a.title} · ${a.weightage}% of CP`}>{a.title}<div className="muted" style={{ textTransform: "none" }}>/{a.max_marks}</div></th>)}
              {th("cp_pct", "CP %", true)}{th("ncp_pct", "NCP %", true)}{th("final_pct", "Final %", true)}<th className="c">Grade</th><th>Result</th>
            </tr></thead>
            <tbody>{rows.map((s) => (
              <tr key={s.student_id} style={{ cursor: "pointer" }} onClick={() => setDetail(s)}>
                <td className="small num">{s.roll_no}</td>
                <td className="nowrap"><strong>{s.name}</strong>{s.flags.length > 0 && <span className="badge badge-warn" style={{ marginLeft: 6 }} title={s.flags.join("\n")}>⚠ {s.flags.length}</span>}</td>
                {data.assessments.map((a) => {
                  const c = s.assessments[a.id];
                  return <td key={a.id} className="r num" style={{ color: c?.pct !== null && c?.pct !== undefined && c.pct < 40 ? "var(--critical-text)" : undefined }}>{c?.absent ? "AB" : c?.marks ?? "—"}</td>;
                })}
                <td className="r num"><strong>{pct(s.cp_pct)}</strong></td>
                <td className="r num">{s.ncp_absent ? "AB" : pct(s.ncp_pct)}</td>
                <td className="r num"><strong>{pct(s.final_pct)}</strong></td>
                <td className="c"><strong>{s.grade ?? "—"}</strong></td>
                <td><ResultBadge passed={s.passed} /></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </Card>
      {detail && (
        <Modal title={`${detail.name} · ${detail.roll_no ?? ""}`} onClose={() => setDetail(null)}>
          <dl className="kv">
            <dt>Quiz</dt><dd>{pct(detail.components.quiz)}</dd>
            <dt>Assignment</dt><dd>{pct(detail.components.assignment)}</dd>
            <dt>Practical</dt><dd>{pct(detail.components.practical)}</dd>
            <dt>Attendance</dt><dd>{pct(detail.components.attendance)}</dd>
            <dt>CP %</dt><dd><strong>{pct(detail.cp_pct)}</strong> <span className="muted small">over {detail.cp_weight_covered}% of CP weightage</span></dd>
            <dt>NCP %</dt><dd>{detail.ncp_absent ? "Absent" : pct(detail.ncp_pct)}</dd>
            <dt>Final</dt><dd><strong>{pct(detail.final_pct)}</strong> {detail.grade && `· grade ${detail.grade}`}</dd>
          </dl>
          {detail.flags.length > 0 && <><div className="divider" /><ul className="list-plain">{detail.flags.map((f) => <li key={f} className="alert alert-warn">⚠ {f}</li>)}</ul></>}
        </Modal>
      )}
    </div>
  );
}
