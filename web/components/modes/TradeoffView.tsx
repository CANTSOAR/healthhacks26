"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { metricValue, money, num, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { KIND, kindInfo } from "@/lib/palette";
import { managerStory, objectiveWords, prettyManager, shortManager } from "@/lib/story";
import { feeds } from "@/lib/session";
import { useUI } from "@/lib/ui";
import type { ManagerKind, RolloutListItem, Validation } from "@/lib/types";
import HospitalScene from "../scene/HospitalScene";
import { KindChip, Marker, SimTag, SourceChip } from "../ui/atoms";
import { Disclaimer } from "../ui/Chrome";

interface Pt {
  id: string;
  label: string;
  /** the server's full label, for hover */
  full?: string;
  kind: ManagerKind;
  objective?: string;
  x: number;
  y: number;
  ex: number;
  ey: number;
  n?: number;
  metrics: Record<string, { mean: number; ci95?: number; std?: number }>;
  human?: boolean;
  /** human run shorter than the evaluation protocol: drawn, but flagged */
  caveat?: string;
}

const TABLE: [string, string, string][] = [
  ["cost_per_day", "Cost / day", "usd"],
  ["wait_mean_min", "Mean wait", "minutes"],
  ["wait_p95_min", "95th pct wait", "minutes"],
  ["lwbs_rate", "LWBS", "fraction"],
  ["margin_per_day", "Margin / day", "usd"],
];

const vFmt = (v: number | null | undefined, unit?: string) => (v == null ? "–" : unit === "fraction" ? `${(v * 100).toFixed(1)}%` : unit === "minutes" ? `${Math.round(v)} min` : Math.round(v).toLocaleString("en-US"));

/** Baseline simulator output against published benchmarks, as the server computed it. Shown as it is, inside or outside. */
function ValidationCard({ v }: { v: Validation | null }) {
  const [all, setAll] = useState(false);
  if (!v || v.status === "offline" || v.status === "no_targets") return null;
  const compared = v.targets.filter((t) => v.simulated[t.name] != null);
  const own = compared.filter((t) => !t.name.includes("."));
  const peers = compared.filter((t) => t.name.includes("."));
  const rows = all ? [...own, ...peers] : own.length ? own : peers.slice(0, 3);
  const inside = compared.filter((t) => v.within[t.name] === true).length;
  const judged = compared.filter((t) => v.within[t.name] != null).length;
  return (
    <div className="mb-3 rounded-xl bg-[#141a33]/[0.035] p-3" data-testid="validation">
      <div className="flex flex-wrap items-center gap-2">
        <span className="eyebrow">Validation against public benchmarks</span>
        {v.status === "pending" && <span className="chip bg-[#FDEFD8] text-[#8A5A00]">{v.stale ? "recomputing · showing previous" : "computing"}</span>}
        {v.status === "error" && <span className="chip bg-[#FDE7E8] text-[#B4232A]">error</span>}
      </div>
      {compared.length === 0 ? (
        <div className="mt-1 text-[11px] text-ink-3">{v.status === "pending" ? "The baseline run is still being computed." : "No comparable outputs yet."}</div>
      ) : (
        <>
          <div className="mt-1 text-[11px] leading-snug text-ink-3">
            Baseline: {v.baseline?.policy ?? "default settings"}, {v.baseline?.scenario?.replace(/_/g, " ") ?? "normal week"}
            {v.baseline?.days ? `, ${v.baseline.days} days` : ""}
            {v.baseline?.seeds?.length ? `, ${v.baseline.seeds.length} seeds` : ""}. {inside} of {judged} comparisons fall inside the published range.
          </div>
          <div className="mt-2 space-y-1.5">
            {rows.map((t) => {
              const ok = v.within[t.name];
              return (
                <div key={t.name} className="rounded-lg bg-white/70 px-2.5 py-1.5">
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[11.5px] font-semibold text-ink">{titleCase((t.attribute ?? t.name).replace(/_min$/, ""))}</div>
                      <div className="truncate text-[10.5px] text-ink-3">{t.variant_label ?? t.name}</div>
                    </div>
                    {ok == null ? <span className="chip bg-[#141a33]/[0.05] text-ink-3">no range</span> : <span className="chip" style={{ background: ok ? "#DFF5EA" : "#FDE7E8", color: ok ? "#11734B" : "#B4232A" }}>{ok ? "inside" : "outside"}</span>}
                  </div>
                  <div className="tnum mt-0.5 flex flex-wrap items-baseline gap-x-3 text-[11px] text-ink-2">
                    <span>
                      simulated <b className="font-semibold text-ink">{vFmt(v.simulated[t.name], t.unit)}</b>
                    </span>
                    <span>
                      published {vFmt(t.value, t.unit)}
                      {t.range ? ` (range ${vFmt(t.range[0], t.unit)} to ${vFmt(t.range[1], t.unit)})` : ""}
                    </span>
                    {t.url && /^https?:/.test(t.url) && (
                      <a href={t.url} target="_blank" rel="noreferrer" className="font-medium text-accent-dark hover:underline" title={t.citation}>
                        source
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {own.length + peers.length > rows.length || all ? (
            <button className="mt-2 text-[11px] font-semibold text-accent-dark hover:underline" onClick={() => setAll((x) => !x)}>
              {all ? "Show fewer" : `Show all ${compared.length} comparisons`}
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}

function nice(min: number, max: number, count: number): number[] {
  const span = max - min || 1;
  const raw = span / count;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const f = raw / p;
  const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
  const out: number[] = [];
  // run to the first tick at or past max, so no point can sit beyond the last gridline
  for (let v = Math.floor(min / step) * step; v < max + step * 0.999; v += step) out.push(+v.toFixed(6));
  return out;
}

function Scatter({ pts, selected, onSelect, xLabel }: { pts: Pt[]; selected: string | null; onSelect: (id: string | null) => void; xLabel: string }) {
  const [size, setSize] = useState({ w: 720, h: 460 });
  const [hover, setHover] = useState<string | null>(null);
  const box = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);
  const pad = { l: 46, r: 24, t: 34, b: 46 };
  const iw = Math.max(50, size.w - pad.l - pad.r);
  const ih = Math.max(50, size.h - pad.t - pad.b);
  const { xt, yt } = useMemo(() => {
    const xs = pts.flatMap((p) => [p.x - p.ex, p.x + p.ex]);
    const ys = pts.flatMap((p) => [p.y - p.ey, p.y + p.ey]);
    let x0 = Math.min(...xs);
    let x1 = Math.max(...xs);
    const y1 = Math.max(...ys, 1);
    if (x1 - x0 < Math.abs(x1) * 0.02) {
      // a single point (or identical costs): give it room
      x0 -= Math.abs(x0) * 0.2 || 1;
      x1 += Math.abs(x1) * 0.2 || 1;
    }
    return { xt: nice(x0 - (x1 - x0) * 0.06, x1 + (x1 - x0) * 0.06, 6), yt: nice(0, y1 * 1.06, 5) };
  }, [pts]);
  const xmin = xt[0];
  const xmax = xt[xt.length - 1];
  const ymin = yt[0];
  const ymax = yt[yt.length - 1];
  const X = (v: number) => pad.l + ((v - xmin) / (xmax - xmin || 1)) * iw;
  const Y = (v: number) => pad.t + ih - ((v - ymin) / (ymax - ymin || 1)) * ih;

  // Managers that land on the same spot (a cloned agent on its heuristic) form one cluster: one label, a count badge,
  // a tooltip that lists them all, and clicks that step through them. Nothing is hidden under another mark unsaid.
  const clusters = useMemo(() => {
    const out: { members: number[]; cx: number; cy: number }[] = [];
    pts.forEach((p, i) => {
      const x = X(p.x);
      const y = Y(p.y);
      const c = out.find((q) => Math.hypot(q.cx - x, q.cy - y) < 11);
      if (c) c.members.push(i);
      else out.push({ members: [i], cx: x, cy: y });
    });
    // the tuned heuristic leads its cluster (it is the reference the others are compared with), then baselines
    const rank = (k: string) => (k === "tuned_heuristic" ? 0 : k === "learned" ? 2 : 1);
    out.forEach((c) => c.members.sort((i, j) => rank(pts[i].kind) - rank(pts[j].kind)));
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pts, size.w, size.h, xmin, xmax, ymin, ymax]);
  const clusterOf = (i: number) => clusters.find((c) => c.members.includes(i))!;

  // one direct label per cluster: close to the mark if there is room, otherwise further out on a leader line
  const labels = useMemo(() => {
    // obstacles: every marker, and both error bars of every point
    const placed: { x0: number; y0: number; x1: number; y1: number }[] = pts.flatMap((p) => [
      { x0: X(p.x) - 8, y0: Y(p.y) - 8, x1: X(p.x) + 8, y1: Y(p.y) + 8 },
      { x0: X(p.x - p.ex), y0: Y(p.y) - 2, x1: X(p.x + p.ex), y1: Y(p.y) + 2 },
      { x0: X(p.x) - 2, y0: Y(p.y + p.ey), x1: X(p.x) + 2, y1: Y(p.y - p.ey) },
    ]);
    const labelBoxes: typeof placed = [];
    // the count badge of a shared spot is an obstacle too
    clusters.forEach((c) => c.members.length > 1 && placed.push({ x0: c.cx + 1, y0: c.cy - 17, x1: c.cx + 17, y1: c.cy - 1 }));
    const hit = (b: { x0: number; y0: number; x1: number; y1: number }) => placed.some((q) => !(b.x1 < q.x0 || b.x0 > q.x1 || b.y1 < q.y0 || b.y0 > q.y1));
    const out: { x: number; y: number; a: "start" | "end"; leader: null | { x: number; y0: number; y1: number }; text: string; show: boolean }[] = [];
    // Labels all run the same way from their marks (towards the emptier side of the chart) and are placed starting
    // from that side, so the vertical leader of a mark placed later can never run through an earlier label: a crowded
    // row of marks becomes a staircase of labels.
    const mid = pad.l + iw / 2;
    const left = clusters.filter((c) => c.cx > mid).length >= clusters.length / 2; // most marks on the right: labels run leftwards
    const order = clusters.map((_, i) => i).sort((i, j) => (left ? clusters[i].cx - clusters[j].cx : clusters[j].cx - clusters[i].cx));
    for (const ci of order) {
      const c = clusters[ci];
      const inCluster = c.members.find((i) => pts[i].id === selected);
      const lead = pts[inCluster ?? c.members[0]];
      const text = lead.label.replace(/\s*\[fixture\]$/, "") + (c.members.length > 1 ? `  +${c.members.length - 1} here` : "");
      const tw = text.length * 6.1 + 6;
      const { cx, cy } = c;
      const badge = c.members.length > 1 ? 10 : 0;
      type Cand = { x: number; y: number; a: "start" | "end"; leader: null | { x: number; y0: number; y1: number }; away?: boolean };
      const A = left ? "end" : "start";
      const sgn = left ? -1 : 1;
      const cands: Cand[] = [
        // beside the mark, on the diagonals (the error bars run straight through the point, so corners stay clear)
        { x: cx + sgn * (10 + (left ? 0 : badge)), y: cy - 8, a: A, leader: null },
        { x: cx + sgn * 10, y: cy + 18, a: A, leader: null },
        // on the other side only where no other mark sits under the label
        { x: cx - sgn * (10 + (left ? badge : 0)), y: cy - 8, a: left ? "start" : "end", leader: null, away: true },
        { x: cx - sgn * 10, y: cy + 18, a: left ? "start" : "end", leader: null, away: true },
      ];
      // then straight above, higher and higher, joined to the mark by a vertical line
      for (let h = 26; h <= 280; h += 15) cands.push({ x: cx + sgn * 5, y: cy - h, a: A, leader: { x: cx, y0: cy - 10, y1: cy - h - 9 } });
      for (let h = 30; h <= 90; h += 15) cands.push({ x: cx + sgn * 5, y: cy + h, a: A, leader: { x: cx, y0: cy + 10, y1: cy + h + 3 } });
      let chosen: Cand | null = null;
      for (const k of cands) {
        const bx = k.a === "start" ? k.x : k.x - tw;
        const b = { x0: bx, y0: k.y - 11, x1: bx + tw, y1: k.y + 3 };
        if (b.x0 < pad.l || b.x1 > size.w - 4 || b.y0 < pad.t - 6 || b.y1 > size.h - pad.b + 2) continue;
        if (hit(b)) continue;
        // (a leader rises at most 300 px from its mark, so a label far above other marks is in nobody's way)
        if (k.away && clusters.some((q) => q !== c && q.cx > b.x0 - 8 && q.cx < b.x1 + 8 && b.y1 > q.cy - 300 && b.y0 < q.cy + 100)) continue;
        const lb = k.leader ? { x0: k.leader.x - 1.5, x1: k.leader.x + 1.5, y0: Math.min(k.leader.y0, k.leader.y1), y1: Math.max(k.leader.y0, k.leader.y1) } : null;
        // a leader may pass error bars but not another label
        if (lb && labelBoxes.some((q) => !(lb.x1 < q.x0 || lb.x0 > q.x1 || lb.y1 < q.y0 || lb.y0 > q.y1))) continue;
        placed.push(b);
        labelBoxes.push(b);
        if (lb) placed.push(lb);
        chosen = k;
        break;
      }
      out[ci] = { ...(chosen ?? cands[0]), text, show: !!chosen };
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clusters, selected]);

  const hoverIdx = pts.findIndex((p) => p.id === hover);
  const hc = hoverIdx >= 0 ? clusterOf(hoverIdx) : null;
  // learned marks are drawn first, so the heuristic or baseline they sit on stays visible on top
  const drawOrder = pts.map((_, i) => i).sort((i, j) => (pts[i].kind === "learned" ? 0 : 1) - (pts[j].kind === "learned" ? 0 : 1));
  const clickPoint = (i: number) => {
    const c = clusterOf(i);
    const at = c.members.findIndex((m) => pts[m].id === selected);
    if (c.members.length === 1) return onSelect(pts[i].id === selected ? null : pts[i].id);
    // a spot shared by several managers: each click steps to the next one
    onSelect(pts[c.members[(at + 1) % c.members.length]].id);
  };
  return (
    <div
      ref={box}
      className="relative h-full min-h-[280px] w-full overflow-hidden"
    >
      <svg className="absolute inset-0" width={size.w} height={size.h} role="img" aria-label={`${xLabel} against mean wait for every evaluated manager`} onClick={() => onSelect(null)}>
        {yt.map((v) => (
          <g key={`y${v}`}>
            <line x1={pad.l} x2={pad.l + iw} y1={Y(v)} y2={Y(v)} stroke="rgba(20,26,51,0.07)" />
            <text x={pad.l - 8} y={Y(v) + 4} textAnchor="end" fontSize={10.5} fill="#8089A8" className="tnum">
              {v}
            </text>
          </g>
        ))}
        {xt.map((v) => (
          <g key={`x${v}`}>
            <line x1={X(v)} x2={X(v)} y1={pad.t} y2={pad.t + ih} stroke="rgba(20,26,51,0.05)" />
            <text x={X(v)} y={pad.t + ih + 16} textAnchor="middle" fontSize={10.5} fill="#8089A8" className="tnum">
              {`$${+(v / 1000).toFixed(1)}k`}
            </text>
          </g>
        ))}
        <text x={pad.l + iw} y={size.h - 8} textAnchor="end" fontSize={11} fontWeight={600} fill="#4A5275">
          {xLabel} →
        </text>
        <text x={4} y={14} fontSize={11} fontWeight={600} fill="#4A5275">
          ↑ Mean door-to-provider wait, minutes
        </text>
        <text x={pad.l + 8} y={pad.t + ih - 8} fontSize={10.5} fill="#8089A8">
          ↙ better: lower wait, lower cost
        </text>
        {pts.map((p) => {
          const k = kindInfo(p.kind);
          const dim = selected && selected !== p.id ? 0.35 : 1;
          return (
            <g key={`e${p.id}`} stroke={k.color} strokeWidth={1.5} opacity={0.55 * dim} strokeLinecap="round">
              {p.ex > 0 && <path d={`M${X(p.x - p.ex)} ${Y(p.y)}H${X(p.x + p.ex)}M${X(p.x - p.ex)} ${Y(p.y) - 3}v6M${X(p.x + p.ex)} ${Y(p.y) - 3}v6`} />}
              {p.ey > 0 && <path d={`M${X(p.x)} ${Y(p.y - p.ey)}V${Y(p.y + p.ey)}M${X(p.x) - 3} ${Y(p.y - p.ey)}h6M${X(p.x) - 3} ${Y(p.y + p.ey)}h6`} />}
            </g>
          );
        })}
        {clusters.map((c, ci) => {
          const l = labels[ci];
          const on = c.members.some((i) => pts[i].id === selected);
          if (!l || !(l.show || on)) return null;
          const dim = selected && !on ? 0.45 : 1;
          return (
            <g key={`l${ci}`} opacity={dim} pointerEvents="none" data-label={pts[c.members[0]].id}>
              {l.leader && <line x1={l.leader.x} y1={l.leader.y0} x2={l.leader.x} y2={l.leader.y1} stroke="#9AA3B5" strokeWidth={1} />}
              <text x={l.x} y={l.y} textAnchor={l.a} fontSize={11} fontWeight={on ? 700 : 500} fill={on ? "#141A33" : "#4A5275"} stroke="#fff" strokeWidth={3} paintOrder="stroke" strokeLinejoin="round" style={{ whiteSpace: "pre" }}>
                {l.text}
              </text>
            </g>
          );
        })}
        {drawOrder.map((i) => {
          const p = pts[i];
          const k = kindInfo(p.kind);
          const on = selected === p.id;
          const dim = selected && !on ? 0.4 : 1;
          return (
            <g
              key={p.id}
              data-point={p.id}
              transform={`translate(${X(p.x)} ${Y(p.y)})`}
              opacity={dim}
              style={{ cursor: "pointer" }}
              onClick={(e) => {
                e.stopPropagation();
                clickPoint(i);
              }}
              onPointerEnter={() => setHover(p.id)}
              onPointerLeave={() => setHover(null)}
            >
              <circle r={16} fill="transparent" />
              {on && <circle r={13} fill="none" stroke="#2F55F5" strokeWidth={2} />}
              {p.caveat && <circle r={11} fill="none" stroke="#141A33" strokeWidth={1.2} strokeDasharray="2 3" />}
              <Marker shape={k.shape} color={k.color} size={p.human ? 13 : 12} ring />
            </g>
          );
        })}
        {clusters
          .filter((c) => c.members.length > 1)
          .map((c, ci) => (
            <g key={`n${ci}`} transform={`translate(${c.cx + 9} ${c.cy - 9})`} pointerEvents="none" data-cluster={c.members.length}>
              <circle r={7} fill="#141A33" stroke="#fff" strokeWidth={1.5} />
              <text y={3.5} textAnchor="middle" fontSize={9.5} fontWeight={700} fill="#fff">
                {c.members.length}
              </text>
            </g>
          ))}
      </svg>
      {hc && (
        <div className="pointer-events-none absolute z-10 w-[250px] rounded-xl border border-line bg-white/95 px-3 py-2 text-[11px] shadow-card" style={{ left: Math.max(4, Math.min(hc.cx + 18, size.w - 258)), top: Math.max(4, Math.min(hc.cy - 30, size.h - 80 - hc.members.length * 46)) }} data-testid="tradeoff-tip">
          {hc.members.length > 1 && <div className="mb-1 font-semibold text-ink">{hc.members.length} managers at this spot · click to step through them</div>}
          {hc.members.map((i) => {
            const hp = pts[i];
            const k = kindInfo(hp.kind);
            return (
              <div key={hp.id} className="border-t border-line py-1 first:border-t-0">
                <div className="flex items-center gap-1.5 font-semibold text-ink">
                  <svg width="11" height="11" viewBox="-7 -7 14 14" className="shrink-0" aria-hidden>
                    <Marker shape={k.shape} color={k.color} size={9} />
                  </svg>
                  {hp.label}
                </div>
                <div className="tnum flex justify-between text-ink-2">
                  <span>{xLabel.replace(" per day", " / day")}</span>
                  <b className="text-ink">{money(hp.x)}{hp.ex ? ` ± ${money(hp.ex)}` : ""}</b>
                </div>
                <div className="tnum flex justify-between text-ink-2">
                  <span>Mean wait</span>
                  <b className="text-ink">{num(hp.y, 1)}{hp.ey ? ` ± ${num(hp.ey, 1)}` : ""} min</b>
                </div>
                {hc.members.length === 1 && (hp.n ? <div className="mt-0.5 text-ink-3">{hp.n} seeds · bars show 95% interval</div> : <div className="mt-0.5 text-ink-3">{hp.caveat ? "single short run · not comparable" : "single run"}</div>)}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function TradeoffView({ narrow, top, onWatch, onCompare }: { narrow: boolean; top: React.ReactNode; onWatch: (rolloutId: string) => void; onCompare: (a: string, b: string) => void }) {
  const { data, source, loading } = useApi(() => api.results(), []);
  const rollouts = useUI((s) => s.rollouts);
  const globalScenario = useUI((s) => s.scenarioId);
  const scenarios = useMemo(() => {
    const evaluated = Array.from(new Set([...(data?.protocol?.scenarios ?? []), ...(data?.rows ?? []).map((r) => r.scenario)]));
    // scenarios that only have a human run are offered only when nothing has been evaluated at all
    return evaluated.length ? evaluated : Array.from(new Set((data?.human_runs ?? []).map((r) => r.scenario)));
  }, [data]);
  const managers = useUI((s) => s.managers);
  // a staffing-cost metric is offered as an alternative x-axis only if the result rows actually carry one
  const laborKey = useMemo(() => {
    const keys = new Set((data?.rows ?? []).flatMap((r) => Object.keys(r.metrics)));
    return [...keys].find((k) => /(labou?r|staffing).*cost|cost.*(labou?r|staffing)/i.test(k) && /per_day/i.test(k)) ?? [...keys].find((k) => /(labou?r|staffing).*cost|cost.*(labou?r|staffing)/i.test(k)) ?? null;
  }, [data]);
  // Staffing cost is what a manager's decisions move (total cost is dominated by costs no action touches), so it is
  // the default x-axis whenever the results carry it.
  const [xAxis, setXAxis] = useState<"total" | "labor">("labor");
  const xKey = xAxis === "labor" && laborKey ? laborKey : "cost_per_day";
  const xLabel = xKey === "cost_per_day" ? "Cost per day" : "Staffing cost per day";
  const validation = useApi(() => api.validation(), []);
  const [scenario, setScenario] = useState<string | null>(null);
  const sc = scenario && scenarios.includes(scenario) ? scenario : scenarios.includes(globalScenario) ? globalScenario : (scenarios[0] ?? "");
  const [selected, setSelected] = useState<string | null>(null);
  const [other, setOther] = useState<string>("");

  const pts: Pt[] = useMemo(() => {
    if (!data) return [];
    const out: Pt[] = [];
    for (const r of data.rows) {
      if (r.scenario !== sc) continue;
      const c = r.metrics[xKey];
      const w = r.metrics.wait_mean_min;
      if (!c || !w) continue;
      out.push({ id: r.manager_id, label: shortManager(r), full: prettyManager(r.label), kind: r.kind, objective: r.objective, x: c.mean, y: w.mean, ex: c.ci95 ?? 0, ey: w.ci95 ?? 0, n: r.n_seeds, metrics: r.metrics });
    }
    const humans = (data.human_runs ?? []).filter((h) => h.scenario === sc && h.summary?.[xKey] != null && h.summary?.wait_mean_min != null);
    const last = humans[humans.length - 1];
    if (last) {
      const hours = Math.round((last.days ?? 0) * 24);
      const len = hours >= 48 ? `${+(hours / 24).toFixed(1)} d` : `${hours} h`;
      const need = data.protocol?.days ?? 0;
      const short = need > 0 && (last.days ?? 0) < need;
      out.push({
        id: "__human",
        label: `${last.label || "You"} · ${short ? `not comparable (${len} run)` : `${len} run`}`,
        kind: "human",
        x: last.summary[xKey],
        y: last.summary.wait_mean_min,
        ex: 0,
        ey: 0,
        human: true,
        caveat: short ? `This run lasted ${len} on one seed; the managers were each evaluated over ${need} days${Array.isArray(data.protocol?.seeds) ? ` on ${data.protocol!.seeds!.length} seeds` : ""}. A short run misses the slow effects (nights, weekends, staffing changes), so the positions are not comparable.` : undefined,
        metrics: Object.fromEntries(Object.entries(last.summary).map(([k, v]) => [k, { mean: v }])),
      });
    }
    return out;
  }, [data, sc, xKey]);
  const pendingKinds = (Object.keys(KIND) as ManagerKind[]).filter((k) => k !== "human" && managers.some((m) => m.kind === k) && !pts.some((p) => p.kind === k));

  const rolloutFor = (managerId: string): RolloutListItem | undefined => rollouts.find((r) => r.manager.id === managerId && r.scenario === sc) ?? rollouts.find((r) => r.manager.id === managerId);
  const sel = pts.find((p) => p.id === selected) ?? null;
  const selRollout = sel ? rolloutFor(sel.id) : undefined;
  const others = pts.map((p) => ({ p, r: rolloutFor(p.id) })).filter((o) => o.r && o.p.id !== sel?.id);
  const otherId = others.some((o) => o.r!.rollout_id === other) ? other : (others[0]?.r?.rollout_id ?? "");
  const kindsShown = (Object.keys(KIND) as ManagerKind[]).filter((k) => pts.some((p) => p.kind === k));

  return (
    <>
      <div className="fixed inset-0 opacity-60">
        <HospitalScene feed={feeds.a} />
      </div>
      <div className={`fixed inset-0 flex flex-col gap-3 ${narrow ? "overflow-y-auto p-2" : "p-3"}`}>
        {top}
        <div className={`flex min-h-0 flex-1 gap-3 ${narrow ? "flex-col" : ""}`}>
          <div className={`glass-solid flex min-w-0 flex-col p-4 ${narrow ? "flex-none" : "min-h-0 flex-1"}`} data-testid="tradeoff">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <div className="min-w-0">
                <div className="text-[17px] font-semibold tracking-[-0.01em] text-ink">{xKey === "cost_per_day" ? "Cost against wait" : "Staffing cost against wait"}</div>
                <div className="text-[12px] text-ink-3">
                  Every evaluated manager on the same scenario and seeds
                  {data?.protocol?.days ? ` · ${data.protocol.days}-day episodes` : ""}
                  {Array.isArray(data?.protocol?.seeds) && data!.protocol!.seeds!.length ? ` · ${data!.protocol!.seeds!.length} held-out seeds` : ""}
                </div>
              </div>
              <div className="ml-auto flex max-w-full flex-wrap items-center justify-end gap-2">
                {source === "fixture" ? <SourceChip tag="fixture" /> : <SimTag />}
                {laborKey && (
                  <div className="seg" data-testid="xaxis-toggle" title={`Staffing cost is read from the results metric “${laborKey}”`}>
                    <button data-on={xAxis === "labor"} onClick={() => setXAxis("labor")}>
                      Staffing cost
                    </button>
                    <button data-on={xAxis === "total"} onClick={() => setXAxis("total")}>
                      Total cost
                    </button>
                  </div>
                )}
                <div className="seg" data-testid="scenario-toggle">
                  {scenarios.map((s) => (
                    <button key={s} data-on={s === sc} data-scenario={s} onClick={() => { setScenario(s); setSelected(null); }}>
                      {titleCase(s).replace(/ week$/, "")}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            {source === "fixture" && (
              <div className="mt-3 rounded-xl bg-[#FDF6E7] px-3 py-2 text-[11.5px] leading-snug text-[#8A5A00]" data-testid="fixture-banner">
                Placeholder points. The server is unreachable, so this chart is drawn from a hand-typed fixture file to show the layout. These are not evaluation results and say nothing about which manager is better.
              </div>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] font-medium text-ink-2">
              {kindsShown.map((k) => (
                <span key={k} className="flex items-center gap-1.5">
                  <svg width="14" height="14" viewBox="-8 -8 16 16" aria-hidden>
                    <Marker shape={KIND[k].shape} color={KIND[k].color} size={10} />
                  </svg>
                  {KIND[k].label}
                </span>
              ))}
              {pendingKinds.map((k) => (
                <span key={k} className="flex items-center gap-1.5 text-ink-3" title="Managers of this kind are listed by the server but have no evaluation results yet">
                  <svg width="14" height="14" viewBox="-8 -8 16 16" aria-hidden opacity={0.45}>
                    <Marker shape={KIND[k].shape} color={KIND[k].color} size={10} />
                  </svg>
                  {KIND[k].label} (not evaluated yet)
                </span>
              ))}
              <span className="text-ink-3">· bars: 95% interval across seeds</span>
              {xKey !== "cost_per_day" && (data?.human_runs ?? []).some((h) => h.scenario === sc && h.summary?.[xKey] == null) && (
                <span className="text-ink-3" data-testid="human-axis-note">
                  · your own run has no staffing-cost figure, so it appears on the Total cost axis only
                </span>
              )}
            </div>
            <div className={narrow ? "mt-2 h-[340px] flex-none" : "mt-2 min-h-0 flex-1"}>
              {loading ? <div className="flex h-full items-center justify-center text-[12px] text-ink-3">Loading results…</div> : pts.length ? <Scatter pts={pts} selected={selected} onSelect={setSelected} xLabel={xLabel} /> : <div className="flex h-full flex-col items-center justify-center gap-1 px-6 text-center text-[12px] text-ink-3" data-testid="tradeoff-empty">
                  <div className="text-[13px] font-semibold text-ink-2">No evaluated managers yet</div>
                  <div>{data?.note ?? "The results table is empty for this scenario."}</div>
                  <div>Points appear here as evaluations finish. Finish a run in Play to add your own.</div>
                </div>}
            </div>
            <Disclaimer feed={feeds.a} className="mt-2 !text-left" />
          </div>

          <div className={`glass-solid flex flex-col ${narrow ? "flex-none" : "min-h-0 w-[380px] shrink-0"}`} data-testid="tradeoff-side">
            {sel ? (
              <div className="border-b border-line p-4">
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="eyebrow">Selected manager</div>
                    <div className="text-[15px] font-semibold leading-snug text-ink" title={sel.full} data-testid="selected-name">{sel.label}</div>
                    {sel.full && <div className="text-[10.5px] leading-snug text-ink-3">{sel.full}</div>}
                  </div>
                  <KindChip kind={sel.kind} />
                </div>
                <div className="mt-1 text-[11px] text-ink-3">
                  {objectiveWords(managers.find((m) => m.id === sel.id), data) ? `Objective: ${objectiveWords(managers.find((m) => m.id === sel.id), data)} · ` : ""}
                  {sel.human ? "your last run, single seed" : `${sel.n ?? "?"} seeds`}
                </div>
                {!sel.human && managerStory(sel.id, sc) && (
                  <div className="mt-2 rounded-xl bg-[#141a33]/[0.035] px-3 py-2 text-[11px] leading-snug text-ink-2" data-testid="manager-story">
                    {managerStory(sel.id, sc)}
                  </div>
                )}
                {sel.caveat && <div className="mt-2 rounded-xl bg-[#FDF6E7] px-3 py-2 text-[11px] leading-snug text-[#8A5A00]" data-testid="human-caveat">{sel.caveat}</div>}
                <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5">
                  {TABLE.filter(([k]) => sel.metrics[k]).map(([k, label, unit]) => (
                    <div key={k}>
                      <div className="text-[10.5px] text-ink-3">{label}</div>
                      <div className="tnum text-[13px] font-semibold text-ink">
                        {metricValue(sel.metrics[k].mean, unit)}
                        {sel.metrics[k].ci95 ? <span className="ml-1 text-[11px] font-medium text-ink-3">± {metricValue(sel.metrics[k].ci95!, unit)}</span> : null}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <button className="btn-primary" disabled={!selRollout?.has_segments} onClick={() => selRollout && onWatch(selRollout.rollout_id)} data-testid="tradeoff-watch" title={selRollout ? "Replay this manager's recorded rollout" : "No recorded rollout for this manager"}>
                    Watch
                  </button>
                  <button className="btn-quiet" disabled={!selRollout || !otherId} onClick={() => selRollout && otherId && onCompare(selRollout.rollout_id, otherId)} data-testid="tradeoff-compare">
                    Compare with
                  </button>
                  <select className="select min-w-0 flex-1" value={otherId} onChange={(e) => setOther(e.target.value)} disabled={!others.length} aria-label="Manager to compare with">
                    {others.length === 0 && <option value="">no other rollout</option>}
                    {others.map((o) => (
                      <option key={o.r!.rollout_id} value={o.r!.rollout_id} title={o.p.full}>
                        {o.p.label}
                      </option>
                    ))}
                  </select>
                </div>
                {!selRollout && <div className="mt-2 text-[11px] text-ink-3">No recorded rollout is available for this manager, so it cannot be replayed.</div>}
              </div>
            ) : (
              <div className="border-b border-line p-4 text-[12px] leading-relaxed text-ink-3">
                <div className="eyebrow mb-1">How to read this</div>
                Each mark is one manager, averaged over held-out seeds; the bars are 95% intervals. Marks that overlap did not differ on these two measures; a numbered badge says how many managers share a spot, and clicking it steps through them. Click a mark for its details, to replay it, or to put two side by side.
              </div>
            )}
            <div className="scroll-thin min-h-0 flex-1 overflow-auto p-3">
              <ValidationCard v={validation.data} />
              <table className="w-full border-separate border-spacing-0 text-[11.5px]" data-testid="tradeoff-table">
                <thead>
                  <tr className="text-left text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-3">
                    <th className="pb-1.5 pl-1 font-semibold">Manager</th>
                    <th className="pb-1.5 text-right font-semibold">{xKey === "cost_per_day" ? "Cost / day" : "Staffing / day"}</th>
                    <th className="pb-1.5 text-right font-semibold">Wait</th>
                    <th className="pb-1.5 pr-1 text-right font-semibold">LWBS</th>
                  </tr>
                </thead>
                <tbody>
                  {[...pts].sort((a, b) => a.y - b.y).map((p) => {
                    const k = kindInfo(p.kind);
                    const on = p.id === selected;
                    return (
                      <tr key={p.id} data-row={p.id} title={p.full} className={`cursor-pointer ${on ? "bg-accent-soft" : "hover:bg-white"}`} onClick={() => setSelected(on ? null : p.id)}>
                        <td className="rounded-l-lg border-t border-line py-1.5 pl-1 pr-2">
                          <span className="flex items-center gap-1.5">
                            <svg width="12" height="12" viewBox="-7 -7 14 14" className="shrink-0" aria-hidden>
                              <Marker shape={k.shape} color={k.color} size={9} />
                            </svg>
                            <span className="min-w-0">
                              <span className="block break-words font-semibold leading-tight text-ink">{p.label.replace(/\s*\[fixture\]$/, "")}</span>
                              <span className="block text-[10px] text-ink-3">{k.label}</span>
                            </span>
                          </span>
                        </td>
                        <td className="tnum border-t border-line py-1.5 text-right text-ink">{money(p.x)}</td>
                        <td className="tnum border-t border-line py-1.5 text-right text-ink">{num(p.y, 1)} min</td>
                        <td className="tnum rounded-r-lg border-t border-line py-1.5 pr-1 text-right text-ink">{p.metrics.lwbs_rate ? metricValue(p.metrics.lwbs_rate.mean, "fraction") : "–"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
