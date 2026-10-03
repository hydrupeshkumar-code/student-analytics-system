import { useState } from "react";
import { del, post, put } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dateStr, useFetch } from "../../lib/hooks";
import type { Rubric } from "../../lib/types";
import { Card, Empty, ErrorBox, Field, Modal, PageHead, Spinner, useConfirm, useToast } from "../../components/ui";

interface Draft {
  title: string; description: string;
  levels: { label: string; points: number }[];
  criteria: { name: string; description: string; weight: number; descriptors: string[] }[];
}

const TEMPLATE: Draft = {
  title: "", description: "",
  levels: [{ label: "Excellent", points: 4 }, { label: "Good", points: 3 }, { label: "Satisfactory", points: 2 }, { label: "Needs improvement", points: 1 }],
  criteria: [{ name: "", description: "", weight: 100, descriptors: ["", "", "", ""] }],
};

function toDraft(r: Rubric): Draft {
  return {
    title: r.title, description: r.description ?? "",
    levels: r.levels.map((l) => ({ label: l.label, points: l.points })),
    criteria: r.criteria.map((c) => ({ name: c.name, description: c.description ?? "", weight: c.weight, descriptors: r.levels.map((_, i) => c.descriptors?.[i] ?? "") })),
  };
}

function RubricEditor({ rubric, onClose, onSaved }: { rubric?: Rubric; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [d, setD] = useState<Draft>(rubric ? toDraft(rubric) : structuredClone(TEMPLATE));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const locked = !!rubric?.in_use;
  const totalW = d.criteria.reduce((a, c) => a + (Number(c.weight) || 0), 0);

  const setLevel = (i: number, p: Partial<Draft["levels"][0]>) => setD({ ...d, levels: d.levels.map((l, j) => (j === i ? { ...l, ...p } : l)) });
  const setCrit = (i: number, p: Partial<Draft["criteria"][0]>) => setD({ ...d, criteria: d.criteria.map((c, j) => (j === i ? { ...c, ...p } : c)) });
  const addLevel = () => setD({ ...d, levels: [...d.levels, { label: "", points: 0 }], criteria: d.criteria.map((c) => ({ ...c, descriptors: [...c.descriptors, ""] })) });
  const removeLevel = (i: number) => setD({ ...d, levels: d.levels.filter((_, j) => j !== i), criteria: d.criteria.map((c) => ({ ...c, descriptors: c.descriptors.filter((_, j) => j !== i) })) });

  async function save() {
    setBusy(true); setError(null);
    // server orders levels by points (high → low); keep descriptors aligned
    const order = d.levels.map((l, i) => ({ l, i })).sort((a, b) => b.l.points - a.l.points);
    const body = {
      title: d.title.trim(), description: d.description.trim() || null,
      levels: order.map(({ l }) => ({ label: l.label.trim(), points: Number(l.points) })),
      criteria: d.criteria.map((c) => ({ name: c.name.trim(), description: c.description.trim() || null, weight: Number(c.weight),
        descriptors: order.some(({ i }) => c.descriptors[i]?.trim()) ? order.map(({ i }) => c.descriptors[i]?.trim() ?? "") : null })),
    };
    try {
      if (rubric) await put(`/rubrics/${rubric.id}`, body); else await post("/rubrics", body);
      toast("Rubric saved"); onSaved();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Modal wide title={rubric ? `Edit rubric` : "New rubric"} onClose={onClose} footer={<>
      <span className="small muted" style={{ marginRight: "auto" }}>Score = max marks × Σ(weight × level points ÷ top points) ÷ Σ weight</span>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn btn-primary" disabled={busy || !d.title.trim() || d.criteria.some((c) => !c.name.trim()) || d.levels.some((l) => !l.label.trim())} onClick={save}>{busy ? "Saving…" : "Save rubric"}</button>
    </>}>
      {error && <div className="alert alert-bad" style={{ marginBottom: 12 }}>{error}</div>}
      {locked && <div className="alert alert-warn" style={{ marginBottom: 12 }}>This rubric has been used for scoring: you can rename labels and edit descriptors, but not change points, weights or structure. Duplicate it to make structural changes.</div>}
      <div className="form-grid" style={{ gridTemplateColumns: "1fr 2fr" }}>
        <Field label="Title"><input className="input" value={d.title} onChange={(e) => setD({ ...d, title: e.target.value })} placeholder="Lab report rubric" /></Field>
        <Field label="Description"><input className="input" value={d.description} onChange={(e) => setD({ ...d, description: e.target.value })} placeholder="When to use this rubric" /></Field>
      </div>

      <h3 style={{ margin: "18px 0 8px" }}>Performance levels</h3>
      <div className="row">
        {d.levels.map((l, i) => (
          <div key={i} className="row" style={{ background: "var(--surface-2)", padding: 6, borderRadius: 12, flexWrap: "nowrap" }}>
            <input className="input" style={{ width: 150 }} value={l.label} onChange={(e) => setLevel(i, { label: e.target.value })} placeholder="Label" aria-label={`Level ${i + 1} label`} />
            <input className="input" style={{ width: 64 }} type="number" min={0} disabled={locked} value={l.points} onChange={(e) => setLevel(i, { points: Number(e.target.value) })} aria-label={`Level ${i + 1} points`} />
            {!locked && d.levels.length > 2 && <button className="btn btn-ghost icon-btn btn-sm" onClick={() => removeLevel(i)} aria-label="Remove level">✕</button>}
          </div>
        ))}
        {!locked && <button className="btn btn-sm" onClick={addLevel}>+ Level</button>}
      </div>

      <div className="spread" style={{ margin: "18px 0 8px" }}>
        <h3>Criteria</h3>
        <span className="small text-2">Total weightage: <strong className="num">{totalW}</strong> {totalW !== 100 && <span className="muted">(weights are relative; 100 is conventional)</span>}</span>
      </div>
      <div className="stack" style={{ gap: 10 }}>
        {d.criteria.map((c, i) => (
          <div key={i} className="card card-pad" style={{ boxShadow: "none" }}>
            <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-end" }}>
              <Field label="Criterion"><input className="input" value={c.name} onChange={(e) => setCrit(i, { name: e.target.value })} placeholder="e.g. Correctness" /></Field>
              <Field label="What is assessed"><input className="input" value={c.description} onChange={(e) => setCrit(i, { description: e.target.value })} /></Field>
              <div style={{ width: 100 }}><Field label="Weight"><input className="input" type="number" min={1} disabled={locked} value={c.weight} onChange={(e) => setCrit(i, { weight: Number(e.target.value) })} /></Field></div>
              {!locked && d.criteria.length > 1 && <button className="btn btn-ghost btn-danger btn-sm" onClick={() => setD({ ...d, criteria: d.criteria.filter((_, j) => j !== i) })}>Remove</button>}
            </div>
            <div className="grid" style={{ gridTemplateColumns: `repeat(${d.levels.length}, minmax(0, 1fr))`, gap: 8, marginTop: 10 }}>
              {d.levels.map((l, li) => (
                <label key={li} className="field"><span className="small">{l.label || `Level ${li + 1}`} descriptor</span>
                  <textarea className="input" rows={2} value={c.descriptors[li] ?? ""} onChange={(e) => setCrit(i, { descriptors: c.descriptors.map((x, k) => (k === li ? e.target.value : x)) })} placeholder="Optional" />
                </label>
              ))}
            </div>
          </div>
        ))}
        {!locked && <div><button className="btn" onClick={() => setD({ ...d, criteria: [...d.criteria, { name: "", description: "", weight: 25, descriptors: d.levels.map(() => "") }] })}>+ Add criterion</button></div>}
      </div>
    </Modal>
  );
}

export default function Rubrics() {
  const { user } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const { data, error, loading, reload } = useFetch<Rubric[]>("/rubrics");
  const [editing, setEditing] = useState<Rubric | "new" | null>(null);
  const [view, setView] = useState<Rubric | null>(null);
  const mine = (r: Rubric) => user?.role === "admin" || r.owner_id === user?.id;

  async function duplicate(r: Rubric) {
    try { await post(`/rubrics/${r.id}/duplicate`); toast("Rubric duplicated — it is now in your library"); reload(); } catch (e) { toast((e as Error).message, "error"); }
  }
  async function remove(r: Rubric) {
    if (!(await confirm({ title: `Delete “${r.title}”?`, confirm: "Delete", danger: true }))) return;
    try { await del(`/rubrics/${r.id}`); toast("Rubric deleted"); reload(); } catch (e) { toast((e as Error).message, "error"); }
  }

  return (
    <>
      <PageHead title="Rubric library" subtitle="Shared institutional rubrics. Define criteria, performance levels and weightages once — CP scores are computed automatically."
        actions={<button className="btn btn-primary" onClick={() => setEditing("new")}>+ New rubric</button>} />
      {loading && !data ? <Spinner /> : error ? <ErrorBox error={error} onRetry={reload} /> : !data?.length ? (
        <Card><Empty title="No rubrics yet" action={<button className="btn btn-primary" onClick={() => setEditing("new")}>Create the first rubric</button>}>Rubrics make grading of assignments and practicals objective and consistent.</Empty></Card>
      ) : (
        <div className="grid grid-3">
          {data.map((r) => (
            <div key={r.id} className="card card-pad stack" style={{ gap: 10 }}>
              <div className="spread" style={{ alignItems: "flex-start" }}>
                <div><h3>{r.title}</h3><div className="small muted">{r.owner_name ?? "—"} · updated {dateStr(r.updated_at)}</div></div>
                {r.in_use && <span className="badge badge-info">In use</span>}
              </div>
              {r.description && <p className="small text-2">{r.description}</p>}
              <div className="small"><strong>{r.criteria.length}</strong> criteria · <strong>{r.levels.length}</strong> levels ({r.levels.map((l) => l.label).join(" / ")})</div>
              <div className="row" style={{ marginTop: "auto" }}>
                <button className="btn btn-sm" onClick={() => setView(r)}>View</button>
                {mine(r) && <button className="btn btn-sm" onClick={() => setEditing(r)}>Edit</button>}
                <button className="btn btn-sm btn-ghost" onClick={() => duplicate(r)}>Duplicate</button>
                {mine(r) && !r.in_use && <button className="btn btn-sm btn-ghost btn-danger" onClick={() => remove(r)}>Delete</button>}
              </div>
            </div>
          ))}
        </div>
      )}
      {editing && <RubricEditor rubric={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />}
      {view && (
        <Modal wide title={view.title} onClose={() => setView(null)}>
          <div className="table-wrap">
            <div className="rubric-grid" style={{ gridTemplateColumns: `minmax(160px,1.3fr) repeat(${view.levels.length}, minmax(110px,1fr))`, minWidth: 560 }}>
              <div className="rh">Criterion (weight)</div>
              {view.levels.map((l) => <div key={l.id} className="rh">{l.label} · {l.points}</div>)}
              {view.criteria.map((c) => (
                <div key={c.id} style={{ display: "contents" }}>
                  <div><strong>{c.name}</strong> <span className="muted">({c.weight})</span>{c.description && <div className="muted">{c.description}</div>}</div>
                  {view.levels.map((l, i) => <div key={l.id}>{c.descriptors?.[i] || <span className="muted">—</span>}</div>)}
                </div>
              ))}
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
