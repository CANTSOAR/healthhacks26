"use client";
import type { FeedState } from "@/lib/feed";
import { money, num, pct } from "@/lib/format";
import { SimTag } from "./atoms";

const n = (v: unknown): number => (typeof v === "number" && isFinite(v) ? v : NaN);

/** Hour index into `hourly` for tick t. Live streams append from the run's start; replays hold the whole episode. */
export const hourIndex = (f: FeedState, t: number) => Math.floor(t / 12) - f.hour0;

function trailing(arr: number[] | undefined, end: number, hours: number): number {
  if (!arr?.length) return NaN;
  const e = Math.min(arr.length, Math.max(0, end));
  const s = Math.max(0, e - hours);
  if (e <= s) return NaN;
  let sum = 0;
  for (let i = s; i < e; i++) sum += arr[i];
  return (sum / (e - s)) * hours; // scaled to a full window when fewer hours exist (run-rate)
}

export interface Kpi {
  key: string;
  label: string;
  value: string;
  unit?: string;
  sub: string;
  delta: number; // fractional change vs one simulated hour earlier; NaN if unknown
  goodWhenDown: boolean;
}

export function computeKpis(f: FeedState): Kpi[] {
  const snap = f.snap;
  const k = (snap?.kpis ?? {}) as Record<string, unknown>;
  const h = snap ? hourIndex(f, snap.t) + 1 : 0;
  const at = (key: string, i: number) => n(f.hourly[key]?.[Math.max(0, Math.min((f.hourly[key]?.length ?? 0) - 1, i))]);
  const rel = (now: number, then: number) => (isFinite(now) && isFinite(then) && then !== 0 ? (now - then) / Math.abs(then) : NaN);

  const wait = isFinite(n(k.wait_mean_min)) ? n(k.wait_mean_min) : at("wait_mean_min", h - 1);
  const waiting = isFinite(n(k.waiting_count)) ? n(k.waiting_count) : at("waiting_count", h - 1);
  const lwbs = isFinite(n(k.lwbs_rate)) ? n(k.lwbs_rate) : at("lwbs_rate", h - 1);
  const cost = trailing(f.hourly.cost_total, h, 24);
  const costPrev = trailing(f.hourly.cost_total, h - 1, 24);
  const margin = trailing(f.hourly.margin, h, 24);

  return [
    { key: "wait", label: "Door to provider", value: isFinite(wait) ? num(wait, 0) : "–", unit: "min", sub: isFinite(n(k.wait_p95_min)) ? `95th pct ${num(n(k.wait_p95_min))} min` : "mean wait", delta: rel(at("wait_mean_min", h - 1), at("wait_mean_min", h - 2)), goodWhenDown: true },
    { key: "waiting", label: "Patients waiting", value: isFinite(waiting) ? num(waiting) : "–", sub: isFinite(lwbs) ? `LWBS ${pct(lwbs, 1)}` : "not yet seen", delta: rel(at("waiting_count", h - 1), at("waiting_count", h - 2)), goodWhenDown: true },
    { key: "cost", label: "Cost per day", value: isFinite(cost) ? money(cost) : "–", sub: isFinite(margin) ? `margin ${money(margin)}` : "trailing 24 h", delta: rel(cost, costPrev), goodWhenDown: true },
  ];
}

export function DeltaChip({ delta, goodWhenDown, title = "Change against one simulated hour earlier" }: { delta: number; goodWhenDown: boolean; title?: string }) {
  if (!isFinite(delta)) return <span className="chip bg-[#141a33]/[0.05] text-ink-3">–</span>;
  const flat = Math.abs(delta) < 0.005;
  const good = flat ? null : delta < 0 === goodWhenDown;
  const bg = good == null ? "rgba(20,26,51,0.05)" : good ? "#DFF5EA" : "#FDE7E8";
  const fg = good == null ? "#8089A8" : good ? "#11734B" : "#B4232A";
  return (
    <span className="chip tnum" style={{ background: bg, color: fg }} title={title}>
      {flat ? "→" : delta > 0 ? "▲" : "▼"} {Math.abs(delta * 100).toFixed(Math.abs(delta) < 0.1 ? 1 : 0)}%
    </span>
  );
}

export function KpiCards({ f, compact = false }: { f: FeedState; compact?: boolean }) {
  const kpis = computeKpis(f);
  return (
    <div className={compact ? "flex gap-2 overflow-x-auto scroll-thin" : "grid grid-cols-3 gap-3"} data-testid="kpis">
      {kpis.map((k) => (
        <div key={k.key} className={`glass pointer-events-auto ${compact ? "min-w-[124px] flex-1 px-3 py-2" : "px-3.5 py-3"}`}>
          <div className="eyebrow truncate">{k.label}</div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className={`tnum font-semibold tracking-[-0.02em] text-ink ${compact ? "text-[20px] leading-6" : "text-[28px] leading-[32px]"}`}>{k.value}</span>
            {k.unit && <span className="text-[12px] font-medium text-ink-3">{k.unit}</span>}
          </div>
          <div className="tnum mt-0.5 truncate text-[11px] text-ink-3">{k.sub}</div>
          <div className="mt-2 flex items-center justify-between gap-1">
            <DeltaChip delta={k.delta} goodWhenDown={k.goodWhenDown} />
            {!compact && <SimTag>{f.origin === "fixture" ? "fixture" : "simulated"}</SimTag>}
          </div>
        </div>
      ))}
    </div>
  );
}
