"use client";
import { useState } from "react";
import type { FeedState } from "@/lib/feed";
import { metricValue } from "@/lib/format";
import { SERIES } from "@/lib/palette";
import { transport } from "@/lib/session";
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

/** Whole-episode chart with a scrubber. Click or drag to jump to the nearest recorded snapshot. */
export function Timeline({ f, other, className = "" }: { f: FeedState; other?: FeedState; className?: string }) {
  const [metric, setMetric] = useState(CHART_METRICS[0]);
  const [zoom, setZoom] = useState<ChartZoom>("all");
  const values = f.hourly[metric.key] ?? [];
  const cur = playheadHour(f);
  const view = chartView([values.length, other?.hourly[metric.key]?.length ?? 0], f.hour0, cur, zoom);
  const series: Series[] = [{ name: f.header?.manager.label ?? "This run", color: SERIES[0], ...view.shape(values) }];
  if (other?.hourly[metric.key]) series.push({ name: other.header?.manager.label ?? "Other", color: SERIES[1], ...view.shape(other.hourly[metric.key]) });
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
        <span className="whitespace-nowrap text-[11px] text-ink-3 max-[1500px]:hidden">this hour</span>
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
          onScrub={seek ? (h) => transport.seekTick(Math.round((h + view.offset + f.hour0) * 12)) : undefined}
          bands={f.segments.map((s) => ({ start: s.start / 12 - f.hour0 - view.offset, end: s.end / 12 - f.hour0 - view.offset }))}
          marks={view.step === 1 ? f.decisions.map((d) => d.t / 12 - f.hour0 - view.offset).filter((h) => h >= 0 && h <= WINDOW * 10) : []}
          showLegend={series.length > 1}
        />
      ) : (
        <div className="flex h-[104px] items-center justify-center text-[12px] text-ink-3">Hourly metrics appear here once the first simulated hour completes.</div>
      )}
      {view.long && (
        <div className="-mt-0.5 text-[10px] text-ink-3">{view.step === 24 ? `One point per day: the day’s mean, shaded from its lowest to its highest hour.${f.segments.length ? " Shaded columns: days with recorded snapshots." : ""}` : "Hourly values in a 72-hour window around the playhead."}</div>
      )}
    </div>
  );
}
