"use client";
import type { FeedState } from "@/lib/feed";
import { metricValue, tickLabelLong, titleCase } from "@/lib/format";
import { managerStory, objectiveWords, prettyManager, shortManager } from "@/lib/story";
import { HEAD_LABEL, optLabel } from "./labels";
import { eventText, openWatch } from "@/lib/session";
import { useUI } from "@/lib/ui";
import type { RolloutListItem } from "@/lib/types";
import { KindChip, SimTag, SourceChip } from "../ui/atoms";

const CADENCE_STYLE: Record<string, [string, string]> = {
  hourly: ["#ECEEF6", "#4A5275"],
  daily: ["#E3E9FF", "#1F3FD1"],
  weekly: ["#E8F6EF", "#11734B"],
  monthly: ["#FDEFD8", "#8A5A00"],
};

const ROUTINE = new Set(["lwbs", "deterioration", "callout", "info"]);

export const rolloutLabel = (r: RolloutListItem) => `${shortManager(r.manager)} · ${titleCase(r.scenario)} · seed ${r.seed}`;

/** The server writes decisions as "md_night: lvl2 -> lvl0" and events as "Scenario event started: flu_wave": say them in words. */
export function plainText(text: string): string {
  const m = /^([a-z0-9_]+): (\S+) -> (\S+)$/.exec(text);
  if (m) return `${HEAD_LABEL[m[1]] ?? titleCase(m[1])}: ${optLabel(m[2])} → ${optLabel(m[3])}`;
  return eventText(text);
}

export function RolloutPicker({ value, onChange, testid }: { value: string | null; onChange: (id: string) => void; testid?: string }) {
  const rollouts = useUI((s) => s.rollouts);
  return (
    <select className="select w-full" value={value ?? ""} onChange={(e) => onChange(e.target.value)} aria-label="Recorded rollout" data-testid={testid}>
      {rollouts.length === 0 && <option value="">No recorded rollouts</option>}
      {rollouts.map((r) => (
        <option key={r.rollout_id} value={r.rollout_id} disabled={!r.has_segments} title={prettyManager(r.manager.label)}>
          {rolloutLabel(r)}
          {r.has_segments ? "" : " (charts only)"}
        </option>
      ))}
    </select>
  );
}

const SUMMARY: [string, string, string][] = [
  ["wait_mean_min", "Mean wait", "minutes"],
  ["wait_p95_min", "95th pct wait", "minutes"],
  ["lwbs_rate", "LWBS", "fraction"],
  ["cost_per_day", "Cost / day", "usd"],
  ["margin_per_day", "Margin / day", "usd"],
  ["ed_los_median_min", "Median ED stay", "minutes"],
];

export function SummaryGrid({ summary }: { summary: Record<string, number> | null | undefined }) {
  if (!summary) return null;
  const items = SUMMARY.filter(([k]) => summary[k] != null);
  if (!items.length) return null;
  return (
    <div className="grid grid-cols-3 gap-x-3 gap-y-2">
      {items.map(([k, label, unit]) => (
        <div key={k} className="min-w-0">
          <div className="truncate text-[10.5px] text-ink-3">{label}</div>
          <div className="tnum truncate text-[13px] font-semibold text-ink">{metricValue(summary[k], unit)}</div>
        </div>
      ))}
    </div>
  );
}

/** Decisions surfaced as they happen: everything the manager changed up to the playhead, newest first. */
export function DecisionFeed({ f, limit = 40 }: { f: FeedState; limit?: number }) {
  const now = f.snap?.t ?? 0;
  const tm = f.header?.tick_minutes ?? 5;
  const past = f.decisions.filter((d) => d.t <= now);
  const upcoming = f.decisions.find((d) => d.t > now);
  const seen = f.events.filter((e) => e.t <= now);
  // routine events (a patient leaving, a call-out) would bury the rest: keep only the latest few of those
  const events = [...seen.filter((e) => !ROUTINE.has(e.kind)).slice(-30), ...seen.filter((e) => ROUTINE.has(e.kind)).slice(-4)];
  const items = [
    ...past.map((d) => ({ t: d.t, kind: "decision" as const, text: plainText(d.label), cadence: d.cadence })),
    ...events.map((e) => ({ t: e.t, kind: "event" as const, text: plainText(e.text), cadence: titleCase(e.kind) })),
  ]
    .sort((a, b) => b.t - a.t)
    .slice(0, limit);
  return (
    <div data-testid="decision-feed">
      {items.length === 0 && (
        <div className="rounded-xl bg-[#141a33]/[0.035] px-3 py-3 text-[12px] leading-snug text-ink-3">
          No decisions yet at this point in the run.
          {upcoming ? ` Next: ${tickLabelLong(upcoming.t, tm)}.` : ""}
        </div>
      )}
      <ol className="space-y-1.5">
        {items.map((d, i) => {
          const fresh = now - d.t < 12;
          const [bg, fg] = d.kind === "decision" ? (CADENCE_STYLE[d.cadence] ?? CADENCE_STYLE.hourly) : ROUTINE.has(d.cadence.toLowerCase().replace(/ /g, "_")) ? ["#ECEEF6", "#4A5275"] : ["#FDE7E8", "#B4232A"];
          return (
            <li key={`${d.t}-${i}`} className={`rounded-xl px-3 py-2 ${fresh ? "bg-accent-soft ring-1 ring-inset ring-accent/25" : "bg-white/60"} ${i === 0 ? "rise" : ""}`}>
              <div className="flex items-center gap-2">
                <span className="tnum text-[10.5px] font-medium text-ink-3">{tickLabelLong(d.t, tm)}</span>
                <span className="chip ml-auto" style={{ background: bg, color: fg }}>
                  {d.cadence}
                </span>
              </div>
              <div className="mt-0.5 text-[12px] font-semibold leading-snug text-ink">{d.text}</div>
            </li>
          );
        })}
      </ol>
      {items.length > 0 && upcoming && <div className="mt-2 px-1 text-[11px] text-ink-3">Next decision at {tickLabelLong(upcoming.t, tm)}.</div>}
    </div>
  );
}

export function WatchPanel({ f, className = "" }: { f: FeedState; className?: string }) {
  const watchId = useUI((s) => s.watchId);
  const loading = useUI((s) => s.loading);
  useUI((s) => s.results); // the story is composed from the results table: re-render when it arrives
  const h = f.header;
  const goal = h ? objectiveWords(h.manager) : "";
  return (
    <div className={`glass pointer-events-auto flex min-h-0 flex-col ${className}`} data-testid="watch-panel">
      <div className="space-y-2.5 px-3.5 pb-3 pt-3.5">
        <div className="flex items-center gap-2">
          <span className="eyebrow">Watching</span>
          {h && <KindChip kind={h.manager.kind} />}
          {f.origin === "fixture" && <SourceChip tag="fixture" title="Bundled placeholder rollout, shown because the server is unreachable. Not a simulator run." />}
          <span className="ml-auto">
            <SimTag />
          </span>
        </div>
        <RolloutPicker value={watchId} onChange={(id) => void openWatch(id)} testid="rollout-picker" />
        {h && managerStory(h.manager.id, h.scenario) && (
          <div className="rounded-xl bg-[#141a33]/[0.035] px-3 py-2 text-[11px] leading-snug text-ink-2" data-testid="manager-story">
            {managerStory(h.manager.id, h.scenario)}
          </div>
        )}
        {h && (
          <div className="text-[11px] leading-snug text-ink-3">
            {goal ? `Objective: ${goal} · ` : ""}
            {titleCase(h.scenario)} · seed {h.seed} · {h.days} {h.days === 1 ? "day" : "days"}
            {loading ? ` · ${loading}` : ""}
          </div>
        )}
        <SummaryGrid summary={f.summary} />
      </div>
      <div className="flex items-center gap-2 border-t border-line px-3.5 pb-1.5 pt-2.5">
        <span className="eyebrow">{f.decisions.length ? "Manager decisions and events" : "Events"}</span>
        <span className="tnum ml-auto text-[10.5px] text-ink-3">
          {f.decisions.length ? `${f.decisions.filter((d) => d.t <= (f.snap?.t ?? 0)).length} of ${f.decisions.length} decisions` : "this manager never changes a setting"}
        </span>
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-2.5 pb-2.5">
        <DecisionFeed f={f} />
      </div>
    </div>
  );
}
