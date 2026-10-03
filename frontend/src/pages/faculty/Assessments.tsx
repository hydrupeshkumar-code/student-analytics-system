import { useState } from "react";
import { Link } from "react-router-dom";
import { del, patch, post } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dateStr, titleCase, useFetch } from "../../lib/hooks";
import type { AStatus, Assessment, Component, Outcome, Rubric } from "../../lib/types";
import { Card, Empty, ErrorBox, Field, Meter, Modal, Spinner, StatusBadge, useConfirm, useToast } from "../../components/ui";
import { useCourse } from "./CourseWorkspace";

const COMPONENTS: Component[] = ["quiz", "assignment", "practical", "attendance", "other"];

function AssessmentForm({ courseId, a, remaining, onClose, onSaved }: {
  courseId: number; a?: Assessment; remaining: number; onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const rubrics = useFetch<Rubric[]>("/rubrics");
  const cos = useFetch<Outcome[]>(`/courses/${courseId}/outcomes`);
  const locked = !!a && a.graded_count > 0;
  const [f, setF] = useState({
    title: a?.title ?? "", component: a?.component ?? ("quiz" as Component), max_marks: String(a?.max_marks ?? 20),
    weightage: String(a?.weightage ?? Math.min(remaining, 15)), rubric_id: String(a?.rubric_id ?? ""),
    sessions_held: String(a?.sessions_held ?? ""), due_date: a?.due_date ?? "", co_ids: a?.co_ids ?? ([] as number[]),
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isAtt = f.component === "attendance";

  async function save() {
    setBusy(true); setError(null);
    const body: Record<string, unknown> = {
      title: f.title.trim(), max_marks: Number(f.max_marks), weightage: Number(f.weightage),
      rubric_id: !isAtt && f.rubric_id ? Number(f.rubric_id) : null,
      sessions_held: isAtt ? Number(f.sessions_held) || null : null, due_date: f.due_date || null, co_ids: f.co_ids,
    };
    try {
      if (a) await patch(`/assessments/${a.id}`, body);
      else await post(`/courses/${courseId}/assessments`, { ...body, component: f.component });
      toast(a ? "Assessment updated" : "Assessment created");
      onSaved();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Modal title={a ? `Edit ${a.title}` : "New CP assessment"} onClose={onClose} wide footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn btn-primary" disabled={busy || !f.title} onClick={save}>{busy ? "Saving…" : "Save"}</button>
    </>}>
      {error && <div className="alert alert-bad" style={{ marginBottom: 12 }}>{error}</div>}
      {locked && <div className="alert alert-warn" style={{ marginBottom: 12 }}>Marks have been entered, so maximum marks, rubric and sessions are locked.</div>}
      <div className="form-grid">
        <Field label="Title"><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="Quiz 1" /></Field>
        <Field label="CP component"><select className="input" value={f.component} disabled={!!a} onChange={(e) => setF({ ...f, component: e.target.value as Component })}>
          {COMPONENTS.map((c) => <option key={c} value={c}>{titleCase(c)}</option>)}
        </select></Field>
        <Field label="Maximum marks"><input className="input" type="number" min={1} disabled={locked} value={f.max_marks} onChange={(e) => setF({ ...f, max_marks: e.target.value })} /></Field>
        <Field label="Weightage in CP (%)" hint={`${remaining.toFixed(0)}% of CP still unallocated`}><input className="input" type="number" min={0} max={100} value={f.weightage} onChange={(e) => setF({ ...f, weightage: e.target.value })} /></Field>
        {isAtt ? (
          <Field label="Sessions held" hint="Marks = attended ÷ held × max marks"><input className="input" type="number" min={1} disabled={locked} value={f.sessions_held} onChange={(e) => setF({ ...f, sessions_held: e.target.value })} /></Field>
        ) : (
          <Field label="Scoring" hint="Rubric-scored assessments compute marks automatically"><select className="input" value={f.rubric_id} disabled={locked} onChange={(e) => setF({ ...f, rubric_id: e.target.value })}>
            <option value="">Direct marks entry</option>
            {rubrics.data?.map((r) => <option key={r.id} value={r.id}>Rubric: {r.title}</option>)}
          </select></Field>
        )}
        <Field label="Due / conducted on"><input className="input" type="date" value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} /></Field>
      </div>
      <div className="field" style={{ marginTop: 14 }}>
        <span>Course outcomes assessed</span>
        {cos.data?.length ? (
          <div className="row" style={{ gap: 14 }}>{cos.data.map((co) => (
            <label key={co.id} className="check" title={co.description}>
              <input type="checkbox" checked={f.co_ids.includes(co.id)} onChange={(e) => setF({ ...f, co_ids: e.target.checked ? [...f.co_ids, co.id] : f.co_ids.filter((x) => x !== co.id) })} />{co.code}
            </label>
          ))}</div>
        ) : <small className="hint">Define course outcomes in the “COs & mapping” tab to include this assessment in CO attainment.</small>}
      </div>
    </Modal>
  );
}

const ACTIONS: Record<AStatus, { to: AStatus; label: string; primary?: boolean }[]> = {
  draft: [{ to: "in_progress", label: "Open marking", primary: true }],
  in_progress: [{ to: "completed", label: "Mark completed", primary: true }, { to: "draft", label: "Back to draft" }],
  completed: [{ to: "finalized", label: "Finalize & lock" }, { to: "in_progress", label: "Reopen" }],
  finalized: [{ to: "in_progress", label: "Reopen (admin)" }],
};

export default function Assessments() {
  const { course, canEdit } = useCourse();
  const { user } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const { data, error, loading, reload } = useFetch<Assessment[]>(`/courses/${course.id}/assessments`);
  const [editing, setEditing] = useState<Assessment | "new" | null>(null);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  const list = data ?? [];
  const total = list.reduce((a, x) => a + x.weightage, 0);

  async function setStatus(a: Assessment, to: AStatus) {
    if (to === "finalized" && !(await confirm({ title: `Finalize ${a.title}?`, body: "Finalized marks are locked. Only an administrator can reopen them.", confirm: "Finalize" }))) return;
    if (to === "completed" && a.graded_count < course.student_count && !(await confirm({ title: "Some students have no score", body: `${course.student_count - a.graded_count} student(s) have no mark. After completion they count as 0 (not submitted). Continue?`, confirm: "Mark completed" }))) return;
    try { await post(`/assessments/${a.id}/status`, { status: to }); toast(`${a.title}: ${titleCase(to)}`); reload(); } catch (e) { toast((e as Error).message, "error"); }
  }
  async function remove(a: Assessment) {
    if (!(await confirm({ title: `Delete ${a.title}?`, body: "All marks for this assessment will be deleted.", confirm: "Delete", danger: true }))) return;
    try { await del(`/assessments/${a.id}`); toast("Assessment deleted"); reload(); } catch (e) { toast((e as Error).message, "error"); }
  }

  return (
    <div className="stack">
      <Card>
        <div className="spread">
          <div style={{ flex: 1, minWidth: 220 }}>
            <div className="small text-2" style={{ marginBottom: 6 }}>CP weightage allocated: <strong className="num">{total.toFixed(0)}%</strong> of 100%</div>
            <Meter value={total} color={total > 100 ? "var(--critical)" : undefined} />
            {total < 100 && list.length > 0 && <div className="small muted" style={{ marginTop: 6 }}>CP percentage is computed over the weightage allocated so far, so students are not penalised for assessments that have not happened yet.</div>}
          </div>
          {canEdit && <button className="btn btn-primary" onClick={() => setEditing("new")}>+ New assessment</button>}
        </div>
      </Card>
      <Card pad={false}>
        {!list.length ? <Empty title="No assessments yet">Create quizzes, assignments, practicals and attendance as CP components.</Empty> : (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Assessment</th><th>Component</th><th className="r">Max</th><th className="r">Weight</th><th>Scoring</th><th>Due</th><th>Status</th><th className="r">Scored</th><th /></tr></thead>
            <tbody>{list.map((a) => (
              <tr key={a.id}>
                <td><strong>{a.title}</strong></td>
                <td>{titleCase(a.component)}</td>
                <td className="r num">{a.max_marks}</td>
                <td className="r num">{a.weightage}%</td>
                <td className="small">{a.component === "attendance" ? `${a.sessions_held} sessions` : a.rubric_id ? "Rubric" : "Direct"}</td>
                <td className="small nowrap">{dateStr(a.due_date)}</td>
                <td><StatusBadge status={a.status} /></td>
                <td className="r num">{a.graded_count}/{course.student_count}</td>
                <td className="r nowrap">
                  {a.status !== "draft" && <Link className="btn btn-sm" to={`/courses/${course.id}/marks/${a.id}`}>{a.status === "in_progress" && canEdit ? "Enter marks" : "View marks"}</Link>}{" "}
                  {canEdit && ACTIONS[a.status].filter(() => a.status !== "finalized" || user?.role === "admin").map((x) => (
                    <button key={x.to} className={`btn btn-sm ${x.primary ? "btn-primary" : "btn-ghost"}`} onClick={() => setStatus(a, x.to)}>{x.label}</button>
                  ))}
                  {canEdit && a.status !== "finalized" && <>
                    <button className="btn btn-sm btn-ghost" onClick={() => setEditing(a)}>Edit</button>
                    <button className="btn btn-sm btn-ghost btn-danger" onClick={() => remove(a)} aria-label={`Delete ${a.title}`}>Delete</button>
                  </>}
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      <p className="small muted">Lifecycle: Draft → Marking open → Completed (visible to students) → Finalized (locked). Completed assessments can be reopened for corrections.</p>
      {editing && <AssessmentForm courseId={course.id} a={editing === "new" ? undefined : editing}
        remaining={100 - total + (editing !== "new" ? editing.weightage : 0)}
        onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />}
    </div>
  );
}
