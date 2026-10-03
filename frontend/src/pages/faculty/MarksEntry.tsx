import { useEffect, useMemo, useState } from "react";
import { Link, useBlocker, useNavigate, useParams } from "react-router-dom";
import { download, put, upload } from "../../lib/api";
import { titleCase, useFetch } from "../../lib/hooks";
import type { Assessment, Rubric } from "../../lib/types";
import { Card, Empty, ErrorBox, Modal, Spinner, StatusBadge, UploadButton, useToast } from "../../components/ui";
import { useCourse } from "./CourseWorkspace";

interface Row {
  student_id: number; name: string; roll_no: string | null; marks: number | null; attended: number | null;
  is_absent: boolean; feedback: string | null; criteria: Record<string, number>;
}
interface ScoresResp { assessment: Assessment; editable: boolean; rows: Row[] }

export function rubricMarks(r: Rubric, sel: Record<string, number>, max: number): number | null {
  const pts = new Map(r.levels.map((l) => [l.id, l.points]));
  const top = Math.max(...r.levels.map((l) => l.points));
  const tw = r.criteria.reduce((a, c) => a + c.weight, 0);
  let acc = 0;
  for (const c of r.criteria) {
    const lv = sel[c.id];
    if (lv === undefined) return null;
    acc += c.weight * ((pts.get(lv) ?? 0) / top);
  }
  return Math.round((max * acc / tw) * 100) / 100;
}

function RubricScorer({ rubric, rows, index, max, editable, onChange, onClose, onIndex }: {
  rubric: Rubric; rows: Row[]; index: number; max: number; editable: boolean;
  onChange: (sid: number, patch: Partial<Row>) => void; onClose: () => void; onIndex: (i: number) => void;
}) {
  const row = rows[index];
  const score = rubricMarks(rubric, row.criteria, max);
  const cols = `minmax(160px, 1.3fr) repeat(${rubric.levels.length}, minmax(110px, 1fr))`;
  return (
    <Modal wide title={<>{row.name} <span className="muted small">{row.roll_no}</span></>} onClose={onClose} footer={<>
      <span className="small muted" style={{ marginRight: "auto" }}>Student {index + 1} of {rows.length}</span>
      <button className="btn" disabled={index === 0} onClick={() => onIndex(index - 1)}>← Previous</button>
      <button className="btn btn-primary" onClick={() => (index < rows.length - 1 ? onIndex(index + 1) : onClose())}>{index < rows.length - 1 ? "Next student →" : "Done"}</button>
    </>}>
      <div className="spread" style={{ marginBottom: 12 }}>
        <div><strong>{rubric.title}</strong><div className="small muted">Click one performance level per criterion.</div></div>
        <div style={{ textAlign: "right" }}>
          <div className="stat-value num" style={{ fontSize: 24 }}>{score === null ? "—" : score.toFixed(2)}<small>/ {max}</small></div>
          <label className="check small"><input type="checkbox" disabled={!editable} checked={row.is_absent} onChange={(e) => onChange(row.student_id, { is_absent: e.target.checked, criteria: e.target.checked ? {} : row.criteria })} /> Absent / not submitted</label>
        </div>
      </div>
      <div className="table-wrap">
        <div className="rubric-grid" style={{ gridTemplateColumns: cols, minWidth: 560, opacity: row.is_absent ? 0.4 : 1 }}>
          <div className="rh">Criterion (weight)</div>
          {rubric.levels.map((l) => <div key={l.id} className="rh">{l.label} <span className="muted">· {l.points}</span></div>)}
          {rubric.criteria.map((c) => (
            <div key={c.id} style={{ display: "contents" }}>
              <div><strong>{c.name}</strong> <span className="muted">({c.weight}%)</span>{c.description && <div className="muted">{c.description}</div>}</div>
              {rubric.levels.map((l, li) => {
                const selected = row.criteria[c.id] === l.id;
                return (
                  <div key={l.id} role="radio" aria-checked={selected} tabIndex={editable && !row.is_absent ? 0 : -1}
                    className={`rubric-cell ${selected ? "selected" : ""}`}
                    onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && editable && !row.is_absent) { e.preventDefault(); onChange(row.student_id, { criteria: { ...row.criteria, [c.id]: l.id } }); } }}
                    onClick={() => editable && !row.is_absent && onChange(row.student_id, { criteria: { ...row.criteria, [c.id]: l.id } })}>
                    {selected && "✓ "}{c.descriptors?.[li] || <span className="muted">{l.label}</span>}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <label className="field" style={{ marginTop: 14 }}><span>Feedback to student</span>
        <textarea className="input" rows={2} disabled={!editable} value={row.feedback ?? ""} onChange={(e) => onChange(row.student_id, { feedback: e.target.value })} placeholder="What went well, what to improve…" />
      </label>
    </Modal>
  );
}

export function MarksPicker() {
  const { course } = useCourse();
  const { data, loading } = useFetch<Assessment[]>(`/courses/${course.id}/assessments`);
  if (loading && !data) return <Spinner />;
  const open = (data ?? []).filter((a) => a.status !== "draft");
  return (
    <Card title="Choose an assessment" pad={false}>
      {!open.length ? <Empty title="Nothing to mark yet" action={<Link className="btn btn-primary" to={`/courses/${course.id}/assessments`}>Go to assessments</Link>}>Open marking on an assessment first.</Empty> : (
        <div className="table-wrap"><table className="table"><tbody>{open.map((a) => (
          <tr key={a.id}><td><strong>{a.title}</strong> <span className="small muted">{titleCase(a.component)} · /{a.max_marks}</span></td><td><StatusBadge status={a.status} /></td>
            <td className="r num">{a.graded_count}/{course.student_count}</td>
            <td className="r"><Link className="btn btn-sm" to={String(a.id)}>{a.status === "in_progress" ? "Enter marks" : "View"}</Link></td></tr>
        ))}</tbody></table></div>
      )}
    </Card>
  );
}

export default function MarksEntry() {
  const { course, canEdit } = useCourse();
  const { assessmentId } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const { data, error, loading, reload, setData } = useFetch<ScoresResp>(`/assessments/${assessmentId}/scores`);
  const a = data?.assessment;
  const rubricRes = useFetch<Rubric>(a?.rubric_id ? `/rubrics/${a.rubric_id}` : null);
  const [rows, setRows] = useState<Row[]>([]);
  const [dirty, setDirty] = useState<Set<number>>(new Set());
  const [scorer, setScorer] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (data) { setRows(data.rows); setDirty(new Set()); } }, [data]);
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty.size > 0 && currentLocation.pathname !== nextLocation.pathname);
  useEffect(() => {
    if (blocker.state === "blocked") {
      if (window.confirm("You have unsaved marks. Leave without saving?")) blocker.proceed(); else blocker.reset();
    }
  }, [blocker]);
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => { if (dirty.size) { e.preventDefault(); } };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [dirty]);

  const editable = !!data?.editable && canEdit;
  const isAtt = a?.component === "attendance";
  const rubric = rubricRes.data;
  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return q ? rows.filter((r) => r.name.toLowerCase().includes(q) || (r.roll_no ?? "").toLowerCase().includes(q)) : rows;
  }, [rows, filter]);

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!a) return null;

  const change = (sid: number, p: Partial<Row>) => {
    setRows((rs) => rs.map((r) => (r.student_id === sid ? { ...r, ...p } : r)));
    setDirty((d) => new Set(d).add(sid));
  };
  const limit = isAtt ? a.sessions_held ?? 0 : a.max_marks;
  const invalid = rows.some((r) => { const v = isAtt ? r.attended : r.marks; return v !== null && (v < 0 || v > limit); });
  const scored = rows.filter((r) => r.is_absent || (isAtt ? r.attended !== null : rubric ? Object.keys(r.criteria).length === rubric.criteria.length : r.marks !== null)).length;
  const valueOf = (r: Row) => (r.is_absent ? 0 : isAtt ? (r.attended === null ? null : (a.max_marks * r.attended) / (a.sessions_held || 1)) : rubric ? rubricMarks(rubric, r.criteria, a.max_marks) : r.marks);

  async function save() {
    if (rubric) {
      const partial = rows.filter((r) => dirty.has(r.student_id) && !r.is_absent && Object.keys(r.criteria).length > 0 && Object.keys(r.criteria).length < rubric.criteria.length);
      if (partial.length) return toast(`Complete every rubric criterion for: ${partial.map((r) => r.name).join(", ")}`, "error");
    }
    setBusy(true);
    try {
      const scores = rows.filter((r) => dirty.has(r.student_id)).map((r) => ({
        student_id: r.student_id, marks: r.marks, attended: r.attended, is_absent: r.is_absent,
        feedback: r.feedback, criteria: rubric ? r.criteria : null,
      }));
      const res = await put<ScoresResp>(`/assessments/${a!.id}/scores`, { scores });
      setData(res);
      toast(`Saved ${scores.length} score${scores.length === 1 ? "" : "s"}`);
    } catch (e) { toast((e as Error).message, "error"); } finally { setBusy(false); }
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>, idx: number) {
    if (e.key === "Enter" || e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const next = document.querySelector<HTMLInputElement>(`[data-cell="${idx + (e.key === "ArrowUp" ? -1 : 1)}"]`);
      next?.focus(); next?.select();
    }
  }

  return (
    <div className="stack">
      <Card>
        <div className="spread">
          <div>
            <div className="row"><h2>{a.title}</h2><StatusBadge status={a.status} /></div>
            <div className="small text-2" style={{ marginTop: 4 }}>
              {titleCase(a.component)} · max {a.max_marks} marks · {a.weightage}% of CP
              {isAtt && ` · ${a.sessions_held} sessions held`}{rubric && ` · rubric “${rubric.title}”`} · {scored}/{rows.length} scored
            </div>
          </div>
          <div className="row">
            <button className="btn" onClick={() => nav(`/courses/${course.id}/marks`)}>All assessments</button>
            <button className="btn" onClick={() => download(`/assessments/${a.id}/scores/template`)}>↓ CSV</button>
            {editable && !rubric && <UploadButton label="Import CSV" onFile={async (f) => {
              if (dirty.size && !window.confirm("Importing will discard unsaved edits. Continue?")) return;
              try { const r = await upload<{ saved: number }>(`/assessments/${a.id}/scores/import`, f); toast(`Imported ${r.saved} rows`); reload(); }
              catch (e) { toast((e as Error).message, "error"); }
            }} />}
            {editable && <button className="btn btn-primary" disabled={!dirty.size || busy || invalid} onClick={save}>{busy ? "Saving…" : dirty.size ? `Save ${dirty.size} change${dirty.size > 1 ? "s" : ""}` : "Saved"}</button>}
          </div>
        </div>
        {!editable && <div className="alert alert-info" style={{ marginTop: 12 }}>
          {canEdit ? (a.status === "draft" ? "Open marking on this assessment to enter scores." : "Marking is closed. Reopen the assessment from the Assessments tab to make corrections.") : "View only."}
        </div>}
        {invalid && <div className="alert alert-bad" style={{ marginTop: 12 }}>Some values are outside 0–{limit}. Fix the highlighted cells before saving.</div>}
      </Card>

      <Card pad={false}>
        <div style={{ padding: "12px 16px" }}><input className="input" style={{ maxWidth: 280 }} placeholder="Filter by name or roll no." value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter students" /></div>
        <div className="table-wrap" style={{ maxHeight: "65vh" }}>
          <table className="table sticky compact">
            <thead><tr><th>Roll no</th><th>Student</th><th className="r">{isAtt ? `Attended / ${a.sessions_held}` : rubric ? "Rubric" : `Marks / ${a.max_marks}`}</th><th className="r">Marks</th><th className="r">%</th><th className="c">Absent</th><th>Feedback</th></tr></thead>
            <tbody>{shown.map((r, idx) => {
              const v = isAtt ? r.attended : r.marks;
              const bad = v !== null && (v < 0 || v > limit);
              const marks = valueOf(r);
              const p = marks === null ? null : (100 * marks) / a.max_marks;
              return (
                <tr key={r.student_id}>
                  <td className="num small">{r.roll_no}</td>
                  <td className="nowrap"><strong>{r.name}</strong>{dirty.has(r.student_id) && <span className="badge badge-info" style={{ marginLeft: 6 }}>edited</span>}</td>
                  <td className="r">
                    {rubric ? (
                      <button className="btn btn-sm" onClick={() => setScorer(rows.indexOf(r))} disabled={!rubric}>
                        {r.is_absent ? "Absent" : Object.keys(r.criteria).length === rubric.criteria.length ? "Review" : Object.keys(r.criteria).length ? `${Object.keys(r.criteria).length}/${rubric.criteria.length} criteria` : editable ? "Score" : "—"}
                      </button>
                    ) : (
                      <input className={`cell-input ${dirty.has(r.student_id) ? "dirty" : ""} ${bad ? "bad" : ""}`} data-cell={idx}
                        inputMode="decimal" disabled={!editable || r.is_absent} aria-label={`${isAtt ? "Attended" : "Marks"} for ${r.name}`}
                        value={v ?? ""} onKeyDown={(e) => onKeyDown(e, idx)}
                        onChange={(e) => {
                          const t = e.target.value.trim();
                          const n = t === "" ? null : Number(t);
                          if (t !== "" && Number.isNaN(n)) return;
                          change(r.student_id, isAtt ? { attended: n === null ? null : Math.round(n) } : { marks: n });
                        }} />
                    )}
                  </td>
                  <td className="r num">{marks === null ? "—" : marks.toFixed(1)}</td>
                  <td className="r num" style={{ color: p !== null && p < 40 ? "var(--critical-text)" : undefined }}>{p === null ? "—" : `${p.toFixed(0)}%`}</td>
                  <td className="c"><input type="checkbox" disabled={!editable} checked={r.is_absent} aria-label={`${r.name} absent`} onChange={(e) => change(r.student_id, { is_absent: e.target.checked })} /></td>
                  <td><input className="input" style={{ height: 30, minWidth: 180 }} disabled={!editable} value={r.feedback ?? ""} placeholder="Optional" aria-label={`Feedback for ${r.name}`} onChange={(e) => change(r.student_id, { feedback: e.target.value })} /></td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      </Card>
      {scorer !== null && rubric && <RubricScorer rubric={rubric} rows={rows} index={scorer} max={a.max_marks} editable={editable}
        onChange={change} onClose={() => setScorer(null)} onIndex={setScorer} />}
    </div>
  );

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>, idx: number) { onKey(e, idx); }
}
