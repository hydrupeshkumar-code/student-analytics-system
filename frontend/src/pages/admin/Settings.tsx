import { useEffect, useState } from "react";
import { put } from "../../lib/api";
import { useFetch } from "../../lib/hooks";
import type { Settings as S } from "../../lib/types";
import { Card, ErrorBox, Field, PageHead, Spinner, useToast } from "../../components/ui";

export default function Settings() {
  const toast = useToast();
  const { data, error, loading, reload } = useFetch<S>("/settings");
  const [s, setS] = useState<S | null>(null);
  useEffect(() => { if (data) setS(structuredClone(data)); }, [data]);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!s) return null;
  const num = (k: keyof S) => (e: React.ChangeEvent<HTMLInputElement>) => setS({ ...s, [k]: Number(e.target.value) });

  async function save() {
    try { setS(await put<S>("/settings", s)); toast("Settings saved"); } catch (e) { toast((e as Error).message, "error"); }
  }

  return (
    <>
      <PageHead title="Academic settings" subtitle="Institution-wide rules used for results, alerts and early warning." actions={<button className="btn btn-primary" onClick={save}>Save settings</button>} />
      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <Card title="Pass rules & alerts">
          <div className="form-grid">
            <Field label="Pass mark — final (%)"><input className="input" type="number" value={s.pass_mark_pct} onChange={num("pass_mark_pct")} /></Field>
            <Field label="Minimum in semester-end (%)"><input className="input" type="number" value={s.ncp_min_pct} onChange={num("ncp_min_pct")} /></Field>
            <Field label="Attendance requirement (%)"><input className="input" type="number" value={s.attendance_min_pct} onChange={num("attendance_min_pct")} /></Field>
            <Field label="Flag CP component below (%)"><input className="input" type="number" value={s.component_alert_pct} onChange={num("component_alert_pct")} /></Field>
          </div>
          <div className="divider" />
          <h3 style={{ marginBottom: 8 }}>Early-warning thresholds</h3>
          <div className="form-grid">
            <Field label="High risk at probability ≥" hint="0–1"><input className="input" type="number" step={0.05} value={s.risk_high} onChange={num("risk_high")} /></Field>
            <Field label="Medium risk at probability ≥" hint="0–1"><input className="input" type="number" step={0.05} value={s.risk_medium} onChange={num("risk_medium")} /></Field>
          </div>
        </Card>
        <Card title="Grade bands" subtitle="A student receives the first band whose minimum they reach">
          <table className="table compact">
            <thead><tr><th>Grade</th><th>Min %</th><th>Grade points</th><th /></tr></thead>
            <tbody>{s.grade_bands.map((b, i) => (
              <tr key={i}>
                <td><input className="input" style={{ width: 70 }} value={b.grade} onChange={(e) => setS({ ...s, grade_bands: s.grade_bands.map((x, j) => (j === i ? { ...x, grade: e.target.value } : x)) })} aria-label="Grade" /></td>
                <td><input className="input" style={{ width: 80 }} type="number" value={b.min} onChange={(e) => setS({ ...s, grade_bands: s.grade_bands.map((x, j) => (j === i ? { ...x, min: Number(e.target.value) } : x)) })} aria-label="Minimum percent" /></td>
                <td><input className="input" style={{ width: 80 }} type="number" value={b.points} onChange={(e) => setS({ ...s, grade_bands: s.grade_bands.map((x, j) => (j === i ? { ...x, points: Number(e.target.value) } : x)) })} aria-label="Grade points" /></td>
                <td className="r"><button className="btn btn-sm btn-ghost btn-danger" onClick={() => setS({ ...s, grade_bands: s.grade_bands.filter((_, j) => j !== i) })} aria-label="Remove band">✕</button></td>
              </tr>
            ))}</tbody>
          </table>
          <button className="btn btn-sm" style={{ marginTop: 8 }} onClick={() => setS({ ...s, grade_bands: [...s.grade_bands, { grade: "", min: 0, points: 0 }] })}>+ Band</button>
          <p className="small muted" style={{ marginTop: 8 }}>A student who fails the pass rules receives F regardless of band.</p>
        </Card>
      </div>
    </>
  );
}
