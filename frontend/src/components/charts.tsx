import {
  Bar, BarChart, CartesianGrid, Line, ComposedChart, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
  ZAxis, ReferenceLine,
} from "recharts";
import { Meter } from "./ui";

/* Palette roles (validated for CVD + contrast in light and dark): series-1 green, series-2 violet. Text never wears series colour. */
const S1 = "var(--series-1)";
const S2 = "var(--series-2)";
const AXIS = { stroke: "var(--axis)", tickLine: false, tick: { fill: "var(--muted)", fontSize: 11 } };

/** Category axis that tilts and truncates labels once there are too many to sit side by side. */
function catAxis(count: number) {
  if (count <= 4) return { height: 30 };
  return {
    height: 56,
    tick: ({ x, y, payload }: { x: number; y: number; payload: { value: string } }) => {
      const v = String(payload.value);
      return (
        <g transform={`translate(${x},${y + 6})`}>
          <title>{v}</title>
          <text textAnchor="end" transform="rotate(-32)" fill="var(--muted)" fontSize={11}>
            {v.length > 14 ? `${v.slice(0, 13)}…` : v}
          </text>
        </g>
      );
    },
  };
}

type TipProps ={ active?: boolean; payload?: { name?: string; value?: number; payload: Record<string, unknown> }[]; label?: string };

function Tip({ active, payload, label, unit = "", labelKey }: TipProps & { unit?: string; labelKey?: string }) {
  if (!active || !payload?.length) return null;
  const head = labelKey ? String(payload[0].payload[labelKey]) : label;
  return (
    <div className="chart-tip">
      <b>{head}</b>
      {payload.map((p, i) => <div key={i} className="num">{p.name}: {typeof p.value === "number" ? p.value.toFixed(1) : p.value}{unit}</div>)}
    </div>
  );
}

/** Single-series column chart (counts per band, averages per item). */
export function Columns({ data, x, y, name, unit = "", height = 220, refLine }: {
  data: Record<string, unknown>[]; x: string; y: string; name: string; unit?: string; height?: number; refLine?: { y: number; label: string };
}) {
  return (
    <div role="img" aria-label={`${name} by ${x}`}>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 10, right: 8, left: -14, bottom: 0 }} barCategoryGap="22%">
          <CartesianGrid vertical={false} />
          <XAxis dataKey={x} {...AXIS} interval={0} {...catAxis(data.length > 5 ? data.length : 0)} />
          <YAxis {...AXIS} axisLine={false} allowDecimals={false} />
          <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip unit={unit} />} />
          {refLine && <ReferenceLine y={refLine.y} stroke="var(--critical)" strokeDasharray="4 3" label={{ value: refLine.label, fill: "var(--muted)", fontSize: 11, position: "insideTopRight" }} />}
          <Bar dataKey={y} name={name} fill={S1} radius={[4, 4, 0, 0]} maxBarSize={44} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Two-series grouped columns, e.g. class average vs student. Legend always shown for 2 series. */
export function PairedColumns({ data, x, a, b, height = 240, unit = "%" }: {
  data: Record<string, unknown>[]; x: string; a: { key: string; name: string }; b: { key: string; name: string }; height?: number; unit?: string;
}) {
  return (
    <div>
      <div className="legend" style={{ marginBottom: 6 }}>
        <span><i style={{ background: S1 }} />{a.name}</span><span><i style={{ background: S2 }} />{b.name}</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 6, right: 8, left: -14, bottom: 0 }} barGap={2} barCategoryGap="24%">
          <CartesianGrid vertical={false} />
          <XAxis dataKey={x} {...AXIS} interval={0} {...catAxis(data.length)} />
          <YAxis {...AXIS} axisLine={false} domain={[0, 100]} />
          <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip unit={unit} />} />
          <Bar dataKey={a.key} name={a.name} fill={S1} radius={[4, 4, 0, 0]} maxBarSize={28} />
          <Bar dataKey={b.key} name={b.name} fill={S2} radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** CP vs NCP scatter with least-squares fit — the CP–NCP correlation view. */
export function CorrelationScatter({ points, fit }: {
  points: { name: string; cp: number; ncp: number }[]; fit: { slope: number; intercept: number } | null;
}) {
  const line = fit ? [0, 100].map((x) => ({ cp: x, fit: Math.max(0, Math.min(100, fit.intercept + fit.slope * x)) })) : [];
  return (
    <div role="img" aria-label="Scatter of CP score against NCP score">
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart margin={{ top: 10, right: 12, left: -6, bottom: 14 }}>
          <CartesianGrid />
          <XAxis type="number" dataKey="cp" domain={[0, 100]} {...AXIS} label={{ value: "CP score %", position: "insideBottom", offset: -6, fill: "var(--muted)", fontSize: 11 }} />
          <YAxis type="number" dataKey="ncp" domain={[0, 100]} {...AXIS} label={{ value: "NCP %", angle: -90, position: "insideLeft", offset: 18, fill: "var(--muted)", fontSize: 11 }} />
          <ZAxis range={[64, 64]} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} content={({ active, payload }) => {
            const p = payload?.find((x) => (x.payload as { name?: string }).name)?.payload as { name: string; cp: number; ncp: number } | undefined;
            if (!active || !p) return null;
            return <div className="chart-tip"><b>{p.name}</b><div className="num">CP {p.cp.toFixed(1)}% · NCP {p.ncp.toFixed(1)}%</div></div>;
          }} />
          {fit && <Line data={line} dataKey="fit" stroke="var(--muted)" strokeDasharray="5 4" strokeWidth={2} dot={false} activeDot={false} isAnimationActive={false} />}
          <Scatter data={points} fill={S1} stroke="var(--surface)" strokeWidth={2} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Horizontal labelled bars built from HTML — crisp, accessible, works for long labels. */
export function BarList({ rows, max = 100, unit = "%", threshold }: {
  rows: { label: string; value: number | null; sub?: string }[]; max?: number; unit?: string; threshold?: number;
}) {
  return (
    <div className="stack" style={{ gap: 10 }}>
      {rows.map((r) => (
        <div key={r.label} style={{ display: "grid", gridTemplateColumns: "minmax(90px, 160px) 1fr 56px", gap: 12, alignItems: "center" }}>
          <div className="small" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={r.label}>
            {r.label}{r.sub && <span className="muted"> · {r.sub}</span>}
          </div>
          <Meter value={r.value} max={max} color={threshold !== undefined && r.value !== null && r.value < threshold ? "var(--critical)" : undefined} />
          <div className="small num" style={{ textAlign: "right", fontWeight: 600 }}>
            {r.value === null ? "—" : `${r.value.toFixed(1)}${unit}`}
          </div>
        </div>
      ))}
    </div>
  );
}


