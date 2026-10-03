import { useState, type FormEvent } from "react";
import { useAuth } from "../lib/auth";
import { StudyIllustration } from "../components/Illustrations";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-hero">
        <div className="row" style={{ gap: 12 }}>
          <div className="brand-mark">S</div>
          <div><div className="brand-name">SAAP</div><div className="brand-sub">Student Assessment &amp; Analytics</div></div>
        </div>

        <div>
          <span className="badge" style={{ background: "rgba(255,255,255,.18)", color: "#fff", marginBottom: 16 }}>Continuous evaluation, unified</span>
          <h1>Every quiz, rubric and exam in <em>one clear record</em> for each student.</h1>
          <p className="lede">CP and NCP marks in one ledger, rubric-scored automatically, with CO/PO attainment ready for NAAC/NBA and early warnings before results are declared.</p>
        </div>

        <div className="row" style={{ alignItems: "flex-end", gap: 24, flexWrap: "nowrap" }}>
        <div className="specimen" aria-hidden>
          <div className="spread" style={{ marginBottom: 8 }}>
            <span style={{ fontSize: 15, fontWeight: 600 }}>CS301 · Software Engineering</span>
            <span className="badge" style={{ background: "#e3f6ec", color: "#157a50" }}>2026-27</span>
          </div>
          <div className="row-l hd"><span>Component</span><span>Score</span><span>Weight</span></div>
          <div className="row-l"><span>Quiz average</span><span>72%</span><span>30</span></div>
          <div className="row-l"><span>Assignment · rubric</span><span>81%</span><span>20</span></div>
          <div className="row-l"><span>Lab evaluation · rubric</span><span>76%</span><span>25</span></div>
          <div className="row-l"><span>Attendance</span><span>88%</span><span>10</span></div>
          <div className="row-l" style={{ borderBottom: "none", fontWeight: 600 }}><span>CP total</span><span>77.4%</span><span /></div>
          <span className="stamp">Low risk</span>
        </div>
        <StudyIllustration className="illus" />
        </div>
      </div>

      <div className="login-form">
        <form onSubmit={submit} noValidate>
          <div>
            <h2 style={{ fontSize: 26 }}>Welcome back 👋</h2>
            <p className="text-2" style={{ marginTop: 6 }}>Use the account issued by your institution.</p>
          </div>
          {error && <div className="alert alert-bad" role="alert">{error}</div>}
          <label className="field"><span>Email</span>
            <input className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field"><span>Password</span>
            <input className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          <button className="btn btn-primary" style={{ height: 44, fontSize: 15 }} disabled={busy || !email || !password}>{busy ? "Signing in…" : "Sign in →"}</button>
          <p className="small muted">Forgot your password? The exam cell or administrator can reset it for you.</p>
        </form>
      </div>
    </div>
  );
}
