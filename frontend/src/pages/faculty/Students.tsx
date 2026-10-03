import { useState } from "react";
import { del, post, upload } from "../../lib/api";
import { useDebounced, useFetch } from "../../lib/hooks";
import type { Paged, User } from "../../lib/types";
import { Card, Empty, ErrorBox, Modal, Spinner, UploadButton, useConfirm, useToast } from "../../components/ui";
import { useCourse } from "./CourseWorkspace";

interface Enrolled { id: number; name: string; email: string; roll_no: string | null; section: string | null; is_active: boolean }

function AddStudents({ courseId, enrolled, onClose, onDone }: { courseId: number; enrolled: Set<number>; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [rolls, setRolls] = useState("");
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const { data, loading } = useFetch<Paged<User>>(`/users?role=student&active=true&page_size=100&q=${encodeURIComponent(dq)}`);

  async function submit() {
    const roll_nos = rolls.split(/[\s,;]+/).map((r) => r.trim()).filter(Boolean);
    try {
      const r = await post<{ added: number; unknown_roll_nos: string[] }>(`/courses/${courseId}/students`, { student_ids: [...picked], roll_nos });
      toast(`${r.added} student(s) enrolled${r.unknown_roll_nos.length ? ` · unknown: ${r.unknown_roll_nos.join(", ")}` : ""}`, r.unknown_roll_nos.length ? "error" : "ok");
      onDone();
    } catch (e) { toast((e as Error).message, "error"); }
  }

  return (
    <Modal title="Enrol students" onClose={onClose} wide footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn btn-primary" disabled={!picked.size && !rolls.trim()} onClick={submit}>Enrol {picked.size ? picked.size : ""}</button>
    </>}>
      <div className="grid grid-2">
        <div className="stack" style={{ gap: 8 }}>
          <input className="input" placeholder="Search name, email or roll no." value={q} onChange={(e) => setQ(e.target.value)} />
          <div style={{ maxHeight: 320, overflow: "auto", border: "1px solid var(--border)", borderRadius: 12 }}>
            {loading ? <Spinner /> : data?.items.map((u) => {
              const already = enrolled.has(u.id);
              return (
                <label key={u.id} className="check" style={{ display: "flex", padding: "6px 10px", borderBottom: "1px solid var(--border)", opacity: already ? 0.5 : 1 }}>
                  <input type="checkbox" disabled={already} checked={already || picked.has(u.id)} onChange={(e) => { const s = new Set(picked); if (e.target.checked) s.add(u.id); else s.delete(u.id); setPicked(s); }} />
                  <span style={{ flex: 1 }}>{u.name}</span><span className="small muted num">{u.student_profile?.roll_no}</span>
                </label>
              );
            })}
          </div>
        </div>
        <label className="field"><span>…or paste roll numbers</span>
          <textarea className="input" rows={12} value={rolls} onChange={(e) => setRolls(e.target.value)} placeholder={"24STUCHH010001\n24STUCHH010002"} />
          <small className="hint">Separated by new lines, commas or spaces.</small>
        </label>
      </div>
    </Modal>
  );
}

export default function Students() {
  const { course, canEdit, reloadCourse } = useCourse();
  const toast = useToast();
  const confirm = useConfirm();
  const { data, error, loading, reload } = useFetch<Enrolled[]>(`/courses/${course.id}/students`);
  const [adding, setAdding] = useState(false);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  const refresh = () => { reload(); reloadCourse(); };

  async function remove(s: Enrolled) {
    if (!(await confirm({ title: `Remove ${s.name}?`, body: "Their marks stay in the database but are excluded from course results while unenrolled.", confirm: "Remove", danger: true }))) return;
    try { await del(`/courses/${course.id}/students/${s.id}`); toast("Student removed"); refresh(); } catch (e) { toast((e as Error).message, "error"); }
  }

  return (
    <Card title={`Enrolled students (${data?.length ?? 0})`} pad={false} actions={canEdit && <>
      <UploadButton label="Import roll numbers" onFile={async (f) => {
        try { const r = await upload<{ added: number; unknown_roll_nos: string[] }>(`/courses/${course.id}/students/import`, f); toast(`${r.added} enrolled${r.unknown_roll_nos.length ? ` · ${r.unknown_roll_nos.length} unknown` : ""}`); refresh(); }
        catch (e) { toast((e as Error).message, "error"); }
      }} />
      <button className="btn btn-primary" onClick={() => setAdding(true)}>+ Enrol students</button>
    </>}>
      {!data?.length ? <Empty title="No students enrolled">Enrol students individually or import a CSV with a roll_no column.</Empty> : (
        <div className="table-wrap"><table className="table">
          <thead><tr><th>Roll no</th><th>Name</th><th>Email</th><th>Section</th><th /></tr></thead>
          <tbody>{data.map((s) => (
            <tr key={s.id}><td className="num small">{s.roll_no}</td><td><strong>{s.name}</strong>{!s.is_active && <span className="badge" style={{ marginLeft: 6 }}>Inactive</span>}</td>
              <td className="small">{s.email}</td><td>{s.section ?? "—"}</td>
              <td className="r">{canEdit && <button className="btn btn-sm btn-ghost btn-danger" onClick={() => remove(s)}>Remove</button>}</td></tr>
          ))}</tbody>
        </table></div>
      )}
      {adding && <AddStudents courseId={course.id} enrolled={new Set(data?.map((s) => s.id))} onClose={() => setAdding(false)} onDone={() => { setAdding(false); refresh(); }} />}
    </Card>
  );
}
