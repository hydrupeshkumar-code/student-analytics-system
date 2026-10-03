import { useState } from "react";
import { del, patch, post } from "../../lib/api";
import { useFetch } from "../../lib/hooks";
import type { Outcome, Program } from "../../lib/types";
import { Card, Empty, ErrorBox, Field, Modal, PageHead, Spinner, useConfirm, useToast } from "../../components/ui";

const NBA_POS = [
  "Engineering knowledge", "Problem analysis", "Design/development of solutions", "Conduct investigations of complex problems",
  "Modern tool usage", "The engineer and society", "Environment and sustainability", "Ethics", "Individual and team work",
  "Communication", "Project management and finance", "Life-long learning",
];

export default function Programs() {
  const toast = useToast();
  const confirm = useConfirm();
  const { data, error, loading, reload } = useFetch<Program[]>("/programs");
  const [form, setForm] = useState<Program | "new" | null>(null);
  const [f, setF] = useState({ code: "", name: "", department: "" });
  const [po, setPo] = useState<{ program: Program; outcome?: Outcome } | null>(null);
  const [pf, setPf] = useState({ code: "", description: "" });

  function openForm(p: Program | "new") { setForm(p); setF(p === "new" ? { code: "", name: "", department: "" } : { code: p.code, name: p.name, department: p.department ?? "" }); }
  async function saveProgram() {
    try { if (form === "new") await post("/programs", f); else if (form) await patch(`/programs/${form.id}`, f); setForm(null); reload(); toast("Program saved"); }
    catch (e) { toast((e as Error).message, "error"); }
  }
  async function removeProgram(p: Program) {
    if (!(await confirm({ title: `Delete ${p.code}?`, body: "Its program outcomes and CO–PO mappings will be deleted.", confirm: "Delete", danger: true }))) return;
    try { await del(`/programs/${p.id}`); reload(); } catch (e) { toast((e as Error).message, "error"); }
  }
  function openPo(program: Program, outcome?: Outcome) { setPo({ program, outcome }); setPf(outcome ? { code: outcome.code, description: outcome.description } : { code: `PO${program.outcomes.length + 1}`, description: "" }); }
  async function savePo() {
    if (!po) return;
    try {
      if (po.outcome) await patch(`/programs/${po.program.id}/outcomes/${po.outcome.id}`, pf); else await post(`/programs/${po.program.id}/outcomes`, pf);
      setPo(null); reload();
    } catch (e) { toast((e as Error).message, "error"); }
  }
  async function addNbaPos(p: Program) {
    const existing = new Set(p.outcomes.map((o) => o.code));
    let n = 0;
    for (const [i, d] of NBA_POS.entries()) {
      if (existing.has(`PO${i + 1}`)) continue;
      try { await post(`/programs/${p.id}/outcomes`, { code: `PO${i + 1}`, description: d }); n++; } catch { /* skip */ }
    }
    toast(`${n} NBA graduate attributes added`); reload();
  }

  return (
    <>
      <PageHead title="Programs & program outcomes" subtitle="Program Outcomes (POs) are the targets that course outcomes map to for accreditation."
        actions={<button className="btn btn-primary" onClick={() => openForm("new")}>+ New program</button>} />
      {loading && !data ? <Spinner /> : error ? <ErrorBox error={error} onRetry={reload} /> : !data?.length ? <Card><Empty title="No programs yet" /></Card> : (
        <div className="stack">{data.map((p) => (
          <Card key={p.id} title={<>{p.code} · {p.name}</>} subtitle={p.department ?? undefined} actions={<>
            {p.outcomes.length < 12 && <button className="btn btn-sm" onClick={() => addNbaPos(p)}>Add NBA PO1–PO12</button>}
            <button className="btn btn-sm" onClick={() => openPo(p)}>+ Outcome</button>
            <button className="btn btn-sm btn-ghost" onClick={() => openForm(p)}>Edit</button>
            <button className="btn btn-sm btn-ghost btn-danger" onClick={() => removeProgram(p)}>Delete</button>
          </>} pad={false}>
            {!p.outcomes.length ? <Empty title="No program outcomes" /> : (
              <div className="table-wrap"><table className="table">
                <tbody>{p.outcomes.map((o) => (
                  <tr key={o.id}><td style={{ width: 70 }}><span className="badge badge-info">{o.code}</span></td><td>{o.description}</td>
                    <td className="r nowrap"><button className="btn btn-sm btn-ghost" onClick={() => openPo(p, o)}>Edit</button>
                      <button className="btn btn-sm btn-ghost btn-danger" onClick={async () => { if (await confirm({ title: `Delete ${o.code}?`, confirm: "Delete", danger: true })) { await del(`/programs/${p.id}/outcomes/${o.id}`); reload(); } }}>Delete</button></td></tr>
                ))}</tbody>
              </table></div>
            )}
          </Card>
        ))}</div>
      )}
      {form && <Modal title={form === "new" ? "New program" : `Edit ${form.code}`} onClose={() => setForm(null)} footer={<><button className="btn" onClick={() => setForm(null)}>Cancel</button><button className="btn btn-primary" disabled={!f.code || !f.name} onClick={saveProgram}>Save</button></>}>
        <div className="stack" style={{ gap: 12 }}>
          <Field label="Code"><input className="input" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="BTECH-CSE" /></Field>
          <Field label="Name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <Field label="Department"><input className="input" value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} /></Field>
        </div>
      </Modal>}
      {po && <Modal title={po.outcome ? `Edit ${po.outcome.code}` : `New outcome for ${po.program.code}`} onClose={() => setPo(null)} footer={<><button className="btn" onClick={() => setPo(null)}>Cancel</button><button className="btn btn-primary" disabled={!pf.code || !pf.description} onClick={savePo}>Save</button></>}>
        <div className="stack" style={{ gap: 12 }}>
          <Field label="Code"><input className="input" value={pf.code} onChange={(e) => setPf({ ...pf, code: e.target.value })} /></Field>
          <Field label="Statement"><textarea className="input" rows={3} value={pf.description} onChange={(e) => setPf({ ...pf, description: e.target.value })} /></Field>
        </div>
      </Modal>}
    </>
  );
}
