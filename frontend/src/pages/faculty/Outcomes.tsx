import { useEffect, useState } from "react";
import { del, patch, post, put } from "../../lib/api";
import { useFetch } from "../../lib/hooks";
import type { Outcome } from "../../lib/types";
import { Card, Empty, ErrorBox, Field, Spinner, useConfirm, useToast } from "../../components/ui";
import { useCourse } from "./CourseWorkspace";

interface CoPo { cos: Outcome[]; pos: Outcome[]; cells: { co_id: number; po_id: number; strength: number }[] }

function CoList({ onChanged }: { onChanged: () => void }) {
  const { course, canEdit } = useCourse();
  const toast = useToast();
  const confirm = useConfirm();
  const { data, reload } = useFetch<Outcome[]>(`/courses/${course.id}/outcomes`);
  const [code, setCode] = useState("");
  const [desc, setDesc] = useState("");
  const [edit, setEdit] = useState<Outcome | null>(null);
  useEffect(() => { if (data && !code) setCode(`CO${data.length + 1}`); }, [data, code]);

  async function add() {
    try { await post(`/courses/${course.id}/outcomes`, { code: code.trim(), description: desc.trim() }); setCode(""); setDesc(""); reload(); onChanged(); toast("Course outcome added"); }
    catch (e) { toast((e as Error).message, "error"); }
  }
  async function saveEdit() {
    if (!edit) return;
    try { await patch(`/courses/${course.id}/outcomes/${edit.id}`, { code: edit.code, description: edit.description }); setEdit(null); reload(); onChanged(); }
    catch (e) { toast((e as Error).message, "error"); }
  }
  async function remove(o: Outcome) {
    if (!(await confirm({ title: `Delete ${o.code}?`, body: "Its PO mapping and assessment links will be removed.", confirm: "Delete", danger: true }))) return;
    await del(`/courses/${course.id}/outcomes/${o.id}`); reload(); onChanged();
  }

  return (
    <Card title="Course outcomes (COs)" subtitle="What students should be able to do after the course">
      {!data?.length && <Empty title="No course outcomes yet">Add 4–6 measurable outcomes, e.g. “Design normalised schemas from ER models.”</Empty>}
      <ul className="list-plain">{data?.map((o) => (
        <li key={o.id} className="row" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
          {edit?.id === o.id ? <>
            <input className="input" style={{ width: 80 }} value={edit.code} onChange={(e) => setEdit({ ...edit, code: e.target.value })} />
            <input className="input" value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} />
            <button className="btn btn-sm btn-primary" onClick={saveEdit}>Save</button><button className="btn btn-sm" onClick={() => setEdit(null)}>Cancel</button>
          </> : <>
            <span className="badge badge-info" style={{ flex: "none" }}>{o.code}</span>
            <span style={{ flex: 1 }}>{o.description}</span>
            {canEdit && <><button className="btn btn-sm btn-ghost" onClick={() => setEdit(o)}>Edit</button><button className="btn btn-sm btn-ghost btn-danger" onClick={() => remove(o)}>Delete</button></>}
          </>}
        </li>
      ))}</ul>
      {canEdit && (
        <div className="row" style={{ marginTop: 14, flexWrap: "nowrap" }}>
          <input className="input" style={{ width: 80 }} value={code} onChange={(e) => setCode(e.target.value)} aria-label="CO code" />
          <input className="input" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Outcome statement" aria-label="CO statement" onKeyDown={(e) => e.key === "Enter" && code && desc && add()} />
          <button className="btn btn-primary" disabled={!code || !desc} onClick={add}>Add</button>
        </div>
      )}
    </Card>
  );
}

function CoPoMatrix({ version }: { version: number }) {
  const { course, canEdit } = useCourse();
  const toast = useToast();
  const { data, error, loading, reload } = useFetch<CoPo>(`/courses/${course.id}/co-po`);
  const [cells, setCells] = useState<Record<string, number | null>>({});
  const [dirty, setDirty] = useState(false);
  useEffect(() => { reload(); }, [version, reload]);
  useEffect(() => {
    if (data) { setCells(Object.fromEntries(data.cells.map((c) => [`${c.co_id}:${c.po_id}`, c.strength]))); setDirty(false); }
  }, [data]);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  if (!course.program_id) return <Card title="CO–PO mapping"><div className="alert alert-warn">This course is not linked to a program. An administrator must set the program to map COs to POs.</div></Card>;

  async function save() {
    const payload = data!.cos.flatMap((co) => data!.pos.map((po) => ({ co_id: co.id, po_id: po.id, strength: cells[`${co.id}:${po.id}`] ?? null })));
    try { await put(`/courses/${course.id}/co-po`, payload); toast("CO–PO mapping saved"); reload(); } catch (e) { toast((e as Error).message, "error"); }
  }

  return (
    <Card title="CO–PO mapping matrix" subtitle="Correlation strength: 1 = low, 2 = medium, 3 = high; blank = not mapped"
      actions={canEdit && <button className="btn btn-primary btn-sm" disabled={!dirty} onClick={save}>Save mapping</button>} pad={false}>
      {!data.cos.length ? <Empty title="Add course outcomes first" /> : (
        <div className="table-wrap"><table className="table compact">
          <thead><tr><th>CO</th>{data.pos.map((p) => <th key={p.id} className="c" title={p.description}>{p.code}</th>)}</tr></thead>
          <tbody>{data.cos.map((co) => (
            <tr key={co.id}><td title={co.description}><strong>{co.code}</strong></td>
              {data.pos.map((po) => {
                const k = `${co.id}:${po.id}`;
                return <td key={po.id} className="c">
                  <select className="input" style={{ width: 52, height: 28, padding: "0 4px", fontWeight: cells[k] ? 700 : 400, background: cells[k] ? "var(--brand-soft)" : undefined, color: cells[k] ? "var(--brand-text)" : undefined, borderRadius: 8 }}
                    disabled={!canEdit} value={cells[k] ?? ""} aria-label={`${co.code} to ${po.code}`}
                    onChange={(e) => { setCells({ ...cells, [k]: e.target.value ? Number(e.target.value) : null }); setDirty(true); }}>
                    <option value="">–</option><option value="1">1</option><option value="2">2</option><option value="3">3</option>
                  </select>
                </td>;
              })}
            </tr>
          ))}</tbody>
        </table></div>
      )}
    </Card>
  );
}

function AttainmentConfig() {
  const { course, canEdit, reloadCourse } = useCourse();
  const toast = useToast();
  const [f, setF] = useState({ co_target_pct: course.co_target_pct, level1_pct: course.level1_pct, level2_pct: course.level2_pct, level3_pct: course.level3_pct, target_level: course.target_level });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: Number(e.target.value) });
  async function save() {
    try { await patch(`/courses/${course.id}`, f); toast("Attainment settings saved"); reloadCourse(); } catch (e) { toast((e as Error).message, "error"); }
  }
  return (
    <Card title="Attainment criteria" subtitle="Used to convert marks into CO attainment levels (NBA direct method)"
      actions={canEdit && <button className="btn btn-sm btn-primary" onClick={save}>Save</button>}>
      <div className="form-grid">
        <Field label="Student attains a CO at (% marks)"><input className="input" type="number" disabled={!canEdit} value={f.co_target_pct} onChange={set("co_target_pct")} /></Field>
        <Field label="Level 3 if ≥ % of students"><input className="input" type="number" disabled={!canEdit} value={f.level3_pct} onChange={set("level3_pct")} /></Field>
        <Field label="Level 2 if ≥ % of students"><input className="input" type="number" disabled={!canEdit} value={f.level2_pct} onChange={set("level2_pct")} /></Field>
        <Field label="Level 1 if ≥ % of students"><input className="input" type="number" disabled={!canEdit} value={f.level1_pct} onChange={set("level1_pct")} /></Field>
        <Field label="Target attainment level (0–3)"><input className="input" type="number" step={0.1} disabled={!canEdit} value={f.target_level} onChange={set("target_level")} /></Field>
      </div>
    </Card>
  );
}

export default function Outcomes() {
  const [v, setV] = useState(0);
  return (
    <div className="stack">
      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <CoList onChanged={() => setV((x) => x + 1)} />
        <AttainmentConfig />
      </div>
      <CoPoMatrix version={v} />
    </div>
  );
}
