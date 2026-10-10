"use client";
import { useState } from "react";
import type { FeedState } from "@/lib/feed";
import { hhmm, metricValue, tickClock, DOW, DOW_LONG } from "@/lib/format";
import { useUI } from "@/lib/ui";
import { SERIES } from "@/lib/palette";
import { transport } from "@/lib/session";
import { shortManager } from "@/lib/story";
import { SimTag } from "./atoms";
import { LineChart, type Series } from "./LineChart";

export const CHART_METRICS: { key: string; label: string; unit: string }[] = [
  { key: "wait_mean_min", label: "Wait", unit: "minutes" },
  { key: "ed_census", label: "Census", unit: "patients" },
  { key: "cost_total", label: "Cost", unit: "usd" },
  { key: "lwbs", label: "LWBS", unit: "patients" },
];

/** Playhead position as an index into the hourly arrays. */
export const playheadHour = (f: FeedState) => (f.snap ? f.snap.t / 12 - f.hour0 : undefined);

export type ChartZoom = "all" | "window";
const LONG = 120; // hours beyond which hourly points stop being readable at panel width
const WINDOW = 72;

/**
 * A readable view of an hourly series. Short runs are drawn as they are. Long ones (a 30-day rollout is 720 points)
 * default to one point per day (the day's mean, with a band from its lowest to its highest hour), and can be
 * switched to an hourly window around the playhead.
 */
export function chartView(lengths: number[], hour0: number, cursor: number | undefined, zoom: ChartZoom) {
  const n = Math.max(0, ...lengths);
  const long = n > LONG;
  if (!long) return { long, step: 1, hour0, cursor, offset: 0, shape: (v: number[]): Pick<Series, "values" | "lo" | "hi"> => ({ values: v }) };
  if (zoom === "window") {
    const c = Math.max(0, Math.min(n - 1, Math.floor(cursor ?? 0)));
    const start = Math.max(0, Math.min(n - WINDOW, c - WINDOW / 2));
    return { long, step: 1, hour0: hour0 + start, cursor: cursor != null ? cursor - start : undefined, offset: start, shape: (v: number[]): Pick<Series, "values" | "lo" | "hi"> => ({ values: v.slice(start, start + WINDOW) }) };
  }
  const shape = (v: number[]): Pick<Series, "values" | "lo" | "hi"> => {
    const values: number[] = [];
    const lo: number[] = [];
    const hi: number[] = [];
    for (let d = 0; d * 24 < v.length; d++) {
      const day = v.slice(d * 24, d * 24 + 24).filter((x) => isFinite(x));
      values.push(day.length ? day.reduce((a, b) => a + b, 0) / day.length : NaN);
      lo.push(day.length ? Math.min(...day) : NaN);
      hi.push(day.length ? Math.max(...day) : NaN);
    }
    return { values, lo, hi };
  };
  return { long, step: 24, hour0, cursor, offset: 0, shape };
}

export function ZoomToggle({ zoom, onZoom }: { zoom: ChartZoom; onZoom: (z: ChartZoom) => void }) {
  return (
    <div className="seg" title="Daily: one point per day (mean, with the range of that day's hours). 72 h: hourly values around the playhead." data-testid="chart-zoom">
      <button data-on={zoom === "all"} onClick={() => onZoom("all")}>
        Daily
      </button>
      <button data-on={zoom === "window"} onClick={() => onZoom("window")}>
        72 h
      </button>
    </div>
  );
}

/** "Day 2 · Tue 08:00–20:00" for a recorded window, from its ticks (not from the recording's own label). */
export function windowLabel(w: { start: number; end: number }, tickMinutes = 5): string {
  const a = tickClock(w.start, tickMinutes);
  const b = tickClock(w.end, tickMinutes);
  const minutes = (w.end - w.start) * tickMinutes;
  // a window that starts at midnight and runs a whole day reads "00:00–00:00" otherwise
  if (a.minute_of_day === 0 && minutes >= 1435 && minutes <= 1445) return `Day ${a.day + 1} · ${DOW_LONG[a.dow]} (full day)`;
  if (a.minute_of_day === 0 && minutes > 1445 && minutes % 1440 <= 5) return `Days ${a.day + 1}–${a.day + Math.round(minutes / 1440)} (full days)`;
  return `Day ${a.day + 1} · ${DOW[a.dow]} ${hhmm(a.minute_of_day)}–${hhmm(b.minute_of_day)}${b.day > a.day && b.minute_of_day !== 0 ? ` (day ${b.day + 1})` : ""}`;
}

/**
 * Move to an hour of the episode from a chart. Hourly metrics exist for the whole episode but the 3D scene was
 * recorded only for some windows: inside one, playback jumps there; outside, only the chart cursor moves.
 * `hour` is absolute (hours since the start of the episode); `wholeDay` = the click came from a daily chart.
 */
export function scrubTo(hour: number, wholeDay: boolean) {
  const tick = Math.round(hour * 12);
  if (wholeDay) {
    const day0 = Math.floor(hour / 24) * 288;
    const w = transport.windows().find((x) => x.end >= day0 && x.start < day0 + 288);
    if (w && transport.seekTick(Math.max(w.start, Math.min(w.end, tick)), true)) return;
  } else if (transport.seekTick(tick)) return;
  useUI.setState({ chartCursor: hour });
}

/** Controls that say what the recording holds: its windows, the end of one, and a cursor outside them. */
export function RecordingNote({ f }: { f: FeedState }) {
  const windowEnd = useUI((s) => s.windowEnd);
  const chartCursor = useUI((s) => s.chartCursor);
  const tm = f.header?.tick_minutes ?? 5;
  if (f.origin === "live" || !f.segments.length) return null;
  const now = f.snap?.t ?? 0;
  const cur = f.segments.findIndex((w) => now >= w.start && now <= w.end);
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10.5px] text-ink-3" data-testid="recording-note">
      {chartCursor != null ? (
        <span className="rounded-md bg-[#FDF6E7] px-1.5 py-[2px] font-medium text-[#8A5A00]" data-testid="no-recording">
          No 3D recording for {`Day ${Math.floor(chartCursor / 24) + 1}, ${hhmm((Math.floor(chartCursor) % 24) * 60)}`}: the chart shows that hour, the scene stays where it was.
        </span>
      ) : windowEnd ? (
        <span className="flex items-center gap-1.5" data-testid="window-end">
          <span className="font-semibold text-ink-2">End of this recorded window.</span>
          {windowEnd.next && (
            <button className="btn-primary !h-6 !px-2 !text-[10.5px]" onClick={() => transport.nextWindow()} data-testid="next-window">
              Next recorded window
            </button>
          )}
          <button className="btn-quiet !h-6 !px-2 !text-[10.5px]" onClick={() => transport.replayWindow()} data-testid="replay-window">
            Replay
          </button>
          {!windowEnd.next && f.segments.length > 1 && (
            <button className="btn-quiet !h-6 !px-2 !text-[10.5px]" onClick={() => transport.nextWindow()}>
              First window
            </button>
          )}
        </span>
      ) : (
        <span>The 3D scene was recorded for {f.segments.length === 1 ? "one window" : `${f.segments.length} windows`} of this {f.header?.days ?? ""}-day run; the charts cover all of it.</span>
      )}
      <span className="flex flex-wrap items-center gap-1">
        {f.segments.slice(0, 8).map((w, i) => (
          <button key={i} onClick={() => transport.seekTick(w.start, true)} data-window={i} className={`rounded-full border px-2 py-[1px] font-semibold transition-colors ${i === cur && chartCursor == null ? "border-accent/40 bg-accent-soft text-accent-dark" : "border-line bg-white/70 text-ink-2 hover:border-accent/40"}`} title="Jump to this recorded window">
            {windowLabel(w, tm)}
          </button>
        ))}
        {f.segments.length > 8 && <span>+{f.segments.length - 8} more</span>}
      </span>
    </div>
  );
}

/** Whole-episode chart with a scrubber. Click or drag to jump to the nearest recorded snapshot. */
export function Timeline({ f, other, className = "" }: { f: FeedState; other?: FeedState; className?: string }) {
  const [metric, setMetric] = useState(CHART_METRICS[0]);
  const [zoom, setZoom] = useState<ChartZoom>("all");
  const values = f.hourly[metric.key] ?? [];
  const chartCursor = useUI((s) => s.chartCursor);
  const play = playheadHour(f);
  // the cursor is the playhead, unless it was moved to an hour that has no 3D recording
  const cur = chartCursor != null && f.origin !== "live" ? chartCursor - f.hour0 : play;
  const view = chartView([values.length, other?.hourly[metric.key]?.length ?? 0], f.hour0, cur, zoom);
  const series: Series[] = [{ name: shortManager(f.header?.manager) || "This run", color: SERIES[0], ...view.shape(values) }];
  if (other?.hourly[metric.key]) series.push({ name: shortManager(other.header?.manager) || "Other", color: SERIES[1], ...view.shape(other.hourly[metric.key]) });
  const curVal = cur != null ? values[Math.max(0, Math.min(values.length - 1, Math.floor(cur)))] : NaN;
  const seek = transport.canSeek();
  return (
    <div className={`glass pointer-events-auto w-full px-3.5 pb-2 pt-2.5 ${className}`} data-testid="timeline">
      <div className="mb-1 flex items-center gap-2">
        <div className="seg">
          {CHART_METRICS.map((m) => (
            <button key={m.key} data-on={m.key === metric.key} onClick={() => setMetric(m)}>
              {m.label}
            </button>
          ))}
        </div>
        <span className="tnum ml-1 whitespace-nowrap text-[13px] font-semibold text-ink">{metricValue(curVal, metric.unit)}</span>
        <span className="whitespace-nowrap text-[11px] text-ink-3">{metric.key === "cost_total" ? "per hour" : metric.key === "lwbs" ? "this hour" : ""}</span>
        <span className="ml-auto flex items-center gap-2 text-[10.5px] text-ink-3">
          {view.long && <ZoomToggle zoom={zoom} onZoom={setZoom} />}
          <SimTag>{f.origin === "fixture" ? "fixture" : "simulated"}</SimTag>
        </span>
      </div>
      {values.length ? (
        <LineChart
          series={series}
          unit={metric.unit}
          height={104}
          cursor={view.cursor}
          hour0={view.hour0}
          step={view.step}
          onScrub={seek ? (h) => scrubTo(h + view.offset + f.hour0, view.step === 24) : undefined}
          bands={f.segments.map((s) => ({ start: s.start / 12 - f.hour0 - view.offset, end: s.end / 12 - f.hour0 - view.offset }))}
          marks={view.step === 1 ? f.decisions.map((d) => d.t / 12 - f.hour0 - view.offset).filter((h) => h >= 0 && h <= WINDOW * 10) : []}
          showLegend={series.length > 1}
        />
      ) : (
        <div className="flex h-[104px] items-center justify-center text-[12px] text-ink-3">Hourly metrics appear here once the first simulated hour completes.</div>
      )}
      <RecordingNote f={f} />
      {view.long && (
        <div className="mt-0.5 text-[10px] text-ink-3">{view.step === 24 ? `One point per day: the day’s mean, shaded from its lowest to its highest hour.${f.segments.length ? " Shaded columns: recorded windows." : ""}` : "Hourly values in a 72-hour window around the playhead."}</div>
      )}
    </div>
  );
}
