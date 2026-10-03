import { useEffect, useState } from "react";
import { download, patch, post, put, upload } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/hooks";
import { Card, ErrorBox, Spinner, UploadButton, useConfirm, useToast } from "../../components/ui";
import { useCourse } from "./CourseWorkspace";

interface NcpRow { id: number; name: string; roll_no: string | null; marks: number | null; is_absent: boolean }
interface NcpResp { max_marks: number; published: boolean; students: NcpRow[] }

export default function NcpEntry() {
  const { course, canEdit, reloadCourse } = useCourse();
  const toast = useToast();
  const confirm = useConfirm();
  const { user } = useAuth();
  const { data, error, loading, reload, setData } = useFetch<NcpResp>(`/courses/${course.id}/ncp`);
  const [rows, setRows] = useState<NcpRow[]>([]);
  const [dirty, setDirty] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) { setRows(data.students); setDirty(new Set()); } }, [data]);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;

  const max = data.max_marks;
  const invalid = rows.some((r) => r.marks !== null && (r.marks < 0 || r.marks > max));
  const entered = rows.filter((r) => r.marks !== null || r.is_absent).length;
  const change = (id: number, p: Partial<NcpRow>) => { setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...p } : r))); setDirty((d) => new Set(d).add(id)); };

  async function save() {
    setBusy(true);
    try {
      const res = await put<NcpResp>(`/courses/${course.id}/ncp`, { results: rows.filter((r) => dirty.has(r.id)).map((r) => ({ student_id: r.id, marks: r.marks, is_absent: r.is_absent })) });
      setData(res); toast("Semester-end marks saved");
    } catch (e) { toast((e as Error).message, "error"); } finally { setBusy(false); }
  }
  async function togglePublish() {
    const next = !data!.published;
    if (next && !(await confirm({ title: "Publish semester-end results?", body: `Students will see their NCP marks, final percentage and grade. ${entered}/${rows.length} results are entered.`, confirm: "Publish" }))) return;
    try { await patch(`/courses/${course.id}`, { ncp_published: next }); toast(next ? "Results published to students" : "Results hidden from students"); reload(); reloadCourse(); }
    catch (e) { toast((e as Error).message, "error"); }
  }

  return (
    <div className="stack">
      <Card>
        <div className="spread">
          <div>
            <h2>Semester-end examination (NCP)</h2>
            <div className="small text-2" style={{ marginTop: 4 }}>Out of {max} marks · {entered}/{rows.length} entered · {data.published ? "Published to students" : "Not yet visible to students"}</div>
          </div>
          <div className="row">
            <button className="btn" onClick={() => download(`/courses/${course.id}/ncp/template`)}>↓ CSV template</button>
            {canEdit && <>
              <UploadButton label="Import CSV" onFile={async (f) => {
                try { const r = await upload<{ saved: number }>(`/courses/${course.id}/ncp/import`, f); toast(`Imported ${r.saved} results`); reload(); }
                catch (e) { toast((e as Error).message, "error"); }
              }} />
              {user?.role === "admin" && data.published && <button className="btn" title="Copy anonymised CP–NCP outcomes into the early-warning training set" onClick={async () => {
                if (!(await confirm({ title: "Add to training history?", body: "Anonymised CP component scores and pass/fail outcomes (no names or roll numbers) are copied into the early-warning model's training data. Do this once per completed course.", confirm: "Add records" }))) return;
                try { const r = await post<{ added: number }>(`/courses/${course.id}/harvest`); toast(`${r.added} anonymised records added — retrain the model to use them`); }
                catch (e) { toast((e as Error).message, "error"); }
              }}>Add to ML history</button>}
              <button className="btn" onClick={togglePublish}>{data.published ? "Unpublish" : "Publish results"}</button>
              <button className="btn btn-primary" disabled={!dirty.size || busy || invalid} onClick={save}>{busy ? "Saving…" : dirty.size ? `Save ${dirty.size}` : "Saved"}</button>
            </>}
          </div>
        </div>
        <p className="small muted" style={{ marginTop: 8 }}>CSV columns: roll_no, marks (write AB for absent). Results combine with CP in the consolidated result.</p>
      </Card>
      <Card pad={false}>
        <div className="table-wrap" style={{ maxHeight: "65vh" }}>
          <table className="table sticky compact">
            <thead><tr><th>Roll no</th><th>Student</th><th className="r">Marks / {max}</th><th className="r">%</th><th className="c">Absent</th></tr></thead>
            <tbody>{rows.map((r, i) => {
              const bad = r.marks !== null && (r.marks < 0 || r.marks > max);
              return (
                <tr key={r.id}>
                  <td className="small num">{r.roll_no}</td>
                  <td><strong>{r.name}</strong></td>
                  <td className="r"><input className={`cell-input ${dirty.has(r.id) ? "dirty" : ""} ${bad ? "bad" : ""}`} data-ncp={i} inputMode="decimal" disabled={!canEdit || r.is_absent}
                    value={r.marks ?? ""} aria-label={`NCP marks for ${r.name}`}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === "ArrowDown") { e.preventDefault(); document.querySelector<HTMLInputElement>(`[data-ncp="${i + 1}"]`)?.focus(); } if (e.key === "ArrowUp") { e.preventDefault(); document.querySelector<HTMLInputElement>(`[data-ncp="${i - 1}"]`)?.focus(); } }}
                    onChange={(e) => { const t = e.target.value.trim(); const n = t === "" ? null : Number(t); if (t === "" || !Number.isNaN(n)) change(r.id, { marks: n }); }} /></td>
                  <td className="r num">{r.is_absent ? "AB" : r.marks === null ? "—" : `${((100 * r.marks) / max).toFixed(0)}%`}</td>
                  <td className="c"><input type="checkbox" disabled={!canEdit} checked={r.is_absent} aria-label={`${r.name} absent`} onChange={(e) => change(r.id, { is_absent: e.target.checked, marks: e.target.checked ? null : r.marks })} /></td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
