import { useState, type FormEvent } from "react";
import { post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTimeStr } from "../lib/hooks";
import type { User } from "../lib/types";
import { Card, PageHead, useToast } from "../components/ui";

export function ChangePasswordForm({ forced }: { forced?: boolean }) {
  const { setSession } = useAuth();
  const toast = useToast();
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const weak = next.length > 0 && (next.length < 8 || !/\d/.test(next) || !/[A-Za-z]/.test(next));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (next !== again) return setError("The new passwords do not match");
    setBusy(true);
    setError(null);
    try {
      const t = await post<{ access_token: string; refresh_token: string; user: User }>("/auth/change-password", { current_password: cur, new_password: next });
      setSession(t);
      toast("Password updated. Other sessions have been signed out.");
      setCur(""); setNext(""); setAgain("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="stack" style={{ gap: 12, maxWidth: 380 }}>
      {forced && <div className="alert alert-info">For security, please replace the temporary password before continuing.</div>}
      {error && <div className="alert alert-bad" role="alert">{error}</div>}
      <label className="field"><span>Current password</span><input className="input" type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} /></label>
      <label className="field"><span>New password</span>
        <input className="input" type="password" autoComplete="new-password" value={next} aria-invalid={weak} onChange={(e) => setNext(e.target.value)} />
        <small className="hint">At least 8 characters with letters and numbers.</small>
      </label>
      <label className="field"><span>Confirm new password</span><input className="input" type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} /></label>
      <div><button className="btn btn-primary" disabled={busy || !cur || !next || weak}>{busy ? "Saving…" : "Change password"}</button></div>
    </form>
  );
}

export function ForcePasswordChange() {
  const { user, logout } = useAuth();
  return (
    <div className="center" style={{ minHeight: "100%" }}>
      <div className="card card-pad" style={{ width: "min(440px, 100%)" }}>
        <h2 style={{ marginBottom: 4 }}>Welcome, {user?.name}</h2>
        <p className="text-2" style={{ marginBottom: 16 }}>Set a new password to activate your account.</p>
        <ChangePasswordForm forced />
        <button className="btn btn-ghost btn-sm" style={{ marginTop: 12 }} onClick={logout}>Sign out</button>
      </div>
    </div>
  );
}

export default function Account() {
  const { user, logout } = useAuth();
  const toast = useToast();
  if (!user) return null;
  return (
    <>
      <PageHead title="Account" subtitle="Your profile and sign-in security." />
      <div className="grid grid-2">
        <Card title="Profile">
          <dl className="kv">
            <dt>Name</dt><dd>{user.name}</dd>
            <dt>Email</dt><dd>{user.email}</dd>
            <dt>Role</dt><dd style={{ textTransform: "capitalize" }}>{user.role}</dd>
            {user.department && <><dt>Department</dt><dd>{user.department}</dd></>}
            {user.student_profile && <>
              <dt>Roll number</dt><dd>{user.student_profile.roll_no}</dd>
              <dt>Batch</dt><dd>{user.student_profile.batch ?? "—"}</dd>
              <dt>Semester / section</dt><dd>{user.student_profile.semester ?? "—"} / {user.student_profile.section ?? "—"}</dd>
            </>}
            <dt>Last sign-in</dt><dd>{dateTimeStr(user.last_login_at)}</dd>
          </dl>
          <div className="divider" />
          <button className="btn btn-sm" onClick={async () => { await post("/auth/logout-all"); toast("Signed out everywhere"); logout(); }}>Sign out of all devices</button>
        </Card>
        <Card title="Change password"><ChangePasswordForm /></Card>
      </div>
    </>
  );
}
