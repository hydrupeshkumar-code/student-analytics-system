import { download } from "../../lib/api";
import { fmt, useFetch } from "../../lib/hooks";
import { Card, Empty, ErrorBox, Meter, Spinner, useToast } from "../../components/ui";
import { useCourse } from "./CourseWorkspace";

interface Sum { evaluated: number; attained: number; pct_students: number | null; level: number | null }
interface Att {
  config: { co_target_pct: number; level1_pct: number; level2_pct: number; level3_pct: number; target_level: number; cp_weight: number; ncp_weight: number };
  students: number;
  cos: { id: number; code: string; description: string; assessments: string[]; cp: Sum; ncp: Sum; attainment: number | null; basis: string; attained: boolean | null }[];
  pos: { id: number; code: string; description: string; mapped: boolean; attainment: number | null }[];
  matrix: { co_id: number; co: string; values: Record<string, number | null> }[];
}

export function LevelCell({ v, target }: { v: number | null; target: number }) {
  if (v === null) return <span className="muted">—</span>;
  return (
    <div className="row" style={{ flexWrap: "nowrap", justifyContent: "flex-end" }}>
      <div style={{ width: 70 }}><Meter value={v} max={3} color={v < target ? "var(--serious)" : undefined} /></div>
      <strong className="num" style={{ width: 34, textAlign: "right" }}>{v.toFixed(2)}</strong>
    </div>
  );
}

export default function Attainment() {
  const { course } = useCourse();
  const toast = useToast();
  const { data, error, loading, reload } = useFetch<Att>(`/courses/${course.id}/attainment`);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;
  const c = data.config;
  const dl = (ext: string) => download(`/courses/${course.id}/attainment.${ext}`).catch((e) => toast(e.message, "error"));

  return (
    <div className="stack">
      <Card>
        <div className="spread">
          <div>
            <h2>CO/PO attainment report</h2>
            <p className="small text-2" style={{ marginTop: 4 }}>
              Students attain a CO at ≥ {c.co_target_pct}% marks. Level 3 / 2 / 1 when ≥ {c.level3_pct}% / {c.level2_pct}% / {c.level1_pct}% of students attain.
              CO attainment = {c.cp_weight}% CP level + {c.ncp_weight}% NCP level. Target level {c.target_level}.
            </p>
          </div>
          <div className="row"><button className="btn" onClick={() => dl("xlsx")}>↓ Excel</button><button className="btn btn-primary" onClick={() => dl("pdf")}>↓ PDF for NAAC/NBA</button></div>
        </div>
      </Card>

      <Card title="Course outcome attainment" subtitle={`${data.students} students evaluated`} pad={false}>
        {!data.cos.length ? <Empty title="No course outcomes defined">Add COs and link assessments to them in “COs & mapping”.</Empty> : (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>CO</th><th>Assessed through</th><th className="r">CP: students ≥ target</th><th className="c">CP level</th><th className="r">NCP: students ≥ target</th><th className="c">NCP level</th><th className="r">Attainment (0–3)</th><th>Status</th></tr></thead>
            <tbody>{data.cos.map((co) => (
              <tr key={co.id}>
                <td title={co.description}><strong>{co.code}</strong><div className="small muted" style={{ maxWidth: 260 }}>{co.description}</div></td>
                <td className="small">{co.assessments.join(", ") || <span className="muted">No CP assessment linked</span>}</td>
                <td className="r num">{co.cp.pct_students === null ? "—" : `${co.cp.attained}/${co.cp.evaluated} (${fmt(co.cp.pct_students, 0)}%)`}</td>
                <td className="c num"><strong>{co.cp.level ?? "—"}</strong></td>
                <td className="r num">{co.ncp.pct_students === null ? "—" : `${co.ncp.attained}/${co.ncp.evaluated} (${fmt(co.ncp.pct_students, 0)}%)`}</td>
                <td className="c num"><strong>{co.ncp.level ?? "—"}</strong></td>
                <td className="r"><LevelCell v={co.attainment} target={c.target_level} /><div className="small muted" style={{ textAlign: "right" }}>{co.basis}</div></td>
                <td>{co.attained === null ? <span className="muted">—</span> : co.attained ? <span className="badge badge-good">✓ Attained</span> : <span className="badge badge-warn">Below target</span>}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>

      {data.pos.length > 0 && (
        <Card title="Program outcome attainment" subtitle="Σ(CO attainment × strength) ÷ Σ(strength) over mapped COs" pad={false}>
          <div className="table-wrap"><table className="table compact">
            <thead><tr><th>CO</th>{data.pos.map((p) => <th key={p.id} className="c" title={p.description}>{p.code}</th>)}</tr></thead>
            <tbody>
              {data.matrix.map((m) => (
                <tr key={m.co_id}><td><strong>{m.co}</strong></td>{data.pos.map((p) => <td key={p.id} className="c num">{m.values[p.id] ?? <span className="muted">·</span>}</td>)}</tr>
              ))}
              <tr style={{ background: "var(--surface-2)" }}><td><strong>Attainment</strong></td>
                {data.pos.map((p) => <td key={p.id} className="c num"><strong>{p.attainment === null ? <span className="muted">—</span> : p.attainment.toFixed(2)}</strong></td>)}</tr>
            </tbody>
          </table></div>
        </Card>
      )}
    </div>
  );
}
