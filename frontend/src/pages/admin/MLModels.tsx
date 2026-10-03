import { useState } from "react";
import { del, download, post, upload } from "../../lib/api";
import { dateTimeStr, useFetch } from "../../lib/hooks";
import type { ModelVersion } from "../../lib/types";
import { BarList } from "../../components/charts";
import { Card, Empty, ErrorBox, PageHead, Spinner, Stat, UploadButton, useConfirm, useToast } from "../../components/ui";

interface Status { active_model: ModelVersion | null; history: { total: number; by_source: Record<string, number>; fail_rate: number | null }; features: string[]; min_samples: number }
const LABEL: Record<string, string> = { quiz_pct: "Quiz %", assignment_pct: "Assignment %", practical_pct: "Practical %", attendance_pct: "Attendance %", cp_pct: "Overall CP %" };
const ALG: Record<string, string> = { logistic_regression: "Logistic regression", decision_tree: "Decision tree" };
const p = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function MLModels() {
  const toast = useToast();
  const confirm = useConfirm();
  const status = useFetch<Status>("/ml/status");
  const models = useFetch<ModelVersion[]>("/ml/models");
  const [alg, setAlg] = useState("auto");
  const [busy, setBusy] = useState(false);
  const refresh = () => { status.reload(); models.reload(); };

  async function train() {
    setBusy(true);
    try { const m = await post<ModelVersion>("/ml/train", { algorithm: alg }); toast(`Trained ${ALG[m.algorithm]} · F1 ${m.metrics.holdout.f1.toFixed(2)}`); refresh(); }
    catch (e) { toast((e as Error).message, "error"); } finally { setBusy(false); }
  }
  async function recomputeAll() {
    setBusy(true);
    try { const r = await post<{ predictions: number }>("/ml/recompute-all"); toast(`${r.predictions} predictions refreshed`); } catch (e) { toast((e as Error).message, "error"); } finally { setBusy(false); }
  }

  if (status.loading && !status.data) return <Spinner />;
  if (status.error) return <ErrorBox error={status.error} onRetry={refresh} />;
  const s = status.data!;
  const m = s.active_model;
  const h = m?.metrics.holdout;
  const cm = h?.confusion_matrix;

  return (
    <>
      <PageHead title="Early-warning model" subtitle="Baseline logistic-regression / decision-tree models trained on anonymised historical CP–NCP outcomes." actions={<>
        <button className="btn" onClick={recomputeAll} disabled={busy || !m}>Refresh all predictions</button>
      </>} />
      {s.history.by_source.synthetic && <div className="alert alert-warn" style={{ marginBottom: 16 }}>
        <span style={{ flex: 1 }}>The training set includes <strong>{s.history.by_source.synthetic}</strong> synthetic demo records. Import your institution's anonymised history (or harvest completed courses), then clear the synthetic data and retrain before relying on predictions.</span>
        <button className="btn btn-sm" onClick={async () => { if (await confirm({ title: "Remove synthetic records?", body: "Retrain afterwards so predictions use only real data.", confirm: "Remove", danger: true })) { await del("/ml/history?source=synthetic"); refresh(); } }}>Clear synthetic</button>
      </div>}
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <Stat label="Training records" value={s.history.total} sub={Object.entries(s.history.by_source).map(([k, v]) => `${v} ${k}`).join(" · ") || "none yet"} />
        <Stat label="Historical fail rate" value={s.history.fail_rate === null ? "—" : p(s.history.fail_rate)} />
        <Stat label="Active model" value={m ? ALG[m.algorithm] : "None"} sub={m ? `trained ${dateTimeStr(m.created_at)} on ${m.n_samples} records` : "Rules-based fallback in use"} />
        <Stat label="Hold-out F1 / AUC" value={h ? `${h.f1.toFixed(2)} / ${h.roc_auc.toFixed(2)}` : "—"} sub={h ? `${h.test_size} test records` : undefined} />
      </div>

      <div className="grid grid-2" style={{ alignItems: "start", marginBottom: 16 }}>
        <Card title="Training data" subtitle="Columns: cohort, course_code, quiz_pct, assignment_pct, practical_pct, attendance_pct, cp_pct, ncp_pct, passed">
          <div className="row">
            <button className="btn" onClick={() => download("/ml/history/template")}>↓ CSV template</button>
            <UploadButton label="Import history CSV" onFile={async (f) => {
              try { const r = await upload<{ imported: number }>("/ml/history/import", f); toast(`${r.imported} records imported`); refresh(); } catch (e) { toast((e as Error).message, "error"); }
            }} />
          </div>
          <p className="small muted" style={{ marginTop: 10 }}>Records contain no names or roll numbers. Completed courses can also be added with “Add to ML history” on a course’s Semester-end (NCP) tab once results are published.</p>
          <div className="divider" />
          <div className="row">
            <select className="input" style={{ width: 220 }} value={alg} onChange={(e) => setAlg(e.target.value)} aria-label="Algorithm">
              <option value="auto">Auto-select best (by F1)</option><option value="logistic_regression">Logistic regression</option><option value="decision_tree">Decision tree</option>
            </select>
            <button className="btn btn-primary" disabled={busy || s.history.total < s.min_samples} onClick={train}>{busy ? "Training…" : "Train model"}</button>
          </div>
          {s.history.total < s.min_samples && <p className="small muted" style={{ marginTop: 8 }}>At least {s.min_samples} records are required.</p>}
        </Card>

        {m && h && (
          <Card title="Documented model accuracy" subtitle={`${m.metrics.cv_folds}-fold cross-validation and a 25% hold-out set, at the flagging threshold p ≥ ${m.metrics.threshold ?? 0.5}`}>
            <div className="table-wrap"><table className="table compact">
              <thead><tr><th>Model</th><th className="r">Accuracy</th><th className="r">Precision</th><th className="r">Recall</th><th className="r">F1</th><th className="r">ROC AUC</th></tr></thead>
              <tbody>
                {Object.entries(m.metrics.cv).map(([k, v]) => (
                  <tr key={k}><td>{ALG[k]} (CV){k === m.metrics.selected && <span className="badge badge-info" style={{ marginLeft: 6 }}>selected</span>}</td>
                    <td className="r num">{p(v.accuracy)}</td><td className="r num">{p(v.precision)}</td><td className="r num">{p(v.recall)}</td><td className="r num">{v.f1.toFixed(3)}</td><td className="r num">{v.roc_auc.toFixed(3)}</td></tr>
                ))}
                <tr style={{ background: "var(--surface-2)" }}><td><strong>Hold-out</strong></td><td className="r num">{p(h.accuracy)}</td><td className="r num">{p(h.precision)}</td><td className="r num">{p(h.recall)}</td><td className="r num">{h.f1.toFixed(3)}</td><td className="r num">{h.roc_auc.toFixed(3)}</td></tr>
              </tbody>
            </table></div>
            {cm && <>
              <div className="small muted" style={{ margin: "12px 0 6px" }}>Hold-out confusion matrix</div>
              <table className="table compact" style={{ maxWidth: 360 }}>
                <thead><tr><th /><th className="r">Predicted pass</th><th className="r">Predicted fail</th></tr></thead>
                <tbody><tr><td>Actual pass</td><td className="r num">{cm[0][0]}</td><td className="r num">{cm[0][1]}</td></tr>
                  <tr><td>Actual fail</td><td className="r num">{cm[1][0]}</td><td className="r num"><strong>{cm[1][1]}</strong></td></tr></tbody>
              </table>
            </>}
          </Card>
        )}
      </div>

      {m && (
        <Card title={m.metrics.explain.type === "coefficients" ? "Feature influence (standardised coefficients)" : "Feature importance"}
          subtitle={m.metrics.explain.type === "coefficients" ? "Larger magnitude = stronger influence; negative means a higher value lowers the risk of failing" : "Share of the tree's splitting decisions"}>
          <BarList unit="" max={Math.max(...Object.values(m.metrics.explain.values).map(Math.abs), 0.01)}
            rows={Object.entries(m.metrics.explain.values).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).map(([k, v]) => ({ label: LABEL[k] ?? k, value: Math.abs(v), sub: v < 0 ? "protective" : m.metrics.explain.type === "coefficients" ? "raises risk" : undefined }))} />
        </Card>
      )}

      <div style={{ height: 16 }} />
      <Card title="Model versions" pad={false}>
        {!models.data?.length ? <Empty title="No models trained" /> : (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>#</th><th>Algorithm</th><th>Trained</th><th className="r">Records</th><th className="r">Hold-out F1</th><th className="r">AUC</th><th /></tr></thead>
            <tbody>{models.data.map((v) => (
              <tr key={v.id}><td className="num">{v.id}</td><td>{ALG[v.algorithm]}</td><td className="small">{dateTimeStr(v.created_at)}</td><td className="r num">{v.n_samples}</td>
                <td className="r num">{v.metrics.holdout.f1.toFixed(3)}</td><td className="r num">{v.metrics.holdout.roc_auc.toFixed(3)}</td>
                <td className="r">{v.is_active ? <span className="badge badge-good">Active</span> : <button className="btn btn-sm" onClick={async () => { await post(`/ml/models/${v.id}/activate`); toast("Model activated — refresh predictions to apply it"); refresh(); }}>Activate</button>}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  );
}
