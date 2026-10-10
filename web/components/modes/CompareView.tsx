"use client";
import { useState } from "react";
import type { FeedState } from "@/lib/feed";
import { metricValue, titleCase } from "@/lib/format";
import { useFeedState } from "@/lib/hooks";
import { SERIES } from "@/lib/palette";
import { managerStory, prettyManager, shortManager } from "@/lib/story";
import { feeds, openCompare, startLiveCompare, stopLiveCompare, summarise, transport } from "@/lib/session";
import { useUI } from "@/lib/ui";
import HospitalScene from "../scene/HospitalScene";
import { Icon, ICONS, KindChip, SimTag, SourceChip } from "../ui/atoms";
import { CameraPill, Disclaimer, Legend } from "../ui/Chrome";
import { Inspector } from "../ui/Inspector";
import { LineChart } from "../ui/LineChart";
import { chartView, CHART_METRICS, playheadHour, RecordingNote, scrubTo, ZoomToggle, type ChartZoom } from "../ui/Timeline";
import { RolloutPicker } from "./WatchPanel";

const DIFF: [string, string, string, boolean][] = [
  ["wait_mean_min", "Mean wait", "minutes", true],
  ["wait_p95_min", "95th pct wait", "minutes", true],
  ["ed_los_median_min", "Median ED stay", "minutes", true],
  ["lwbs_rate", "Left without being seen", "fraction", true],
  ["cost_per_day", "Cost per day", "usd", true],
  ["margin_per_day", "Margin per day", "usd", false],
  ["cost_per_treated", "Cost per treated patient", "usd", true],
  ["deaths_per_10k", "Deaths per 10k arrivals", "", true],
  ["boarding_hours_per_day", "Boarding hours per day", "", true],
  ["overtime_hours_per_day", "Overtime hours per day", "", true],
];

/** Value for the hour under the playhead; the hour in progress has no value yet, so fall back to the latest complete one. */
const lastAt = (arr: number[] | undefined, hour: number | undefined) => (arr?.length ? arr[Math.max(0, Math.min(arr.length - 1, Math.floor(hour ?? 0)))] : NaN);

const PANE_INSETS = { l: 0, r: 0, t: 64, b: 0 };

function PaneHeader({ f, side, color }: { f: FeedState; side: "A" | "B"; color: string }) {
  const k = (f.snap?.kpis ?? {}) as Record<string, number>;
  const h = f.header;
  return (
    <div className="glass pointer-events-auto flex max-w-full flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
      <span className="flex h-5 w-5 items-center justify-center rounded-md text-[11px] font-bold text-white" style={{ background: color }}>
        {side}
      </span>
      <span className="max-w-[260px] truncate text-[13px] font-semibold text-ink" title={h ? prettyManager(h.manager.label) : undefined} data-testid="pane-title">{h ? shortManager(h.manager) : "…"}</span>
      {h && <KindChip kind={h.manager.kind} />}
      {f.origin === "fixture" && <SourceChip tag="fixture" />}
      <span className="tnum flex items-center gap-3 text-[11px] text-ink-3">
        <span>
          wait <b className="font-semibold text-ink">{metricValue(k.wait_mean_min, "minutes")}</b>
        </span>
        <span>
          waiting <b className="font-semibold text-ink">{metricValue(k.waiting_count)}</b>
        </span>
        <span>
          census <b className="font-semibold text-ink">{metricValue(k.ed_census)}</b>
        </span>
      </span>
    </div>
  );
}

function DiffTable({ a, b }: { a: FeedState; b: FeedState }) {
  // live runs send a summary once a simulated day; until then derive what the hourly series allows
  const sum = (f: FeedState) => f.summary ?? (f.origin === "live" && Object.keys(f.hourly).length ? summarise(f.hourly, Math.max(...Object.values(f.hourly).map((v) => v.length))) : {});
  const sa = sum(a);
  const sb = sum(b);
  const rows = DIFF.filter(([k]) => sa[k] != null || sb[k] != null);
  return (
    <div data-testid="diff-table">
      <table className="w-full border-separate border-spacing-0 text-[12px]">
        <thead>
          <tr className="text-left text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-3">
            <th className="pb-1.5 font-semibold">Episode summary</th>
            <th className="pb-1.5 text-right font-semibold">
              <span className="mr-1 inline-block h-2 w-2 rounded-sm align-middle" style={{ background: SERIES[0] }} />A
            </th>
            <th className="pb-1.5 text-right font-semibold">
              <span className="mr-1 inline-block h-2 w-2 rounded-sm align-middle" style={{ background: SERIES[1] }} />B
            </th>
            <th className="pb-1.5 text-right font-semibold">B vs A</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([k, label, unit, lowerBetter]) => {
            const va = sa[k];
            const vb = sb[k];
            const d = va != null && vb != null && va !== 0 ? (vb - va) / Math.abs(va) : NaN;
            const better = isFinite(d) && Math.abs(d) > 0.005 ? d < 0 === lowerBetter : null;
            return (
              <tr key={k}>
                <td className="border-t border-line py-1.5 pr-2 text-ink-2">{label}</td>
                <td className="tnum border-t border-line py-1.5 text-right font-semibold text-ink">{metricValue(va, unit)}</td>
                <td className="tnum border-t border-line py-1.5 text-right font-semibold text-ink">{metricValue(vb, unit)}</td>
                <td className="tnum border-t border-line py-1.5 pl-2 text-right">
                  {isFinite(d) ? (
                    <span className="chip" style={{ background: better == null ? "rgba(20,26,51,0.05)" : better ? "#DFF5EA" : "#FDE7E8", color: better == null ? "#8089A8" : better ? "#11734B" : "#B4232A" }}>
                      {better == null ? "" : d > 0 ? "+" : "−"}
                      {Math.abs(d * 100).toFixed(0)}%
                    </span>
                  ) : (
                    <span className="text-ink-3">–</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length === 0 && <div className="py-3 text-[12px] text-ink-3">These rollouts carry no episode summary.</div>}
      <div className="mt-2 text-[10.5px] leading-snug text-ink-3">Green means B is better on that row (lower wait and cost, higher margin). One seed: differences are not significance-tested here; see the trade-off chart for multi-seed results.</div>
    </div>
  );
}

export function CompareView({ narrow, top }: { narrow: boolean; top: React.ReactNode }) {
  const a = useFeedState(feeds.a, 300);
  const b = useFeedState(feeds.b, 300);
  const ids = useUI((s) => s.compareIds);
  const selection = useUI((s) => s.selection);
  const liveState = useUI((s) => s.compareLive);
  const liveManagers = useUI((s) => s.compareManagers);
  const managers = useUI((s) => s.managers);
  const note = useUI((s) => s.compareNote);
  const seed = useUI((s) => s.play.seed);
  const scenarioId = useUI((s) => s.scenarioId);
  const set = useUI((s) => s.set);
  useUI((s) => s.results); // manager stories are composed from the results table
  const [source, setSource] = useState<"recorded" | "live">("recorded");
  const [zoom, setZoom] = useState<ChartZoom>("all");
  const isLive = liveState === "live" || liveState === "connecting";
  const runnable = managers.filter((m) => m.kind !== "human" && m.available !== false);
  const sameSeed = a.header && b.header ? a.header.seed === b.header.seed && a.header.scenario === b.header.scenario : true;
  const chartCursor = useUI((s) => s.chartCursor);
  const cur = chartCursor != null && a.origin !== "live" ? chartCursor - a.hour0 : playheadHour(a);
  const selFeed = selection?.feed === "b" ? b : a;

  const charts = (
    <div className={`grid gap-3 ${narrow ? "grid-cols-1" : "grid-cols-2 min-[1500px]:grid-cols-4"}`} data-testid="compare-charts">
      {CHART_METRICS.slice(0, narrow ? 2 : 4).map((m, mi) => {
        const view = chartView([a.hourly[m.key]?.length ?? 0, b.hourly[m.key]?.length ?? 0], a.hour0, cur, zoom);
        return (
        <div key={m.key} className="glass pointer-events-auto px-3 pb-1.5 pt-2.5">
          <div className="mb-0.5 flex items-center gap-2">
            <span className="text-[12px] font-semibold text-ink">{m.label}</span>
            <span className="tnum flex items-center gap-2 text-[11px] text-ink-3">
              {[a, b].map((f, i) => (
                <span key={i} className="flex items-center gap-1">
                  <span className="h-[3px] w-3 rounded-full" style={{ background: SERIES[i] }} />
                  {i === 0 ? "A" : "B"} <b className="font-semibold text-ink">{metricValue(lastAt(f.hourly[m.key], cur), m.unit)}</b>
                </span>
              ))}
            </span>
            <span className="ml-auto flex items-center gap-2">
              {view.long && mi === 0 && <ZoomToggle zoom={zoom} onZoom={setZoom} />}
              {view.long && mi !== 0 && <span className="text-[10px] text-ink-3">{view.step === 24 ? "daily mean · band = day’s range" : "72 h window"}</span>}
              <SimTag />
            </span>
          </div>
          <LineChart
            series={[
              { name: `A · ${shortManager(a.header?.manager)}`, color: SERIES[0], ...view.shape(a.hourly[m.key] ?? []) },
              { name: `B · ${shortManager(b.header?.manager)}`, color: SERIES[1], ...view.shape(b.hourly[m.key] ?? []) },
            ]}
            unit={m.unit}
            height={narrow ? 84 : 92}
            cursor={view.cursor}
            hour0={view.hour0}
            step={view.step}
            onScrub={transport.canSeek() ? (h) => scrubTo(h + view.offset + a.hour0, view.step === 24) : undefined}
            bands={a.segments.map((s) => ({ start: s.start / 12 - a.hour0 - view.offset, end: s.end / 12 - a.hour0 - view.offset }))}
          />
        </div>
        );
      })}
    </div>
  );

  const side = (
    <div className={`glass pointer-events-auto flex min-h-0 flex-col ${narrow ? "" : "w-[360px] shrink-0"}`} data-testid="compare-panel">
      <div className="space-y-2 px-3.5 pb-3 pt-3.5">
        <div className="flex items-center gap-2">
          <span className="eyebrow">Same seed, two managers</span>
          <span className="ml-auto">
            <SimTag />
          </span>
        </div>
        <div className="seg w-full [&>button]:flex-1" data-testid="compare-source">
          <button data-on={source === "recorded" && !isLive} disabled={isLive} onClick={() => setSource("recorded")}>
            Recorded rollouts
          </button>
          <button data-on={source === "live" || isLive} onClick={() => setSource("live")} data-testid="compare-live-tab">
            Run live
          </button>
        </div>
        {(["A", "B"] as const).map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[11px] font-bold text-white" style={{ background: SERIES[i] }}>
              {s}
            </span>
            {source === "live" || isLive ? (
              <select
                className="select w-full"
                disabled={isLive}
                value={liveManagers[i]}
                aria-label={`Manager ${s}`}
                onChange={(e) => set({ compareManagers: i === 0 ? [e.target.value, liveManagers[1]] : [liveManagers[0], e.target.value] })}
              >
                {!runnable.some((m) => m.id === liveManagers[i]) && <option value={liveManagers[i]}>{liveManagers[i]}</option>}
                {runnable.map((m) => (
                  <option key={m.id} value={m.id} title={prettyManager(m.label)}>
                    {shortManager(m)}
                  </option>
                ))}
              </select>
            ) : (
              <RolloutPicker value={ids[i]} testid={`compare-pick-${s}`} onChange={(id) => void openCompare(i === 0 ? id : (ids[0] ?? id), i === 1 ? id : (ids[1] ?? id))} />
            )}
          </div>
        ))}
        {(source === "live" || isLive) &&
          (isLive ? (
            <button className="btn-quiet w-full" onClick={() => void stopLiveCompare()} data-testid="compare-live-stop">
              Stop both runs
            </button>
          ) : (
            <button className="btn-primary w-full" onClick={() => void startLiveCompare(liveManagers[0], liveManagers[1])} data-testid="compare-live-start">
              <Icon d={ICONS.play} size={12} stroke={2.4} />
              Run both · {titleCase(scenarioId)} · seed {seed}
            </button>
          ))}
        {note && <div className="rounded-xl bg-[#FDF6E7] px-3 py-2 text-[11px] leading-snug text-[#8A5A00]">{note}</div>}
        {a.header && (
          <div className="text-[11px] leading-snug text-ink-3">
            {titleCase(a.header.scenario)} · seed {a.header.seed} ·{" "}
            {a.origin === "live" ? "two live simulations with the same arrivals; each runs on its own clock, so they can drift a few ticks apart." : "clocks locked together."}
            {!sameSeed && <span className="font-semibold text-[#B4232A]"> These two runs differ in scenario or seed, so patients are not the same.</span>}
            {a.origin !== "live" && ids[0] && ids[0] === ids[1] && <span className="font-semibold text-[#8A5A00]"> Both sides show the same recording. Pick a different one for B, or use “Run live”.</span>}
          </div>
        )}
        {[a, b].map((f, i) => {
          const story = f.header ? managerStory(f.header.manager.id, f.header.scenario) : "";
          return story ? (
            <div key={i} className="rounded-xl bg-[#141a33]/[0.035] px-3 py-2 text-[11px] leading-snug text-ink-2" data-testid="manager-story">
              <b className="font-semibold text-ink">{i === 0 ? "A" : "B"}:</b> {story}
            </div>
          ) : null;
        })}
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto border-t border-line px-3.5 pb-3 pt-3">
        <DiffTable a={a} b={b} />
      </div>
    </div>
  );

  const pane = (feedKey: "a" | "b", f: FeedState, i: number) => (
    <div className="relative min-h-0 min-w-0 flex-1 overflow-hidden rounded-2xl border border-white/70 shadow-card" data-testid={`pane-${feedKey}`} style={{ background: "#E9ECFB" }}>
      <div className="absolute inset-0">
        <HospitalScene feed={feeds[feedKey]} sync insets={PANE_INSETS} />
      </div>
      <div className="pointer-events-none absolute left-2 right-2 top-2 flex">
        <PaneHeader f={f} side={i === 0 ? "A" : "B"} color={SERIES[i]} />
      </div>
    </div>
  );

  if (narrow)
    return (
      <div className="fixed inset-0 flex flex-col gap-2 overflow-y-auto p-2">
        {top}
        <div className="flex h-[70vh] shrink-0 flex-col gap-2">
          {pane("a", a, 0)}
          {pane("b", b, 1)}
        </div>
        {charts}
        {side}
        {selection && <Inspector f={selFeed} className="max-h-[60vh]" />}
        <Disclaimer feed={feeds.a} className="px-1 pb-2" />
      </div>
    );

  return (
    <div className="fixed inset-0 flex flex-col gap-3 p-3">
      {top}
      <div className="flex min-h-0 flex-1 gap-3">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
          <div className="relative flex min-h-0 flex-1 gap-3">
            {pane("a", a, 0)}
            {pane("b", b, 1)}
            <div className="pointer-events-none absolute inset-y-0 left-1/2 z-10 flex -translate-x-1/2 items-center">
              <CameraPill />
            </div>
          </div>
          {charts}
          <RecordingNote f={a} />
          <div className="flex items-center justify-between gap-4">
            <Disclaimer feed={feeds.a} className="!text-left" />
            <div className="shrink-0 max-[1500px]:hidden">
              <Legend />
            </div>
          </div>
        </div>
        <div className="flex min-h-0 flex-col gap-3">
          {selection ? <Inspector f={selFeed} className="w-[360px] flex-1" /> : side}
        </div>
      </div>
    </div>
  );
}
