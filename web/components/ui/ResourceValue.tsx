"use client";
// "Value of this resource": what one unit of the selected entity's resource class is worth, from the paired
// with/without simulations of rl/attribution.py. Every number here is simulated.
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { entityValue, excludesZero, signed, signedUsd, statUsd, VERDICT, type AttributionReport, type AttrRankRow, type EntityValue } from "@/lib/attribution";
import type { FeedState } from "@/lib/feed";
import { pct, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { useUI } from "@/lib/ui";
import type { Selection } from "@/lib/types";
import { Bar, Chip, SimTag } from "./atoms";

function VerdictChip({ v }: { v?: string }) {
  if (!v) return null;
  const c = VERDICT[v] ?? { label: v, bg: "#ECEEF6", fg: "#4A5275", title: v };
  return (
    <Chip bg={c.bg} fg={c.fg} title={c.title}>
      {c.label}
    </Chip>
  );
}

/** Value by hour of day: bars from a zero line, the interval as a faint band, the current hour marked. */
export function HourSpark({ values, hw, now, height = 44 }: { values: number[]; hw?: number[]; now?: number; height?: number }) {
  const W = 240;
  const n = values.length || 24;
  const top = Math.max(1e-9, ...values.map((v, i) => Math.abs(v) + (hw?.[i] ?? 0)));
  const mid = height / 2;
  const y = (v: number) => mid - (v / top) * (mid - 3);
  const bw = W / n;
  return (
    <svg viewBox={`0 0 ${W} ${height + 12}`} className="block w-full" role="img" aria-label="Value of this unit by hour of day (simulated)" data-testid="value-spark">
      {[7, 15, 23].map((h) => (
        <line key={h} x1={h * bw} x2={h * bw} y1={0} y2={height} stroke="rgba(20,26,51,0.10)" strokeDasharray="2 3" />
      ))}
      {values.map((v, i) => {
        const e = hw?.[i] ?? 0;
        return (
          <g key={i}>
            {e > 0 && <rect x={i * bw + bw * 0.42} width={bw * 0.16} y={y(v + e)} height={Math.max(0.5, y(v - e) - y(v + e))} fill="rgba(20,26,51,0.22)" />}
            <rect x={i * bw + 1} width={bw - 2} y={Math.min(y(v), mid)} height={Math.max(0.6, Math.abs(y(v) - mid))} rx={1} fill={v >= 0 ? "#2F55F5" : "#C2410C"} opacity={i === now ? 1 : 0.5}>
              <title>{`${String(i).padStart(2, "0")}:00 · ${signedUsd(v)} per hour${e ? ` ± ${Math.round(e)}` : ""}`}</title>
            </rect>
          </g>
        );
      })}
      <line x1={0} x2={W} y1={mid} y2={mid} stroke="rgba(20,26,51,0.35)" />
      {now != null && <path d={`M${now * bw + bw / 2 - 3} ${height + 1}h6l-3 -4z`} fill="#141A33" />}
      {[0, 7, 15, 23].map((h) => (
        <text key={h} x={h * bw + 1} y={height + 11} fontSize={8} fill="#8089A8">
          {String(h).padStart(2, "0")}
        </text>
      ))}
    </svg>
  );
}

const cachedReport = new Map<string, Promise<{ data: AttributionReport | null; source: "live" | "fixture" }>>();
export function useAttribution(hospitalId: string | null | undefined) {
  // no report can mean "server not reachable yet": ask again a few times instead of remembering the miss
  const [attempt, setAttempt] = useState(0);
  const st = useApi<AttributionReport | null>(() => {
    if (!hospitalId) return Promise.resolve({ data: null, source: "live" as const });
    let p = cachedReport.get(hospitalId);
    if (!p) {
      p = api.attribution(hospitalId);
      cachedReport.set(hospitalId, p);
      void p.then((r) => r.data == null && cachedReport.delete(hospitalId), () => cachedReport.delete(hospitalId));
    }
    return p;
  }, [hospitalId, attempt]);
  const missing = !!hospitalId && !st.loading && st.data == null && attempt < 4;
  useEffect(() => {
    if (!missing) return;
    const t = setTimeout(() => setAttempt((n) => n + 1), 9000);
    return () => clearTimeout(t);
  }, [missing, attempt]);
  return st;
}

/** Inspector block. `server` is the `attribution` field of a live entity payload when the server sent one. */
export function ResourceValue({ sel, f, server }: { sel: Selection; f: FeedState; server?: EntityValue | null }) {
  const hospitalId = f.header?.hospital_id ?? f.layout?.hospital_id ?? null;
  const rep = useAttribution(sel.kind === "patient" || sel.kind === "ambulance" ? null : hospitalId);
  const local = useMemo(() => entityValue(rep.data, sel, f), [rep.data, sel, f]);
  // the server's block carries the live utilisation; it is used only while it describes the same resource unit
  const v = server && (!local || server.unit === local.unit || !server.available) ? { ...local, ...server } : local;
  if (!v) return null;
  const what = (v.unit_label ?? v.label ?? "resource").replace(/^one /, "").replace(/ \(.*$/, "");
  if (!v.available) {
    return (
      <div className="mt-3 border-t border-line pt-3" data-testid="resource-value">
        <div className="mb-1 flex items-center gap-2">
          <span className="eyebrow">Value of this role</span>
          <SimTag>simulated</SimTag>
        </div>
        <div className="text-[11px] leading-snug text-ink-3">{v.reason}</div>
      </div>
    );
  }
  // headline: the unit's effect on the objective (in dollars of cost at the objective's own exchange rate); margin alone is second
  const val = v.reward_value_per_day ?? null;
  const net = v.net_value_per_day;
  const head = val ?? net ?? null;
  const sig = excludesZero(head);
  const un = v.utilisation_now;
  const ut = v.utilisation_typical;
  const hourly = v.by_hour?.reward_value ? { values: v.by_hour.reward_value, hw: v.by_hour.reward_value_hw, now: v.now?.reward_value_per_hour } : v.by_hour ? { values: v.by_hour.margin, hw: v.by_hour.margin_hw, now: v.now?.margin_per_hour } : null;
  return (
    <div className="mt-3 border-t border-line pt-3" data-testid="resource-value">
      <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="eyebrow">Value of this {what}</span>
        <SimTag>simulated</SimTag>
        <VerdictChip v={v.verdict} />
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[12px] text-ink-3">{val ? (v.existing ? "Value to the objective, per day" : "Value to the objective if added, per day") : v.existing ? "Margin per day" : "Margin per day if added"}</span>
        <span className="tnum text-right text-[15px] font-semibold text-ink" data-testid="resource-net">
          {head ? signedUsd(head.mean) : "–"}
        </span>
      </div>
      <div className="tnum text-right text-[11px] text-ink-3">
        {head && head.lo != null && head.hi != null ? `95% interval ${signedUsd(head.lo)} to ${signedUsd(head.hi)}` : ""}
        {head && !sig ? " · not distinguishable from zero" : ""}
      </div>
      {val && (
        <div className="mt-0.5 text-[11px] leading-snug text-ink-3">
          Its effect on the balanced objective (cost, revenue, waiting, walk-outs, safety, boarding, staff strain), converted to dollars of daily cost at the objective&rsquo;s own exchange rate. A valuation set by the weights, not cash. Its cost of {signedUsd(v.unit_cost_per_day ?? 0).replace("+", "")} a day is already taken off{(v.n_units ?? 1) > 1 ? ` (${v.n_units} units together)` : ""}.
        </div>
      )}
      {val && net && (
        <div className="mt-2 flex items-baseline justify-between gap-3 text-[12px]" title={`Cash margin ${v.existing ? "the hospital would lose without it" : "gained by adding it"}, its own cost taken off. Counts no harm to patients.`}>
          <span className="text-ink-3">Margin alone</span>
          <span className={`tnum text-right font-medium ${excludesZero(net) ? "text-ink" : "text-ink-3"}`}>
            {statUsd(net)} / day
          </span>
        </div>
      )}
      {hourly?.now && (
        <div className="mt-2 flex items-baseline justify-between gap-3 text-[12px]">
          <span className="text-ink-3">At this hour ({String(v.now!.hour).padStart(2, "0")}:00)</span>
          <span className="tnum font-medium text-ink">
            {signedUsd(hourly.now.mean)} / h<span className="ml-1 text-[11px] text-ink-3">± {Math.round(hourly.now.hw).toLocaleString("en-US")}</span>
          </span>
        </div>
      )}
      {hourly && (
        <div className="mt-1">
          <HourSpark values={hourly.values} hw={hourly.hw} now={v.now?.hour} />
          <div className="text-[10px] leading-snug text-ink-3">Value by hour of day, $-equivalent per hour; thin bars are 95% intervals; dashed lines are shift changes.</div>
        </div>
      )}
      {(un?.value != null || ut) && (
        <div className="mt-2">
          <div className="flex items-baseline justify-between gap-3 text-[12px]">
            <span className="text-ink-3">{un?.value != null ? "In use now" : "Typically in use at this hour"}</span>
            <span className="tnum font-medium text-ink">
              {pct(un?.value ?? ut!.at_hour)}
              {un?.of != null && un.in_use != null ? <span className="ml-1 text-[11px] text-ink-3">{`${un.in_use} of ${un.of}`}</span> : null}
            </span>
          </div>
          <Bar value={un?.value ?? ut!.at_hour} />
          <div className="mt-0.5 text-[10px] leading-snug text-ink-3">
            {un?.value != null ? `${titleCase(un.basis)}. ` : ""}
            {ut ? `Baseline average ${pct(ut.mean)}; every unit busy in ${pct(ut.full_share)} of hours.` : ""}
          </div>
        </div>
      )}
      {v.flow_index_pct && (
        <div className="mt-2 flex items-baseline justify-between gap-3 text-[12px]" title="Door-to-provider wait, median ED stay, walk-out rate and boarding, each as a share of its baseline. No money in it.">
          <span className="text-ink-3">Patient flow {v.existing ? "without it" : "with it"}</span>
          <span className={`tnum text-right font-medium ${excludesZero(v.flow_index_pct) ? (v.flow_index_pct.mean > 0 ? "text-[#B4232A]" : "text-[#11734B]") : "text-ink-3"}`}>
            {signed(v.flow_index_pct.mean)}% {v.flow_index_pct.mean > 0 ? "worse" : v.flow_index_pct.mean < 0 ? "better" : ""}
            {excludesZero(v.flow_index_pct) ? "" : " (n.s.)"}
          </span>
        </div>
      )}
      {v.top_effects && v.top_effects.length > 0 && (
        <div className="mt-2">
          <div className="text-[11px] font-semibold text-ink-2">Largest effects of {v.effects_of}</div>
          {v.top_effects.map((e) => (
            <div key={e.metric} className="flex items-baseline justify-between gap-3 py-[2px] text-[11.5px]">
              <span className="min-w-0 text-ink-3">{e.label}</span>
              <span className={`tnum shrink-0 text-right font-medium ${e.significant ? (e.direction === "worse" ? "text-[#B4232A]" : "text-[#11734B]") : "text-ink-3"}`} title={e.lo != null && e.hi != null ? `95% interval ${signed(e.lo)} to ${signed(e.hi)} ${e.unit}` : undefined}>
                {signed(e.delta, e.unit)}
                {e.significant ? "" : " (n.s.)"}
              </span>
            </div>
          ))}
        </div>
      )}
      {v.next_unit && (
        <div className="mt-2 flex items-baseline justify-between gap-3 text-[11.5px]">
          <span className="text-ink-3">One more would add</span>
          <span className="tnum text-right font-medium text-ink">{statUsd(v.next_unit.reward_value_per_day ?? v.next_unit.net_value_per_day)} / day</span>
        </div>
      )}
      {v.location && (
        <div className="mt-1 text-[10.5px] leading-snug text-ink-3">
          This space is {Math.abs(v.location.vs_class_waiting_m)} m {v.location.vs_class_waiting_m <= 0 ? "nearer to" : "farther from"} the waiting room than the center of its class (about {Math.abs(v.location.walk_seconds_vs_class)} s per patient). The model does not use per-bay distances, so this is not in the value above.
        </div>
      )}
      <div className="mt-2 rounded-xl bg-[#141a33]/[0.035] px-2.5 py-2 text-[10.5px] leading-snug text-ink-3">
        {v.note ? `${v.note} ` : ""}
        Simulated: the twin run with and without {v.existing ? "this unit" : "it"} on the same {v.protocol?.n_seeds ?? ""} sets of simulated patients for {v.protocol?.days ?? ""} days ({titleCase(v.scenario ?? "")}), under current-practice staffing. Not the hospital&rsquo;s data.
      </div>
    </div>
  );
}

const KIND_LABEL: Record<string, string> = { staff: "Staff", space: "Space", equipment: "Equipment" };

/** Every resource unit ranked by net value per dollar, with the binding constraint and the slack called out. */
export function ResourceTable({ scenario, narrow }: { scenario: string; narrow: boolean }) {
  const hospitalId = useUI((s) => s.hospitalId);
  const { data: rep, loading } = useAttribution(hospitalId);
  const [open, setOpen] = useState<string | null>(null);
  if (loading) return <div className="flex h-full items-center justify-center text-[12px] text-ink-3">Loading resource values…</div>;
  const sc = rep && rep.protocol.scenarios.includes(scenario) ? scenario : rep?.protocol.scenarios[0];
  const rows: AttrRankRow[] = (rep && sc && rep.ranking[sc]) || [];
  if (!rep || !sc || !rows.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-1 px-6 text-center text-[12px] text-ink-3" data-testid="resources-empty">
        <div className="text-[13px] font-semibold text-ink-2">No resource values to show</div>
        <div>The server is unreachable or has no resource report for this hospital yet.</div>
      </div>
    );
  }
  const f = rep.findings[sc];
  const unitOf = (id: string) => rep.units.find((u) => u.id === id);
  const cs = rep.reward.cost_scale_per_hour ?? rep.reward.scales?.cost ?? 0;
  return (
    <div className="flex h-full min-h-0 flex-col" data-testid="resources">
      <div className="grid gap-2 text-[11.5px] leading-snug text-ink-2" style={{ gridTemplateColumns: narrow ? "1fr" : "1fr 1fr 1fr" }}>
        <div className="rounded-xl bg-[#DFF5EA]/60 px-3 py-2" data-testid="resources-binding">
          <div className="eyebrow !text-[#11734B]">Add first</div>
          {f.binding ? (
            <>
              <span className="font-semibold text-ink">{f.binding.label}.</span> Worth {statUsd(f.binding.reward_value_per_day ?? f.binding.net_value_per_day)} a day to the objective.
              {f.worth_adding.length > 1 ? ` Also: ${f.worth_adding.slice(1, 4).map((x) => x.label.toLowerCase()).join("; ")}.` : ""}
            </>
          ) : (
            "No single added unit raises the balanced reward with an interval above zero."
          )}
        </div>
        <div className="rounded-xl bg-[#E3E9FF]/60 px-3 py-2" data-testid="resources-slack">
          <div className="eyebrow !text-[#1F3FD1]">Could go with no measurable harm</div>
          {f.slack.length ? f.slack.slice(0, 5).map((x) => `${x.label} (${statUsd(x.margin_per_day)} a day)`).join("; ") + "." : "Nothing can be called slack at this sample size."}
        </div>
        <div className="rounded-xl bg-[#141a33]/[0.035] px-3 py-2">
          <div className="eyebrow">How it was measured</div>
          The twin run with and without one unit on the same {rep.protocol.n_seeds} sets of fresh simulated patients, {rep.protocol.days} days each, under current-practice staffing. Brackets are 95% intervals of the paired difference.
        </div>
      </div>
      <div className="scroll-thin mt-2 min-h-0 flex-1 overflow-auto">
        <table className="w-full border-separate border-spacing-0 text-[11.5px]" data-testid="resources-table">
          <thead className="sticky top-0 z-[1] bg-white/95">
            <tr className="text-left text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-3">
              <th className="pb-1.5 pl-1 font-semibold">Resource (one unit)</th>
              <th className="pb-1.5 text-right font-semibold">Costs / day</th>
              <th className="pb-1.5 text-right font-semibold" title="The unit's effect on the balanced objective in dollars of daily cost at the objective's own exchange rate, its own cost taken off">Value to the objective / day [95%]</th>
              <th className="pb-1.5 text-right font-semibold">Per $</th>
              <th className="pb-1.5 text-right font-semibold" title="Cash margin the hospital would lose per day without the unit, its own cost taken off. Counts no harm to patients.">Margin alone</th>
              <th className="pb-1.5 text-right font-semibold" title="Change in the patient-flow index (wait, stay, walk-outs, boarding; no money) when one is removed. Positive = worse.">Flow if removed</th>
              <th className="pb-1.5 pl-3 font-semibold">If removed</th>
              <th className="pb-1.5 pl-3 font-semibold">Largest effects of removing it</th>
              <th className="pb-1.5 text-right font-semibold">One more / day [95%]</th>
              <th className="pb-1.5 pl-3 pr-1 font-semibold">If added</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const ex = r.existing;
              const u = unitOf(r.unit);
              const on = open === r.unit;
              const side = u?.scenarios[sc]?.minus_one ?? u?.scenarios[sc]?.plus_one;
              return [
                <tr key={r.unit} data-row={r.unit} className={`cursor-pointer align-top ${on ? "bg-accent-soft" : "hover:bg-white"}`} onClick={() => setOpen(on ? null : r.unit)}>
                  <td className="rounded-l-lg border-t border-line py-1.5 pl-1 pr-2">
                    <span className="block font-semibold leading-tight text-ink">{r.label}</span>
                    <span className="block text-[10px] text-ink-3">{KIND_LABEL[r.kind] ?? r.kind}</span>
                  </td>
                  <td className="tnum border-t border-line py-1.5 text-right text-ink">{signedUsd(r.unit_cost_per_day).replace("+", "")}</td>
                  <td className={`tnum border-t border-line py-1.5 text-right ${excludesZero(ex?.reward_value_per_day) ? "font-semibold text-ink" : "text-ink-3"}`}>{ex ? statUsd(ex.reward_value_per_day ?? ex.net_value_per_day) : "not in use"}</td>
                  <td className="tnum border-t border-line py-1.5 text-right text-ink">{ex?.reward_value_per_dollar ? signed(ex.reward_value_per_dollar.mean) : "–"}</td>
                  <td className={`tnum border-t border-line py-1.5 text-right ${excludesZero(ex?.net_value_per_day) ? "text-ink" : "text-ink-3"}`}>{ex ? signedUsd(ex.net_value_per_day.mean) : "–"}</td>
                  <td className={`tnum border-t border-line py-1.5 text-right ${excludesZero(ex?.flow_index_pct) ? ((ex?.flow_index_pct?.mean ?? 0) > 0 ? "font-semibold text-[#B4232A]" : "text-[#11734B]") : "text-ink-3"}`}>
                    {ex?.flow_index_pct ? `${signed(ex.flow_index_pct.mean)}%` : "–"}
                  </td>
                  <td className="border-t border-line py-1.5 pl-3">
                    <VerdictChip v={ex?.verdict} />
                  </td>
                  <td className="border-t border-line py-1.5 pl-3 text-[11px] leading-snug text-ink-2">
                    {(ex?.top_effects ?? []).filter((e) => e.significant).map((e) => `${e.label} ${signed(e.delta, e.unit)}`).join("; ") || (ex ? "none outside the intervals" : "")}
                  </td>
                  <td className={`tnum border-t border-line py-1.5 text-right ${excludesZero(r.next?.reward_value_per_day) ? "text-ink" : "text-ink-3"}`}>{r.next ? statUsd(r.next.reward_value_per_day ?? r.next.net_value_per_day) : "–"}</td>
                  <td className="rounded-r-lg border-t border-line py-1.5 pl-3 pr-1">
                    <VerdictChip v={r.next?.verdict} />
                  </td>
                </tr>,
                on && u && side ? (
                  <tr key={`${r.unit}-detail`}>
                    <td colSpan={10} className="pb-3 pl-1 pr-1">
                      <div className={`grid gap-4 rounded-xl bg-[#141a33]/[0.035] p-3 ${narrow ? "" : "grid-cols-[280px_1fr]"}`}>
                        <div>
                          <div className="text-[11px] font-semibold text-ink-2">{ex ? "Value to the objective by hour of day" : "Value by hour of day if added"}</div>
                          <HourSpark values={side.by_hour.reward.mean.map((x) => (ex ? -x : x) * cs)} hw={side.by_hour.reward.hw.map((x) => x * cs)} />
                          <div className="text-[10px] text-ink-3">$-equivalent per hour; thin bars are 95% intervals; dashed lines are shift changes.</div>
                        </div>
                        <div className="text-[11px] leading-snug text-ink-2">
                          <div>{u.unit_label}. {side.description ? `Tested as: ${side.description}.` : ""}</div>
                          <div className="mt-1 text-ink-3">Cost basis: {u.cost_basis}.</div>
                          {u.utilisation?.[sc] ? (
                            <div className="mt-1 text-ink-3">
                              In use {pct(u.utilisation[sc]!.mean)} of the time at baseline; every unit busy in {pct(u.utilisation[sc]!.full_share)} of hours.
                            </div>
                          ) : null}
                          <div className="mt-1 text-ink-3">
                            Balanced reward if removed: {ex ? `${signed(ex.reward.mean)} per hour [${signed(ex.reward.lo ?? 0)}, ${signed(ex.reward.hi ?? 0)}]` : "–"}
                            {r.next ? ` · if one is added: ${signed(r.next.reward.mean)} [${signed(r.next.reward.lo ?? 0)}, ${signed(r.next.reward.hi ?? 0)}]` : ""}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : null,
              ];
            })}
          </tbody>
        </table>
        {f.revenue_rises_when_removed && f.revenue_rises_when_removed.length > 0 && (
          <div className="mt-2 rounded-xl bg-[#FDF6E7] px-3 py-2 text-[11px] leading-snug text-[#8A5A00]" data-testid="resources-caveat">
            Read the money columns with care for {f.revenue_rises_when_removed.map((x) => x.label.toLowerCase()).join("; ")}: the model&rsquo;s revenue rises when the unit is removed although patient flow gets measurably worse, because slower care ends in more admissions and the model books revenue per admission. That is a property of the cost model, not evidence that the unit loses money. The flow column is the one to act on for these rows.
          </div>
        )}
        <div className="mt-2 text-[10.5px] leading-snug text-ink-3">
          Simulated. Value to the objective = the unit&rsquo;s effect on the balanced objective (cost, revenue, waiting, walk-outs, safety, boarding, staff strain), with the unit against without it, in dollars of daily cost at the objective&rsquo;s own exchange rate; its running cost is already taken off, and it is a valuation set by the chosen weights, not cash. Margin alone is the cash figure and counts no harm. Capital cost (buying a scanner, building a bay) is not included. {f.rule} Staff of a role and bays of a class are interchangeable in the model, so these are values of a unit, not of a named person or room.
        </div>
      </div>
    </div>
  );
}
