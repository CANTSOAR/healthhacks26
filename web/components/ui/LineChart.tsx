"use client";
import { useMemo, useRef, useState } from "react";
import { metricValue, tickLabel } from "@/lib/format";

export interface Series {
  name: string;
  color: string;
  values: number[];
  dashed?: boolean;
}

/** Hourly line chart: one y-axis, quiet grid, crosshair + tooltip, optional scrub cursor and shaded "snapshots exist" bands. */
export function LineChart({
  series,
  unit,
  height = 110,
  cursor,
  onScrub,
  bands = [],
  marks = [],
  showLegend = false,
  hour0 = 0,
}: {
  series: Series[];
  unit?: string;
  height?: number;
  /** hour position of the playhead (may be fractional) */
  cursor?: number;
  onScrub?: (hour: number) => void;
  /** hour ranges to shade */
  bands?: { start: number; end: number }[];
  /** hours to mark with a small tick (decisions) */
  marks?: number[];
  showLegend?: boolean;
  /** hour-of-episode of the first value, for axis and tooltip labels */
  hour0?: number;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const [w, setW] = useState(480);
  const [hover, setHover] = useState<number | null>(null);
  const drag = useRef(false);
  const n = Math.max(1, ...series.map((s) => s.values.length));
  const padL = 38;
  const padR = 10;
  const padT = 8;
  const padB = 18;
  const iw = Math.max(10, w - padL - padR);
  const ih = height - padT - padB;

  const { max, ticks } = useMemo(() => {
    let m = 0;
    let lo = 0;
    for (const s of series) for (const v of s.values) if (isFinite(v)) { m = Math.max(m, v); lo = Math.min(lo, v); }
    if (m <= 0 && lo >= 0) m = 1;
    const span = m - lo;
    const step = niceStep(span / 2.2);
    const top = Math.ceil(m / step) * step;
    const bottom = Math.floor(lo / step) * step;
    const t: number[] = [];
    for (let v = bottom; v <= top + step * 0.01; v += step) t.push(v);
    return { max: top, min: bottom, ticks: t };
  }, [series]);
  const min = ticks[0] ?? 0;
  const x = (i: number) => padL + (n <= 1 ? 0 : (i / (n - 1)) * iw);
  const y = (v: number) => padT + ih - ((v - min) / (max - min || 1)) * ih;
  const path = (vals: number[]) => {
    let d = "";
    let pen = false;
    vals.forEach((v, i) => {
      if (!isFinite(v)) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  const hourAt = (clientX: number) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return 0;
    return Math.max(0, Math.min(n - 1, ((clientX - r.left - padL) / iw) * (n - 1)));
  };
  const dayTicks = useMemo(() => {
    const out: number[] = [];
    // widen the spacing until labels are at least ~76 px apart
    const steps = [6, 12, 24, 48, 24 * 7, 24 * 14, 24 * 28, 24 * 56, 24 * 112];
    const every = steps.find((s) => (s / Math.max(1, n - 1)) * iw >= 76) ?? steps[steps.length - 1];
    for (let h = 0; h < n; h += every) out.push(h);
    return out;
  }, [n, iw]);
  const hi = hover != null ? Math.round(hover) : null;

  return (
    <div className="relative select-none" style={{ height }}>
      <svg
        ref={(el) => {
          ref.current = el;
          if (el) {
            const cw = el.clientWidth;
            if (cw && Math.abs(cw - w) > 1) setW(cw);
          }
        }}
        width="100%"
        height={height}
        role="img"
        aria-label={`${series.map((s) => s.name).join(" and ")}, hourly`}
        style={{ cursor: onScrub ? "ew-resize" : "crosshair", touchAction: "none" }}
        onPointerDown={(e) => {
          drag.current = true;
          (e.target as Element).setPointerCapture?.(e.pointerId);
          onScrub?.(hourAt(e.clientX));
        }}
        onPointerMove={(e) => {
          const h = hourAt(e.clientX);
          setHover(h);
          if (drag.current) onScrub?.(h);
        }}
        onPointerUp={() => (drag.current = false)}
        onPointerLeave={() => {
          setHover(null);
          drag.current = false;
        }}
      >
        {bands.map((b, i) => (
          <rect key={i} x={x(Math.max(0, b.start))} y={padT} width={Math.max(2, x(Math.min(n - 1, b.end)) - x(Math.max(0, b.start)))} height={ih} fill="#2F55F5" opacity={0.07} rx={3} />
        ))}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={padL + iw} y1={y(t)} y2={y(t)} stroke="rgba(20,26,51,0.07)" strokeWidth={1} />
            <text x={padL - 6} y={y(t) + 3.5} textAnchor="end" fontSize={9.5} fill="#8089A8" className="tnum">
              {axisLabel(t, unit)}
            </text>
          </g>
        ))}
        {dayTicks.map((h) => (
          <text key={h} x={x(h)} y={height - 4} fontSize={9.5} fill="#8089A8" textAnchor={h === 0 ? "start" : "middle"} className="tnum">
            {n <= 96 ? tickLabel((h + hour0) * 12) : `Day ${Math.floor((h + hour0) / 24) + 1}`}
          </text>
        ))}
        {marks.map((h, i) => (
          <path key={i} d={`M${x(h)} ${padT + ih}v-5`} stroke="#141A33" strokeWidth={1.5} strokeLinecap="round" opacity={0.55} />
        ))}
        {series.map((s) => (
          <path key={s.name} d={path(s.values)} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" strokeDasharray={s.dashed ? "4 3" : undefined} />
        ))}
        {cursor != null && isFinite(cursor) && cursor >= 0 && cursor <= n - 1 + 1.01 && (
          <g>
            <line x1={x(Math.min(cursor, n - 1))} x2={x(Math.min(cursor, n - 1))} y1={padT - 4} y2={padT + ih} stroke="#141A33" strokeWidth={1.5} />
            <circle cx={x(Math.min(cursor, n - 1))} cy={padT - 4} r={3.5} fill="#141A33" />
          </g>
        )}
        {hi != null && (
          <g pointerEvents="none">
            <line x1={x(hi)} x2={x(hi)} y1={padT} y2={padT + ih} stroke="rgba(20,26,51,0.25)" strokeWidth={1} strokeDasharray="2 3" />
            {series.map((s) => (isFinite(s.values[hi]) ? <circle key={s.name} cx={x(hi)} cy={y(s.values[hi])} r={4} fill={s.color} stroke="#fff" strokeWidth={2} /> : null))}
          </g>
        )}
      </svg>
      {hi != null && (
        <div
          className="pointer-events-none absolute z-10 rounded-lg border border-line bg-white/95 px-2 py-1.5 text-[11px] shadow-card"
          style={{ left: Math.min(Math.max(x(hi) + 10, 4), w - 150), top: 2, minWidth: 110 }}
        >
          <div className="tnum mb-0.5 font-medium text-ink-3">{`Day ${Math.floor((hi + hour0) / 24) + 1} · ${tickLabel((hi + hour0) * 12)}`}</div>
          {series.map((s) => (
            <div key={s.name} className="flex items-center gap-1.5">
              <span className="h-[3px] w-3 rounded-full" style={{ background: s.color }} />
              {series.length > 1 && <span className="max-w-[110px] truncate text-ink-2">{s.name}</span>}
              <span className="tnum ml-auto font-semibold text-ink">{metricValue(s.values[hi], unit)}</span>
            </div>
          ))}
        </div>
      )}
      {showLegend && series.length > 1 && (
        <div className="absolute right-1 top-0 flex gap-3 text-[10.5px] font-medium text-ink-2">
          {series.map((s) => (
            <span key={s.name} className="flex items-center gap-1">
              <span className="h-[3px] w-3 rounded-full" style={{ background: s.color }} />
              {s.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function niceStep(raw: number): number {
  if (!isFinite(raw) || raw <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const f = raw / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
}
function axisLabel(v: number, unit?: string): string {
  if (unit === "usd") return Math.abs(v) >= 1000 ? `$${+(v / 1000).toFixed(1)}k` : `$${v}`;
  if (unit === "fraction" || unit === "index_0_1") return `${+(v * 100).toFixed(1)}%`;
  return Math.abs(v) >= 10000 ? `${+(v / 1000).toFixed(1)}k` : String(+v.toFixed(2));
}
