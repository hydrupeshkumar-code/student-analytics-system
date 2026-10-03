import { useState } from "react";
import { del, download, patch, post, upload } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dateTimeStr, useDebounced, useFetch } from "../../lib/hooks";
import type { Paged, Program, Role, User } from "../../lib/types";
import { Card, Empty, ErrorBox, Field, Modal, PageHead, SecretBox, Spinner, UploadButton, useConfirm, useToast } from "../../components/ui";

function UserForm({ user, onClose, onSaved }: { user?: User; onClose: () => void; onSaved: (temp?: string) => void }) {
  const programs = useFetch<Program[]>("/programs");
  const sp = user?.student_profile;
  const [f, setF] = useState({
    name: user?.name ?? "", email: user?.email ?? "", role: (user?.role ?? "student") as Role, department: user?.department ?? "",
    roll_no: sp?.roll_no ?? "", program_id: String(sp?.program_id ?? ""), batch: sp?.batch ?? "", semester: String(sp?.semester ?? ""), section: sp?.section ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  async function save() {
    setBusy(true); setError(null);
    const profile = f.role === "student" ? { roll_no: f.roll_no.trim(), program_id: f.program_id ? Number(f.program_id) : null, batch: f.batch || null, semester: f.semester ? Number(f.semester) : null, section: f.section || null } : undefined;
    const body = { name: f.name.trim(), email: f.email.trim(), role: f.role, department: f.department || null, student_profile: profile };
    try {
      if (user) { await patch(`/users/${user.id}`, body); onSaved(); }
      else { const r = await post<{ temporary_password: string }>("/users", body); onSaved(r.temporary_password); }
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Modal title={user ? `Edit ${user.name}` : "New user"} onClose={onClose} wide footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn btn-primary" disabled={busy || !f.name || !f.email || (f.role === "student" && !f.roll_no)} onClick={save}>{busy ? "Saving…" : user ? "Save" : "Create user"}</button>
    </>}>
      {error && <div className="alert alert-bad" style={{ marginBottom: 12 }}>{error}</div>}
      <div className="form-grid">
        <Field label="Full name"><input className="input" value={f.name} onChange={set("name")} /></Field>
        <Field label="Email"><input className="input" type="email" value={f.email} onChange={set("email")} /></Field>
        <Field label="Role"><select className="input" value={f.role} onChange={set("role")}><option value="student">Student</option><option value="faculty">Faculty</option><option value="admin">Administrator</option></select></Field>
        <Field label="Department"><input className="input" value={f.department} onChange={set("department")} /></Field>
        {f.role === "student" && <>
          <Field label="Roll number"><input className="input" value={f.roll_no} onChange={set("roll_no")} /></Field>
          <Field label="Program"><select className="input" value={f.program_id} onChange={set("program_id")}><option value="">—</option>{programs.data?.map((p) => <option key={p.id} value={p.id}>{p.code}</option>)}</select></Field>
          <Field label="Batch"><input className="input" value={f.batch} onChange={set("batch")} placeholder="2024-28" /></Field>
          <Field label="Semester"><input className="input" type="number" min={1} max={12} value={f.semester} onChange={set("semester")} /></Field>
          <Field label="Section"><input className="input" value={f.section} onChange={set("section")} /></Field>
        </>}
      </div>
      {!user && <p className="small muted" style={{ marginTop: 12 }}>A temporary password is generated and shown once. The user must change it at first sign-in.</p>}
    </Modal>
  );
}

export default function Users() {
  const { user: me } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const [role, setRole] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const { data, error, loading, reload } = useFetch<Paged<User>>(`/users?page=${page}&page_size=25&q=${encodeURIComponent(dq)}${role ? `&role=${role}` : ""}`);
  const [editing, setEditing] = useState<User | "new" | null>(null);
  const [secret, setSecret] = useState<{ who: string; pw: string } | null>(null);
  const [creds, setCreds] = useState<string[][] | null>(null);
  const pages = data ? Math.max(1, Math.ceil(data.total / 25)) : 1;

  async function reset(u: User) {
    if (!(await confirm({ title: `Reset password for ${u.name}?`, body: "Their current sessions are signed out and a temporary password is generated.", confirm: "Reset password" }))) return;
    try { const r = await post<{ temporary_password: string }>(`/users/${u.id}/reset-password`); setSecret({ who: u.email, pw: r.temporary_password }); } catch (e) { toast((e as Error).message, "error"); }
  }
  async function toggleActive(u: User) {
    try { await patch(`/users/${u.id}`, { is_active: !u.is_active }); toast(u.is_active ? "User deactivated" : "User activated"); reload(); } catch (e) { toast((e as Error).message, "error"); }
  }
  async function remove(u: User) {
    if (!(await confirm({ title: `Delete ${u.name}?`, body: "This permanently deletes the account and, for students, all of their marks. Deactivate instead to keep records.", confirm: "Delete permanently", danger: true }))) return;
    try { await del(`/users/${u.id}`); toast("User deleted"); reload(); } catch (e) { toast((e as Error).message, "error"); }
  }
  function saveCreds() {
    if (!creds) return;
    const csv = creds.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url; a.download = "new_user_credentials.csv"; a.click(); URL.revokeObjectURL(url);
  }

  return (
    <>
      <PageHead title="Users" subtitle="Accounts and roles for administrators, faculty and students." actions={<>
        <button className="btn" onClick={() => download("/users/import/template")}>↓ CSV template</button>
        <UploadButton label="Bulk import" onFile={async (f) => {
          try {
            const r = await upload<{ created: number; errors: { line: number; error: string }[]; credentials?: string[][] }>("/users/import", f);
            if (r.errors.length) toast(`Nothing imported — ${r.errors.slice(0, 3).map((e) => `line ${e.line}: ${e.error}`).join("; ")}${r.errors.length > 3 ? "…" : ""}`, "error");
            else { toast(`${r.created} users created`); setCreds(r.credentials ?? null); reload(); }
          } catch (e) { toast((e as Error).message, "error"); }
        }} />
        <button className="btn btn-primary" onClick={() => setEditing("new")}>+ New user</button>
      </>} />
      <Card pad={false}>
        <div className="row" style={{ padding: "12px 16px" }}>
          <input className="input" style={{ maxWidth: 280 }} placeholder="Search name, email, roll no." value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Search users" />
          <div className="segmented" role="group" aria-label="Filter by role">
            {["", "student", "faculty", "admin"].map((r) => <button key={r} className={role === r ? "active" : ""} onClick={() => { setRole(r); setPage(1); }}>{r ? r[0].toUpperCase() + r.slice(1) : "All"}</button>)}
          </div>
          <span className="small muted" style={{ marginLeft: "auto" }}>{data?.total ?? 0} users</span>
        </div>
        {loading && !data ? <Spinner /> : error ? <div style={{ padding: 16 }}><ErrorBox error={error} onRetry={reload} /></div> : !data?.items.length ? <Empty title="No users match" /> : (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Roll no / dept</th><th>Last sign-in</th><th>Status</th><th /></tr></thead>
            <tbody>{data.items.map((u) => (
              <tr key={u.id}>
                <td><strong>{u.name}</strong></td><td className="small">{u.email}</td>
                <td style={{ textTransform: "capitalize" }}>{u.role}</td>
                <td className="small">{u.student_profile?.roll_no ?? u.department ?? "—"}</td>
                <td className="small">{dateTimeStr(u.last_login_at)}</td>
                <td>{u.is_active ? (u.must_change_password ? <span className="badge badge-warn">Pending first login</span> : <span className="badge badge-good">Active</span>) : <span className="badge">Inactive</span>}</td>
                <td className="r nowrap">
                  <button className="btn btn-sm btn-ghost" onClick={() => setEditing(u)}>Edit</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => reset(u)}>Reset password</button>
                  {u.id !== me?.id && <>
                    <button className="btn btn-sm btn-ghost" onClick={() => toggleActive(u)}>{u.is_active ? "Deactivate" : "Activate"}</button>
                    <button className="btn btn-sm btn-ghost btn-danger" onClick={() => remove(u)}>Delete</button>
                  </>}
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        {pages > 1 && <div className="row" style={{ padding: 12, justifyContent: "flex-end" }}>
          <button className="btn btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</button>
          <span className="small">Page {page} of {pages}</span>
          <button className="btn btn-sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next →</button>
        </div>}
      </Card>
      {editing && <UserForm user={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} onSaved={(temp) => {
        const who = editing === "new" ? "the new user" : editing.email; setEditing(null); reload();
        if (temp) setSecret({ who, pw: temp }); else toast("User updated");
      }} />}
      {secret && <Modal title="Temporary password" onClose={() => setSecret(null)} footer={<button className="btn btn-primary" onClick={() => setSecret(null)}>Done</button>}>
        <p className="text-2" style={{ marginBottom: 10 }}>Share this with {secret.who} through a secure channel. It is shown only once and must be changed at first sign-in.</p>
        <SecretBox value={secret.pw} />
      </Modal>}
      {creds && <Modal title={`${creds.length - 1} users created`} onClose={() => setCreds(null)} footer={<><button className="btn" onClick={() => setCreds(null)}>Close</button><button className="btn btn-primary" onClick={saveCreds}>↓ Download credentials CSV</button></>}>
        <div className="alert alert-warn">Download the temporary passwords now — they cannot be shown again. Distribute them securely and delete the file afterwards.</div>
      </Modal>}
    </>
  );
}
