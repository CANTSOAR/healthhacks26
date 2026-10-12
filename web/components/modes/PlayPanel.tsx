"use client";
import Link from "next/link";
import { useState } from "react";
import type { FeedState } from "@/lib/feed";
import { DOW, duration, hhmm, titleCase } from "@/lib/format";
import { playCtl, savedRun, startPlay } from "@/lib/session";
import { managerStory, prettyManager, shortManager } from "@/lib/story";
import { useUI } from "@/lib/ui";
import type { ActionHead, Cadence, Snapshot } from "@/lib/types";
import { Icon, ICONS, KindChip, SimTag, SourceChip } from "../ui/atoms";
import { HEAD_LABEL, optLabel } from "./labels";
import { DecisionFeed, SummaryGrid } from "./WatchPanel";

const CADENCES: { id: Cadence; label: string; when: string }[] = [
  { id: "hourly", label: "Hourly", when: "applies at the top of the next hour" },
  { id: "daily", label: "Daily", when: "sets the plan for the day that starts at 00:00" },
  { id: "weekly", label: "Weekly", when: "set on Monday 00:00" },
  { id: "monthly", label: "Monthly · structural", when: "set every 28 days; build delay and switching cost" },
];
const INJECT = [
  ["flu_surge", "Flu surge"],
  ["mass_casualty", "Mass casualty"],
  ["ct_outage", "CT outage"],
  ["rn_callouts", "Nurse call-outs"],
];

/** Minutes until the next boundary at which a head of this cadence takes effect (contracts/actions.yaml). */
export function minutesToBoundary(c: Cadence, clock: Snapshot["clock"]): number {
  const toHour = 60 - (clock.minute_of_day % 60);
  if (c === "hourly") return toHour;
  const toMidnight = 1440 - clock.minute_of_day;
  if (c === "daily") return toMidnight;
  if (c === "weekly") return toMidnight + ((7 - ((clock.dow + 1) % 7)) % 7) * 1440;
  const nextDay = clock.day + 1;
  return toMidnight + ((28 - (nextDay % 28)) % 28) * 1440;
}
function boundaryLabel(c: Cadence, clock: Snapshot["clock"]): string {
  const m = minutesToBoundary(c, clock);
  const abs = clock.day * 1440 + clock.minute_of_day + m;
  const day = Math.floor(abs / 1440);
  return `in ${duration(m)} · ${DOW[((day % 7) + 7) % 7]} ${hhmm(abs % 1440)}${c === "hourly" ? "" : `, day ${day + 1}`}`;
}

function optValue(h: ActionHead, i: number): string | null {
  const v = h.values?.[i];
  if (v == null) return null;
  // a bare index against a named policy option says nothing; staffing levels always show their quantity
  if (typeof v === "number" && v === i && !/^lvl\d+$/.test(h.options[i])) return null;
  if (typeof v === "number" || typeof v === "string") return String(v) === h.options[i] ? null : String(v);
  if (typeof v === "boolean") return v ? "on" : "off";
  if (typeof v === "object") return Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k} ${x}`).join(", ");
  return null;
}

function Knob({ h, f, disabled }: { h: ActionHead; f: FeedState; disabled: boolean }) {
  const requested = useUI((s) => s.play.requested[h.name]);
  const current = (f.snap?.kpis.settings?.[h.name] as number | undefined) ?? h.default;
  // live: the server's `pending` is the truth (applied values leave it). Offline there is no server, so show the request.
  const pending = f.origin === "live" ? f.pending[h.name] : requested;
  const queued = pending != null && pending !== current ? pending : null;
  const dense = h.options.length > 3;
  return (
    <div className="py-2" data-head={h.name}>
      <div className="mb-1 flex items-baseline gap-2">
        <span className="text-[12px] font-semibold text-ink" title={h.desc}>
          {HEAD_LABEL[h.name] ?? titleCase(h.name)}
        </span>
        {queued != null && (
          <span className="chip bg-[#FDEFD8] text-[#8A5A00]" title="Requested; applies at the next boundary for this cadence">
            queued: {optLabel(h.options[queued] ?? String(queued))}
          </span>
        )}
        {h.implemented === false && (
          <span className="chip bg-[#141a33]/[0.05] text-ink-3" title="The simulator accepts this setting but does not model its effect yet">
            not modeled yet
          </span>
        )}
      </div>
      <div className={`grid gap-1 ${dense ? "grid-cols-5" : h.options.length === 2 ? "grid-cols-2" : "grid-cols-3"}`} style={h.options.length === 4 ? { gridTemplateColumns: "repeat(4, minmax(0, 1fr))" } : undefined}>
        {h.options.map((o, i) => {
          const on = i === current;
          const q = i === queued;
          const v = optValue(h, i);
          return (
            <button
              key={o}
              disabled={disabled}
              onClick={() => playCtl.action(h.name, i)}
              title={`${optLabel(o)}${v ? ` = ${v}` : ""}${i === h.default ? " (baseline)" : ""}`}
              className={`flex min-h-[34px] min-w-0 flex-col items-center justify-center rounded-lg border px-1 py-1 text-center transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                on ? "border-accent bg-accent text-white" : q ? "border-[#E0A21B] bg-[#FDF6E7] text-ink" : "border-line bg-white/70 text-ink-2 hover:border-accent/40 hover:text-accent-dark"
              }`}
            >
              <span className="w-full truncate text-[10.5px] font-semibold leading-tight">{optLabel(o)}</span>
              {v && <span className={`tnum w-full truncate text-[10px] leading-tight ${on ? "text-white/80" : "text-ink-3"}`}>{v}</span>}
            </button>
          );
        })}
      </div>
      {h.desc && <div className="mt-1 text-[10.5px] leading-snug text-ink-3">{h.desc}</div>}
    </div>
  );
}

export function PlayPanel({ f, className = "" }: { f: FeedState; className?: string }) {
  const play = useUI((s) => s.play);
  const setPlay = useUI((s) => s.setPlay);
  const managers = useUI((s) => s.managers);
  const scenarioId = useUI((s) => s.scenarioId);
  const hasSaved = useUI((s) => s.hasSavedRun);
  const [open, setOpen] = useState<Record<string, boolean>>({ hourly: true, daily: true, weekly: false, monthly: false });
  const [tab, setTab] = useState<"knobs" | "log">("knobs");
  const running = play.state === "live" || play.state === "fixture";
  const spec = f.header?.action_spec ?? [];
  const clock = f.snap?.clock;
  const human = play.manager === "human";
  const inCharge = managers.find((m) => m.id === play.manager);
  // subscribed so the card fills in when the results table arrives
  const results = useUI((s) => s.results);
  const story = !human && running && results !== undefined ? managerStory(play.manager, f.header?.scenario ?? scenarioId) : "";

  return (
    <div className={`glass pointer-events-auto flex min-h-0 flex-col ${className}`} data-testid="play-panel">
      <div className="space-y-2.5 px-3.5 pb-3 pt-3.5">
        <div className="flex items-center gap-2">
          <span className="eyebrow">You are the manager</span>
          {play.state === "live" && <span className="chip bg-[#DFF5EA] text-[#11734B]">live simulation</span>}
          {play.state === "fixture" && <SourceChip tag="fixture" title="No simulator reachable: a recorded fixture is replayed instead" />}
          <span className="ml-auto">
            <SimTag />
          </span>
        </div>
        <div className="flex items-center gap-2">
          <select className="select min-w-0 flex-1" value={play.manager} onChange={(e) => playCtl.manager(e.target.value)} disabled={play.state === "fixture"} aria-label="Who is managing" data-testid="manager-select" title="Hand the hospital to a trained manager, or take it back">
            <option value="human">You (human)</option>
            {managers
              .filter((m) => m.kind !== "human")
              .map((m) => (
                <option key={m.id} value={m.id} disabled={m.available === false}>
                  Hand over: {shortManager(m)}
                </option>
              ))}
          </select>
          <label className="flex h-8 items-center gap-1.5 rounded-full border border-line bg-white/70 px-3 text-[12px] font-semibold text-ink-2" title="Random seed. Two runs with the same scenario and seed see the same patients.">
            seed
            <input type="number" value={play.seed} disabled={running} onChange={(e) => setPlay({ seed: Math.max(0, Math.round(+e.target.value || 0)) })} className="tnum w-10 bg-transparent text-ink outline-none disabled:opacity-60" aria-label="Seed" />
          </label>
        </div>
        {running && (
          <div className={`rounded-xl px-3 py-2 ${human ? "bg-[#141a33]/[0.035]" : "bg-accent-soft ring-1 ring-inset ring-accent/25"}`} data-testid="in-charge">
            <div className="flex items-center gap-2">
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="eyebrow shrink-0">In charge</span>
                  <KindChip kind={human ? "human" : (inCharge?.kind ?? f.header?.manager.kind ?? "learned")} />
                </span>
                <span className="mt-0.5 block text-[12px] font-semibold leading-snug text-ink" title={inCharge ? prettyManager(inCharge.label) : undefined} data-testid="in-charge-name">
                  {human ? "You" : inCharge ? shortManager(inCharge) : play.manager}
                </span>
              </span>
              {!human && (
                <button className="btn-quiet !h-7 shrink-0 !px-2.5 !text-[11px]" onClick={() => playCtl.manager("human")} data-testid="take-back">
                  Take back
                </button>
              )}
            </div>
            {story && (
              <div className="mt-1.5 text-[11px] leading-snug text-ink-2" data-testid="manager-story">
                {story}
              </div>
            )}
          </div>
        )}
        <div className="flex items-center gap-2">
          {!running ? (
            <>
              {hasSaved && play.state === "idle" && (
                <button className="btn-primary flex-1" onClick={() => { const r = savedRun(); if (r) void startPlay({ attach: r.run_id, select: r.selection ?? null }); }} data-testid="play-rejoin" title="Carry on with the run this tab started earlier">
                  Rejoin run
                </button>
              )}
              <button className={hasSaved && play.state === "idle" ? "btn-quiet flex-1" : "btn-primary flex-1"} onClick={() => void startPlay()} disabled={play.state === "connecting"} data-testid="play-start">
                <Icon d={ICONS.play} size={12} stroke={2.4} />
                {play.state === "connecting" ? "Connecting…" : play.state === "ended" || hasSaved ? "Start a new run" : `Start · ${titleCase(scenarioId)}`}
              </button>
            </>
          ) : (
            <>
              <button className="btn-quiet flex-1" onClick={() => void playCtl.stop()} data-testid="play-stop">
                End run and save
              </button>
            </>
          )}
        </div>
        {play.note && <div className="rounded-xl bg-[#FDF6E7] px-3 py-2 text-[11px] leading-snug text-[#8A5A00]">{play.note}</div>}
        {f.error && <div className="rounded-xl bg-[#FDE7E8] px-3 py-2 text-[11px] leading-snug text-[#B4232A]">{f.error}</div>}
        {play.state === "ended" && (
          <div className="rounded-xl bg-accent-soft px-3 py-2.5 text-[11px] leading-snug text-ink-2" data-testid="play-result">
            <div className="mb-1.5 font-semibold text-accent-dark">Run ended</div>
            <SummaryGrid summary={f.summary} />
            <div className="mt-1.5">
              {play.posted
                ? play.posted.where === "live"
                  ? "Saved to the server. "
                  : "Server unreachable: saved in this browser only. "
                : "No summary to save. "}
              <Link href="/?mode=tradeoff" className="font-semibold text-accent-dark underline underline-offset-2">
                See it on the trade-off chart
              </Link>
            </div>
          </div>
        )}
      </div>
      {running && (
        <>
          <div className="flex items-center gap-2 border-t border-line px-3.5 py-2">
            <div className="seg">
              <button data-on={tab === "knobs"} onClick={() => setTab("knobs")}>
                Controls
              </button>
              <button data-on={tab === "log"} onClick={() => setTab("log")}>
                Decisions
              </button>
            </div>
            <span className="ml-auto text-[10.5px] text-ink-3">{spec.length} action heads</span>
          </div>
          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-3.5 pb-3">
            {tab === "log" ? (
              <DecisionFeed f={f} />
            ) : (
              <>
                {CADENCES.map((c) => {
                  const heads = spec.filter((h) => h.cadence === c.id);
                  if (!heads.length) return null;
                  const isOpen = open[c.id];
                  return (
                    <section key={c.id} className="border-b border-line last:border-b-0" data-cadence={c.id}>
                      <button className="flex w-full items-center gap-2 py-2 text-left" onClick={() => setOpen((o) => ({ ...o, [c.id]: !o[c.id] }))} aria-expanded={isOpen}>
                        <span className={`text-ink-3 transition-transform ${isOpen ? "rotate-90" : ""}`}>
                          <Icon d={ICONS.chevron} size={12} stroke={2.4} />
                        </span>
                        <span className="text-[12px] font-semibold text-ink">{c.label}</span>
                        <span className="tnum text-[10.5px] text-ink-3">{heads.length}</span>
                        <span className="tnum ml-auto text-[10.5px] font-medium text-ink-2" title={c.when}>
                          {c.id !== "hourly" && heads.some((h) => f.mask[h.name]) ? "open now · " : ""}
                          {clock ? `next ${boundaryLabel(c.id, clock)}` : c.when}
                        </span>
                      </button>
                      {isOpen && (
                        <div className="pb-1">
                          {!human && <div className="mb-1 text-[10.5px] text-ink-3">Read-only while {inCharge ? shortManager(inCharge) : "another manager"} is in charge. Take back to change these yourself.</div>}
                          {heads.map((h) => (
                            <Knob key={h.name} h={h} f={f} disabled={!human} />
                          ))}
                        </div>
                      )}
                    </section>
                  );
                })}
                <div className="pt-3">
                  <div className="eyebrow mb-1.5">Throw something at it</div>
                  <div className="flex flex-wrap gap-1.5">
                    {INJECT.map(([id, label]) => (
                      <button key={id} className="btn-quiet !h-7 !px-2.5 !text-[11px]" onClick={() => playCtl.inject(id, label)} data-inject={id} disabled={play.state !== "live"} title={play.state !== "live" ? "Needs the live simulator" : `Inject ${label.toLowerCase()}`}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </>
      )}
      {!running && play.state !== "ended" && (
        <div className="border-t border-line px-3.5 py-3 text-[11.5px] leading-relaxed text-ink-3">
          Start a run to staff shifts, set policies and change the building. Hourly, daily, weekly and monthly decisions each take effect at their own boundary.
        </div>
      )}
    </div>
  );
}
