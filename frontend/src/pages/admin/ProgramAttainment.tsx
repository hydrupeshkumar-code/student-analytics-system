import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { download } from "../../lib/api";
import { useFetch } from "../../lib/hooks";
import type { Program } from "../../lib/types";
import { Card, Empty, ErrorBox, Field, PageHead, Spinner } from "../../components/ui";
import { LevelCell } from "../faculty/Attainment";

interface PA {
  pos: { id: number; code: string; description: string; attainment: number | null; courses: number }[];
  courses: { course_id: number; code: string; name: string; semester: number; academic_year: string; values: Record<string, number | null> }[];
  po_list: { id: number; code: string }[];
}

export default function ProgramAttainment() {
  const programs = useFetch<Program[]>("/programs");
  const [pid, setPid] = useState<string>("");
  const [year, setYear] = useState("");
  useEffect(() => { if (!pid && programs.data?.length) setPid(String(programs.data[0].id)); }, [programs.data, pid]);
  const qs = year ? `?academic_year=${encodeURIComponent(year)}` : "";
  const { data, error, loading, reload } = useFetch<PA>(pid ? `/programs/${pid}/attainment${qs}` : null);

  return (
    <>
      <PageHead title="Program outcome attainment" subtitle="Average PO attainment across all courses of a program — the summary sheet for NBA Criterion 3."
        actions={pid && <button className="btn btn-primary" onClick={() => download(`/programs/${pid}/attainment.xlsx${qs}`)}>↓ Excel</button>} />
      <Card>
        <div className="form-grid" style={{ maxWidth: 520 }}>
          <Field label="Program"><select className="input" value={pid} onChange={(e) => setPid(e.target.value)}>{programs.data?.map((p) => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>)}</select></Field>
          <Field label="Academic year" hint="Blank = all years"><input className="input" value={year} onChange={(e) => setYear(e.target.value)} placeholder="2026-27" /></Field>
        </div>
      </Card>
      <div style={{ height: 16 }} />
      {!pid ? <Card><Empty title="Create a program first" /></Card> : loading && !data ? <Spinner /> : error ? <ErrorBox error={error} onRetry={reload} /> : data && (
        <div className="stack">
          <Card title="Program summary" subtitle="0–3 scale" pad={false}>
            <div className="table-wrap"><table className="table">
              <thead><tr><th>PO</th><th>Statement</th><th className="r">Courses contributing</th><th className="r">Attainment</th></tr></thead>
              <tbody>{data.pos.map((p) => (
                <tr key={p.id}><td><strong>{p.code}</strong></td><td className="small text-2">{p.description}</td><td className="r num">{p.courses}</td><td className="r" style={{ width: 160 }}><LevelCell v={p.attainment} target={2} /></td></tr>
              ))}</tbody>
            </table></div>
          </Card>
          <Card title="Course-wise PO attainment" pad={false}>
            {!data.courses.length ? <Empty title="No courses in this selection" /> : (
              <div className="table-wrap"><table className="table compact sticky">
                <thead><tr><th>Course</th>{data.po_list.map((p) => <th key={p.id} className="c">{p.code}</th>)}</tr></thead>
                <tbody>{data.courses.map((c) => (
                  <tr key={c.course_id}><td className="nowrap"><Link to={`/courses/${c.course_id}/attainment`}><strong>{c.code}</strong></Link> <span className="small muted">{c.academic_year} · S{c.semester}</span></td>
                    {data.po_list.map((p) => <td key={p.id} className="c num">{c.values[p.id] === null || c.values[p.id] === undefined ? <span className="muted">·</span> : c.values[p.id]!.toFixed(2)}</td>)}</tr>
                ))}</tbody>
              </table></div>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
