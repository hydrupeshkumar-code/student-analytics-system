import { useState } from "react";
import { Link } from "react-router-dom";
import { post } from "../../lib/api";
import { dateTimeStr, pct, useFetch } from "../../lib/hooks";
import type { Metrics, RiskLevel, RiskRow } from "../../lib/types";
import { Card, Empty, ErrorBox, RiskBadge, Spinner, Stat, useToast } from "../../components/ui";
import { useCourse } from "./CourseWorkspace";

interface RiskResp { model: { id: number; algorithm: string; metrics: Metrics; trained_at: string } | null; students: RiskRow[] }

export default function Risk() {
  const { course } = useCourse();
  const toast = useToast();
  const { data, error, loading, reload, setData } = useFetch<RiskResp>(`/courses/${course.id}/risk`);
  const [filter, setFilter] = useState<RiskLevel | "all">("all");
  const [category, setCategory] = useState<"overall" | "attendance" | "marks">("overall");
  const [busy, setBusy] = useState(false);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;

  async function recompute() {
    setBusy(true);
    try { setData(await post<RiskResp>(`/courses/${course.id}/risk/recompute`)); toast("Risk predictions updated"); }
    catch (e) { toast((e as Error).message, "error"); } finally { setBusy(false); }
  }
  const count = (l: RiskLevel) => data.students.filter((s) => s.risk_level === l).length;
  const signalLevel = (value: number | null | undefined, target: number, higherIsBetter = true): RiskLevel | null => {
    if (value == null || !Number.isFinite(value)) return null;
    const gap = higherIsBetter ? target - value : value - target;
    const index = gap > 0 ? Math.min(100, 35 + gap * (higherIsBetter ? 5 : 2)) : Math.max(5, 35 - Math.abs(gap) * 1.5);
    return index >= 70 ? "high" : index >= 40 ? "medium" : "low";
  };
  const internalAverage = (s: RiskRow) => {
    const vals = [s.features.quiz_pct, s.features.assignment_pct, s.features.practical_pct].filter((v): v is number => v !== null && v !== undefined);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  };
  const attendanceLevel = (s: RiskRow) => signalLevel(s.features.attendance_pct, 75);
  const marksLevel = (s: RiskRow) => signalLevel(internalAverage(s), 60);
  const selectedLevel = (s: RiskRow) => category === "attendance" ? attendanceLevel(s) : category === "marks" ? marksLevel(s) : s.risk_level;
  const rows = data.students.filter((s) => filter === "all" || selectedLevel(s) === filter);
  const m = data.model?.metrics;

  return (
    <div className="stack">
      <div className="grid grid-4">
        <Stat label="High risk" value={count("high")} sub="likely to fail without intervention" />
        <Stat label="Medium risk" value={count("medium")} sub="monitor closely" />
        <Stat label="Low risk" value={count("low")} />
        <Stat label="Model" value={data.model ? (data.model.algorithm === "logistic_regression" ? "Logistic reg." : "Decision tree") : "Rules"}
          sub={m ? `Hold-out accuracy ${(m.accuracy * 100).toFixed(0)}% · recall ${(m.recall * 100).toFixed(0)}% · AUC ${m.roc_auc.toFixed(2)}` : "No trained model — using transparent rules"} />
      </div>
      <Card>
        <div className="spread">
          <div className="small text-2" style={{ maxWidth: 720 }}>
            Predictions use continuous-process data (quiz, assignment, practical, attendance and overall CP), so they can be available before the semester-end exam. Treat them as decision support—not a grade—and review the displayed reasons before acting. Recompute after entering new marks.
            {data.students[0] && <> Last computed {dateTimeStr(data.students[0].generated_at)}.</>}
          </div>
          <div className="row">
            <label className="small">Risk category <select className="input" value={category} onChange={(e) => setCategory(e.target.value as typeof category)} style={{ marginLeft: 6 }}><option value="overall">Overall academic risk</option><option value="attendance">Attendance risk</option><option value="marks">Internal marks risk</option></select></label>
            <div className="segmented" role="group" aria-label="Filter by risk level">
              {(["all", "high", "medium", "low"] as const).map((l) => <button key={l} className={filter === l ? "active" : ""} onClick={() => setFilter(l)}>{l === "all" ? "All levels" : l[0].toUpperCase() + l.slice(1)}</button>)}
            </div>
            <Link className="btn" to="/interventions">Open intervention tracker</Link><button className="btn btn-primary" onClick={recompute} disabled={busy}>{busy ? "Computing…" : "Recompute"}</button>
          </div>
        </div>
      </Card>
      <Card pad={false}>
        {!data.students.length ? <Empty title="No predictions yet" action={<button className="btn btn-primary" onClick={recompute}>Compute now</button>}>Predictions need at least one scored assessment.</Empty> : (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Student</th><th>Overall risk</th><th>Attendance risk</th><th>Internal marks risk</th><th className="r">Probability of failing</th><th className="r">Quiz</th><th className="r">Assign.</th><th className="r">Practical</th><th className="r">Attend.</th><th className="r">CP</th><th>Explainable reasons</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.student_id}>
                <td><strong>{r.name}</strong><div className="small muted">{r.roll_no}</div></td>
                <td><RiskBadge level={r.risk_level} /></td>
                <td><RiskBadge level={attendanceLevel(r)} /><div className="small muted">{pct(r.features.attendance_pct, 0)}</div></td>
                <td><RiskBadge level={marksLevel(r)} /><div className="small muted">{pct(internalAverage(r), 0)} average</div></td>
                <td className="r num"><strong>{Math.round(r.probability * 100)}%</strong></td>
                <td className="r num small">{pct(r.features.quiz_pct, 0)}</td>
                <td className="r num small">{pct(r.features.assignment_pct, 0)}</td>
                <td className="r num small">{pct(r.features.practical_pct, 0)}</td>
                <td className="r num small" style={{ color: r.features.attendance_pct !== null && r.features.attendance_pct < 75 ? "var(--critical-text)" : undefined }}>{pct(r.features.attendance_pct, 0)}</td>
                <td className="r num small"><strong>{pct(r.features.cp_pct, 0)}</strong></td>
                <td className="small">{r.reasons.length ? r.reasons.join("; ") : <span className="muted">No specific reason was returned. Review the underlying marks and attendance with the student.</span>}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </div>
  );
}
