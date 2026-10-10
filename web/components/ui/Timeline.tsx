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

/** Whole-episode hourly chart with a scrubber. Click or drag to jump to the nearest recorded snapshot. */
export function Timeline({ f, other, className = "" }: { f: FeedState; other?: FeedState; className?: string }) {
  const [metric, setMetric] = useState(CHART_METRICS[0]);
  const values = f.hourly[metric.key] ?? [];
  const series: Series[] = [{ name: f.header?.manager.label ?? "This run", color: SERIES[0], values }];
  if (other?.hourly[metric.key]) series.push({ name: other.header?.manager.label ?? "Other", color: SERIES[1], values: other.hourly[metric.key] });
  const cur = playheadHour(f);
  const curVal = cur != null ? values[Math.min(values.length - 1, Math.floor(cur))] : NaN;
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
          {f.segments.length > 0 && (
            <span className="flex items-center gap-1 whitespace-nowrap max-[1500px]:hidden">
              <span className="h-2.5 w-3 rounded-sm bg-accent/15" /> snapshots recorded
            </span>
          )}
          <SimTag>{f.origin === "fixture" ? "fixture" : "simulated"}</SimTag>
        </span>
      </div>
      {values.length ? (
        <LineChart
          series={series}
          unit={metric.unit}
          height={104}
          cursor={cur}
          hour0={f.hour0}
          onScrub={seek ? (h) => transport.seekTick(Math.round((h + f.hour0) * 12)) : undefined}
          bands={f.segments.map((s) => ({ start: s.start / 12 - f.hour0, end: s.end / 12 - f.hour0 }))}
          marks={f.decisions.map((d) => d.t / 12 - f.hour0).filter((h) => h >= 0)}
          showLegend={series.length > 1}
        />
      ) : (
        <div className="flex h-[104px] items-center justify-center text-[12px] text-ink-3">Hourly metrics appear here once the first simulated hour completes.</div>
      )}
    </div>
  );
}
