import { useState } from "react";
import { Link } from "react-router-dom";
import { patch, post, del } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/hooks";
import type { Course, Paged, Program, User } from "../../lib/types";
import { Card, Empty, ErrorBox, Field, Modal, PageHead, Spinner, useConfirm, useToast } from "../../components/ui";

const blank = { code: "", name: "", program_id: "", faculty_id: "", semester: "1", academic_year: "2026-27", section: "A", credits: "3", cp_weight: "50", ncp_weight: "50", ncp_max_marks: "100" };

export function CourseForm({ course, onClose, onSaved }: { course?: Course; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const programs = useFetch<Program[]>("/programs");
  const faculty = useFetch<Paged<User>>("/users?role=faculty&active=true&page_size=500");
  const [f, setF] = useState(() => course ? {
    code: course.code, name: course.name, program_id: String(course.program_id ?? ""), faculty_id: String(course.faculty_id ?? ""),
    semester: String(course.semester), academic_year: course.academic_year, section: course.section, credits: String(course.credits),
    cp_weight: String(course.cp_weight), ncp_weight: String(course.ncp_weight), ncp_max_marks: String(course.ncp_max_marks),
  } : blank);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof blank) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  async function save() {
    setBusy(true);
    setError(null);
    const body = {
      code: f.code.trim(), name: f.name.trim(), program_id: f.program_id ? Number(f.program_id) : null,
      faculty_id: f.faculty_id ? Number(f.faculty_id) : null, semester: Number(f.semester), academic_year: f.academic_year.trim(),
      section: f.section.trim() || "A", credits: Number(f.credits), cp_weight: Number(f.cp_weight), ncp_weight: Number(f.ncp_weight),
      ncp_max_marks: Number(f.ncp_max_marks),
    };
    try {
      if (course) await patch(`/courses/${course.id}`, body); else await post("/courses", body);
      toast(course ? "Course updated" : "Course created");
      onSaved();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Modal title={course ? `Edit ${course.code}` : "New course"} onClose={onClose} wide footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn btn-primary" disabled={busy || !f.code || !f.name} onClick={save}>{busy ? "Saving…" : "Save course"}</button>
    </>}>
      {error && <div className="alert alert-bad" style={{ marginBottom: 12 }}>{error}</div>}
      <div className="form-grid">
        <Field label="Course code"><input className="input" value={f.code} onChange={set("code")} placeholder="CS301" /></Field>
        <Field label="Course name"><input className="input" value={f.name} onChange={set("name")} placeholder="Software Engineering" /></Field>
        <Field label="Program"><select className="input" value={f.program_id} onChange={set("program_id")}>
          <option value="">— none —</option>{programs.data?.map((p) => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>)}
        </select></Field>
        <Field label="Course faculty"><select className="input" value={f.faculty_id} onChange={set("faculty_id")}>
          <option value="">— unassigned —</option>{faculty.data?.items.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </select></Field>
        <Field label="Academic year" hint="Format 2026-27"><input className="input" value={f.academic_year} onChange={set("academic_year")} /></Field>
        <Field label="Semester"><input className="input" type="number" min={1} max={12} value={f.semester} onChange={set("semester")} /></Field>
        <Field label="Section"><input className="input" value={f.section} onChange={set("section")} /></Field>
        <Field label="Credits"><input className="input" type="number" min={0} step={0.5} value={f.credits} onChange={set("credits")} /></Field>
        <Field label="CP weight (%)" hint="Continuous process share of the final mark"><input className="input" type="number" value={f.cp_weight} onChange={(e) => setF({ ...f, cp_weight: e.target.value, ncp_weight: String(100 - Number(e.target.value)) })} /></Field>
        <Field label="NCP weight (%)" hint="Semester-end exam share"><input className="input" type="number" value={f.ncp_weight} onChange={(e) => setF({ ...f, ncp_weight: e.target.value, cp_weight: String(100 - Number(e.target.value)) })} /></Field>
        <Field label="NCP maximum marks"><input className="input" type="number" value={f.ncp_max_marks} onChange={set("ncp_max_marks")} /></Field>
      </div>
    </Modal>
  );
}

export default function Courses() {
  const { user } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const [archived, setArchived] = useState(false);
  const { data, error, loading, reload } = useFetch<Course[]>(`/courses?include_archived=${archived}`);
  const [editing, setEditing] = useState<Course | "new" | null>(null);
  const isAdmin = user?.role === "admin";

  async function remove(c: Course) {
    if (!(await confirm({ title: `Delete ${c.code}?`, body: "All assessments, marks, NCP results and predictions for this course will be permanently removed. Archive it instead to keep the records.", confirm: "Delete course", danger: true }))) return;
    try { await del(`/courses/${c.id}`); toast("Course deleted"); reload(); } catch (e) { toast((e as Error).message, "error"); }
  }
  async function archive(c: Course) {
    try { await patch(`/courses/${c.id}`, { is_archived: !c.is_archived }); toast(c.is_archived ? "Course restored" : "Course archived"); reload(); } catch (e) { toast((e as Error).message, "error"); }
  }

  return (
    <>
      <PageHead title={isAdmin ? "Courses" : "My courses"} subtitle={isAdmin ? "Course offerings, faculty assignment and CP/NCP weighting." : "Open a course to manage assessments, marks and reports."}
        actions={<>
          <label className="check small"><input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} /> Show archived</label>
          {isAdmin && <button className="btn btn-primary" onClick={() => setEditing("new")}>+ New course</button>}
        </>} />
      {loading && !data ? <Spinner /> : error ? <ErrorBox error={error} onRetry={reload} /> : (
        <Card pad={false}>
          {!data?.length ? <Empty title="No courses yet">{isAdmin ? "Create a course and assign a faculty member." : "You have not been assigned any course."}</Empty> : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Course</th><th>Year · Sem · Sec</th><th>Faculty</th><th className="r">Students</th><th>CP / NCP</th><th /></tr></thead>
              <tbody>{data.map((c) => (
                <tr key={c.id}>
                  <td><Link to={`/courses/${c.id}`}><strong>{c.code}</strong> {c.name}</Link>{c.is_archived && <span className="badge" style={{ marginLeft: 8 }}>Archived</span>}
                    <div className="small muted">{c.program_name ?? "No program"}</div></td>
                  <td className="nowrap">{c.academic_year} · {c.semester} · {c.section}</td>
                  <td>{c.faculty_name ?? <span className="muted">Unassigned</span>}</td>
                  <td className="r num">{c.student_count}</td>
                  <td className="num">{c.cp_weight} / {c.ncp_weight}</td>
                  <td className="r nowrap">
                    <Link className="btn btn-sm" to={`/courses/${c.id}`}>Open</Link>{" "}
                    {isAdmin && <>
                      <button className="btn btn-sm btn-ghost" onClick={() => setEditing(c)}>Edit</button>
                      <button className="btn btn-sm btn-ghost" onClick={() => archive(c)}>{c.is_archived ? "Restore" : "Archive"}</button>
                      <button className="btn btn-sm btn-ghost btn-danger" onClick={() => remove(c)}>Delete</button>
                    </>}
                  </td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>
      )}
      {editing && <CourseForm course={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />}
    </>
  );
}
