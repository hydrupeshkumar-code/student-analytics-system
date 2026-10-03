import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { AStatus, RiskLevel } from "../lib/types";

/* ---------------- toasts */
interface Toast { id: number; text: string; kind: "ok" | "error" }
const ToastCtx = createContext<(text: string, kind?: "ok" | "error") => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, kind: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((t) => [...t, { id, text, kind }]);
    setTimeout(() => setItems((t) => t.filter((x) => x.id !== id)), kind === "error" ? 6000 : 3000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`toast ${t.kind === "error" ? "error" : ""}`}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------------- primitives */
export function Spinner({ label = "Loading" }: { label?: string }) {
  return <div className="center"><div className="spinner" role="status" aria-label={label} /></div>;
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="alert alert-bad">
      <span style={{ flex: 1 }}>{error}</span>
      {onRetry && <button className="btn btn-sm" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  );
}

export function Card({ title, subtitle, actions, children, pad = true }: {
  title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode; pad?: boolean;
}) {
  return (
    <section className="card">
      {(title || actions) && (
        <div className="card-head">
          <div>{title && <h3>{title}</h3>}{subtitle && <p>{subtitle}</p>}</div>
          {actions && <div className="row">{actions}</div>}
        </div>
      )}
      <div className={pad ? "card-body" : ""}>{children}</div>
    </section>
  );
}

export type Tone = "green" | "coral" | "blue" | "amber" | "violet";

export function Stat({ label, value, unit, sub, accent, icon, tone = "green" }: {
  label: string; value: ReactNode; unit?: string; sub?: ReactNode; accent?: boolean; icon?: ReactNode; tone?: Tone;
}) {
  return (
    <div className={`card stat tone-${tone} ${accent ? "accent" : ""}`}>
      {icon && <div className="stat-icon" aria-hidden>{icon}</div>}
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}{unit && <small>{unit}</small>}
      </div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function PageHead({ title, subtitle, crumbs, actions }: { title: ReactNode; subtitle?: ReactNode; crumbs?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        {crumbs && <div className="crumbs">{crumbs}</div>}
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}

/** Green welcome banner with illustration, as on the dashboard landing pages. */
export function Hero({ title, subtitle, actions, art }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; art?: ReactNode }) {
  return (
    <section className="hero">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
        {actions && <div className="row">{actions}</div>}
      </div>
      {art}
    </section>
  );
}

export function Meter({ value, max = 100, color }: { value: number | null; max?: number; color?: string }) {
  const w = value === null ? 0 : Math.max(0, Math.min(100, (100 * value) / max));
  return <div className="meter" aria-hidden><i style={{ width: `${w}%`, background: color }} /></div>;
}

/* ---------------- status badges: colour is always paired with a text label */
const STATUS: Record<AStatus, [string, string]> = {
  draft: ["Draft", ""],
  in_progress: ["Marking open", "badge-info"],
  completed: ["Completed", "badge-good"],
  finalized: ["Finalized", "badge-good"],
};
export function StatusBadge({ status }: { status: AStatus }) {
  const [label, cls] = STATUS[status];
  if (status === "finalized") return <span className="stamp stamp-ink">Finalized</span>;
  return <span className={`badge ${cls}`}>{label}</span>;
}

const RISK: Record<RiskLevel, [string, string]> = { high: ["High risk", "badge-bad"], medium: ["Medium risk", "badge-warn"], low: ["Low risk", "badge-good"] };
export function RiskBadge({ level }: { level: RiskLevel | null | undefined }) {
  if (!level) return <span className="badge">Not assessed</span>;
  const [label, cls] = RISK[level];
  return <span className={`badge ${cls}`}><span className="dot" />{label}</span>;
}

export function ResultBadge({ passed }: { passed: boolean | null }) {
  if (passed === null) return <span className="muted">—</span>;
  return passed ? <span className="stamp stamp-good">Pass</span> : <span className="stamp stamp-bad">Fail</span>;
}

/* ---------------- modal & confirm */
export function Modal({ title, onClose, children, footer, wide }: {
  title: ReactNode; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    ref.current?.querySelector<HTMLElement>("input, select, textarea, button.btn-primary")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true" ref={ref}>
        <div className="modal-head"><h2>{title}</h2><button className="btn btn-ghost icon-btn" onClick={onClose} aria-label="Close">✕</button></div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

type ConfirmOpts = { title: string; body?: ReactNode; confirm?: string; danger?: boolean };
const ConfirmCtx = createContext<(o: ConfirmOpts) => Promise<boolean>>(async () => false);
export const useConfirm = () => useContext(ConfirmCtx);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<(ConfirmOpts & { resolve: (v: boolean) => void }) | null>(null);
  const ask = useCallback((o: ConfirmOpts) => new Promise<boolean>((resolve) => setState({ ...o, resolve })), []);
  const close = (v: boolean) => { state?.resolve(v); setState(null); };
  return (
    <ConfirmCtx.Provider value={ask}>
      {children}
      {state && (
        <Modal title={state.title} onClose={() => close(false)} footer={<>
          <button className="btn" onClick={() => close(false)}>Cancel</button>
          <button className={`btn ${state.danger ? "btn-danger" : "btn-primary"}`} onClick={() => close(true)}>{state.confirm ?? "Confirm"}</button>
        </>}>
          <div className="text-2">{state.body}</div>
        </Modal>
      )}
    </ConfirmCtx.Provider>
  );
}

/* ---------------- file picker button */
export function UploadButton({ label, accept = ".csv", onFile, disabled }: { label: string; accept?: string; onFile: (f: File) => void; disabled?: boolean }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <button className="btn" disabled={disabled} onClick={() => ref.current?.click()}>↑ {label}</button>
      <input ref={ref} type="file" accept={accept} hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
    </>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small className="hint">{hint}</small>}</label>;
}

/** Shows a one-time secret (temporary password) with a copy button. */
export function SecretBox({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="row" style={{ background: "var(--surface-2)", padding: "8px 10px", borderRadius: 6 }}>
      <code style={{ flex: 1, fontSize: 15 }}>{value}</code>
      <button className="btn btn-sm" onClick={() => { navigator.clipboard?.writeText(value); setCopied(true); }}>{copied ? "Copied" : "Copy"}</button>
    </div>
  );
}
