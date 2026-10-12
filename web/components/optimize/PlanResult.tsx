"use client";
import { useState } from "react";
import {
  dirWord,
  lowerFirst,
  parseStamp,
  epLabel,
  epUnit,
  epValue,
  meanPeople,
  METRIC_PARTS,
  readingFor,
  SAME_AS,
  scenarioLabel,
  signedPct,
  splitLabel,
  verdictFor,
  type GuardrailRow,
  type JobListItem,
  type MetricRow,
  type ObjectiveGoal,
  type OptJob,
  type OptResult,
  type ScenarioResult,
  type StaffingHead,
  type Verdict, wantsDown } from "@/lib/optimize";
import { num } from "@/lib/format";
import { SearchCharts } from "./SearchProgress";

const TONE = {
  good: { bg: "#DFF5EA", fg: "#11734B", bar: "#1BAF7A" },
  bad: { bg: "#FDE7E8", fg: "#B4232A", bar: "#E5484D" },
  flat: { bg: "#ECEEF6", fg: "#4A5275", bar: "#8089A8" },
};
const VERDICT: Record<Verdict, { text: string; tone: keyof typeof TONE }> = {
  asked: { text: "Moved the way you asked", tone: "good" },
  flat: { text: "No significant change", tone: "flat" },
  against: { text: "Moved against what you asked", tone: "bad" },
};

/** The percent change with its 95% interval, on an axis centered on "no change". */
function IntervalBar({ row, tone }: { row: MetricRow; tone: keyof typeof TONE }) {
  if (row.pct == null || !row.pct_ci95) return <div className="h-[30px] text-[11px] leading-[30px] text-ink-3">No percentage: current practice is zero here.</div>;
  const [lo, hi] = row.pct_ci95;
  const span = Math.max(Math.abs(lo), Math.abs(hi), Math.abs(row.pct), 1) * 1.15;
  const x = (v: number) => 50 + (Math.max(-span, Math.min(span, v)) / span) * 50;
  const c = TONE[tone];
  return (
    <div title={`95% interval ${signedPct(lo)} to ${signedPct(hi)}`}>
      <div className="relative h-[14px]">
        <span className="absolute top-1/2 h-px w-full -translate-y-1/2 bg-[#141a33]/[0.12]" />
        <span className="absolute top-0 h-full w-px bg-[#141a33]/40" style={{ left: "50%" }} />
        <span className="absolute top-1/2 h-[6px] -translate-y-1/2 rounded-full opacity-40" style={{ left: `${x(lo)}%`, width: `${Math.max(0.8, x(hi) - x(lo))}%`, background: c.bar }} />
        <span className="absolute top-1/2 h-[10px] w-[10px] -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white" style={{ left: `${x(row.pct)}%`, background: c.bar }} />
      </div>
      <div className="tnum mt-0.5 flex justify-between text-[10px] text-ink-3">
        <span>{signedPct(-span, 0)}</span>
        <span>
          no change · 95% interval {signedPct(lo)} to {signedPct(hi)}
        </span>
        <span>{signedPct(span, 0)}</span>
      </div>
    </div>
  );
}

function Change({ k, row, tone }: { k: string; row: MetricRow; tone: keyof typeof TONE }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
      <span className="tnum text-[13px] text-ink-2">
        {epValue(k, row.baseline)} <span className="text-ink-4">→</span> <b className="text-[17px] font-semibold text-ink">{epValue(k, row.policy)}</b>
      </span>
      <span className="tnum text-[13px] font-bold" style={{ color: TONE[tone].fg }}>
        {row.pct != null ? signedPct(row.pct) : `${row.diff > 0 ? "+" : "−"}${epValue(k, Math.abs(row.diff))}`}
      </span>
      {epUnit(k) && <span className="text-[11px] text-ink-3">{epUnit(k)}</span>}
    </div>
  );
}

function GoalCard({ g, sc }: { g: ObjectiveGoal; sc: ScenarioResult }) {
  const [name, paren] = splitLabel(g.label);
  const parts = Object.keys(METRIC_PARTS[g.metric] ?? {}).filter((k) => sc.metrics[k]);
  const wantDown = wantsDown(g);
  const vs = parts.map((k) => verdictFor(sc.metrics[k], wantDown));
  const overall: Verdict = !vs.length ? "flat" : vs.every((v) => v === "asked") ? "asked" : vs.some((v) => v === "against") ? "against" : "flat";
  const mixed = parts.length > 1 && overall === "flat" && vs.some((v) => v === "asked");
  const V = VERDICT[overall];
  return (
    <div className="rounded-2xl border border-line bg-white/85 p-4" data-goal-card={g.metric} data-verdict={overall}>
      <div className="flex flex-wrap items-start gap-x-3 gap-y-1.5">
        <span className="tnum flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[12.5px] font-bold text-accent-dark" title={`Rank ${g.rank} · ${Math.round(g.weight * 100)}% of the weight`}>
          {g.rank}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[14px] font-semibold leading-snug text-ink">
            <span className="font-medium text-ink-2">{dirWord(g.direction)}</span> {lowerFirst(name)}
          </div>
          <div className="text-[11px] text-ink-3">
            {Math.round(g.weight * 100)}% of the weight
            {paren ? ` · ${paren}` : ""}
            {g.against_the_grain ? " · an unusual thing to ask for" : ""}
          </div>
        </div>
        <span className="chip !px-2.5 !py-[3px] !text-[11.5px]" style={{ background: TONE[V.tone].bg, color: TONE[V.tone].fg }}>
          {mixed ? "Partly moved the way you asked" : V.text}
        </span>
      </div>
      <div className="mt-3 flex flex-col gap-3">
        {parts.length === 0 && <div className="text-[12px] text-ink-3">This measure was not reported for this situation.</div>}
        {parts.map((k, i) => {
          const tone = VERDICT[vs[i]].tone;
          return (
            <div key={k}>
              {parts.length > 1 && <div className="mb-0.5 text-[11.5px] font-semibold text-ink-2">{epLabel(k)}</div>}
              <Change k={k} row={sc.metrics[k]} tone={tone} />
              <div className="mt-1.5">
                <IntervalBar row={sc.metrics[k]} tone={tone} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SideList({ title, tone, rows, empty }: { title: string; tone: keyof typeof TONE; rows: [string, MetricRow][]; empty: string }) {
  const c = TONE[tone];
  return (
    <div className="rounded-2xl border border-line bg-white/85 p-4" data-side={tone}>
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: c.bar }} />
        <h4 className="text-[13.5px] font-semibold text-ink">{title}</h4>
        <span className="tnum chip" style={{ background: c.bg, color: c.fg }}>
          {rows.length}
        </span>
      </div>
      {rows.length === 0 ? (
        <div className="mt-2 text-[12px] text-ink-3">{empty}</div>
      ) : (
        <ul className="mt-2 divide-y divide-[rgba(20,26,51,0.06)]">
          {rows.map(([k, r]) => (
            <li key={k} className="flex flex-wrap items-baseline justify-between gap-x-3 py-1.5" title={r.pct_ci95 ? `95% interval ${signedPct(r.pct_ci95[0])} to ${signedPct(r.pct_ci95[1])}` : undefined}>
              <span className="min-w-0 text-[12.5px] font-medium text-ink">
                {epLabel(k)}
                {epUnit(k) && <span className="ml-1 text-[10.5px] font-normal text-ink-3">{epUnit(k)}</span>}
              </span>
              <span className="tnum whitespace-nowrap text-[12px] text-ink-2">
                {epValue(k, r.baseline)} <span className="text-ink-4">→</span> <b className="font-semibold text-ink">{epValue(k, r.policy)}</b>
                <b className="ml-2 inline-block min-w-[52px] text-right font-bold" style={{ color: c.fg }}>
                  {r.pct != null ? signedPct(r.pct) : `${r.diff > 0 ? "+" : "−"}${epValue(k, Math.abs(r.diff))}`}
                </b>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Guardrails({ sc, on }: { sc: ScenarioResult; on: boolean }) {
  const g = sc.guardrails;
  if (!g)
    return (
      <span className="chip !px-2.5 !py-[3px] !text-[11.5px]" style={{ background: "#FDEFD8", color: "#8A5A00" }} title="The safety guardrails were switched off for this search, so nothing held the plan to current practice on deaths, adverse events, diversion, overtime or transfers.">
        Guardrails {on ? "not reported" : "were off"}
      </span>
    );
  const missed = g.rows.filter((r) => !r.met);
  if (g.all_met)
    return (
      <span className="chip !px-2.5 !py-[3px] !text-[11.5px]" style={{ background: TONE.good.bg, color: TONE.good.fg }} title={g.rows.map((r) => r.label).join(" · ")}>
        All {g.rows.length} guardrails met
      </span>
    );
  return (
    <span className="chip !px-2.5 !py-[3px] !text-[11.5px]" style={{ background: TONE.bad.bg, color: TONE.bad.fg }}>
      {missed.length} of {g.rows.length} guardrails not met
    </span>
  );
}
const gNum = (v: number) => num(v, Math.abs(v) >= 100 ? 0 : 2);
function MissedGuardrails({ rows }: { rows: GuardrailRow[] }) {
  if (!rows.length) return null;
  return (
    <div className="mt-3 rounded-xl border border-[#E5484D]/25 bg-[#FDE7E8]/60 p-3" data-testid="opt-guard-missed">
      <div className="text-[12.5px] font-semibold text-[#B4232A]">Guardrails this plan did not hold in this situation</div>
      <ul className="mt-1.5 space-y-1">
        {rows.map((r) => (
          <li key={r.label} className="tnum text-[12px] leading-relaxed text-ink-2">
            <b className="font-semibold text-ink">{r.label.charAt(0).toUpperCase() + r.label.slice(1)}</b>: current practice {gNum(r.baseline)}, limit {gNum(r.limit)}, this plan {gNum(r.candidate)}.
          </li>
        ))}
      </ul>
    </div>
  );
}

function StaffChart({ staffing }: { staffing: Record<string, StaffingHead> }) {
  const groups: [string, string, string][] = [
    ["Providers", "md", "#2F55F5"],
    ["Nurses", "rn", "#22A3A0"],
  ];
  const shifts: [string, string][] = [
    ["day", "Day 07–15"],
    ["evening", "Evening 15–23"],
    ["night", "Night 23–07"],
  ];
  return (
    <div className="grid items-start gap-4 self-start min-[620px]:grid-cols-2" data-testid="opt-staffing">
      {groups.map(([title, key, color]) => {
        const rows = shifts.map(([s, label]) => ({ label, h: staffing[`${key}_${s}`] })).filter((r) => r.h);
        const vals = rows.map((r) => [meanPeople(r.h, "baseline"), meanPeople(r.h, "policy")]);
        const max = Math.max(1, ...vals.flat());
        return (
          <div key={key} className="rounded-xl bg-[#141a33]/[0.03] p-3.5">
            <div className="flex items-baseline justify-between">
              <div className="text-[12.5px] font-semibold text-ink">{title} per shift</div>
              <div className="text-[10.5px] text-ink-3">mean people</div>
            </div>
            <div className="mt-2.5 flex flex-col gap-3">
              {rows.map((r, i) => {
                const [b, p] = vals[i];
                const d = p - b;
                return (
                  <div key={r.label}>
                    <div className="flex items-baseline justify-between text-[11.5px]">
                      <span className="font-semibold text-ink-2">{r.label}</span>
                      <span className={`tnum font-semibold ${Math.abs(d) < 0.05 ? "text-ink-3" : "text-ink"}`}>{Math.abs(d) < 0.05 ? "no change" : `${d > 0 ? "+" : "−"}${Math.abs(d).toFixed(1)}`}</span>
                    </div>
                    {[
                      ["Current", b, "#B4BAD1"],
                      ["Plan", p, color],
                    ].map(([name, v, col]) => (
                      <div key={name as string} className="mt-1 flex items-center gap-2">
                        <span className="w-[46px] shrink-0 text-[10.5px] text-ink-3">{name}</span>
                        <span className="block h-2.5 flex-1 overflow-hidden rounded-full bg-[#141a33]/[0.06]">
                          <span className="block h-full rounded-full" style={{ width: `${((v as number) / max) * 100}%`, background: col as string }} />
                        </span>
                        <span className="tnum w-[34px] shrink-0 text-right text-[11.5px] font-semibold text-ink">{(v as number).toFixed(1)}</span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** "Lead: detail" sentences from the server, with arrows drawn as arrows and "policy" called the plan. */
function ChangeList({ lines }: { lines: string[] }) {
  const tidy = (s: string) => s.replace(/\s*->\s*/g, " → ").replace(/ensemble member (\d+)/g, "twin $1").replace(/ensemble members/g, "twins").replace(/\bbaseline → policy\b/g, "current → plan").replace(/\bpolicy\b/g, "plan").replace(/\bbaseline\b/g, "current practice");
  const notes = lines.filter((l) => /^People counts above/.test(l));
  const main = lines.filter((l) => !notes.includes(l));
  return (
    <div className="min-w-0">
      <ul className="divide-y divide-[rgba(20,26,51,0.06)]" data-testid="opt-changes">
        {main.map((l, i) => {
          const t = tidy(l);
          const cut = t.indexOf(":");
          const same = /unchanged/.test(t);
          const lead = cut > 0 && cut < 70 ? t.slice(0, cut) : null;
          return (
            <li key={i} className={`flex gap-2.5 py-2 text-[12.5px] leading-relaxed ${same ? "text-ink-3" : "text-ink-2"}`}>
              <span className={`mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full ${same ? "bg-ink-4" : "bg-accent"}`} />
              <span className="min-w-0">
                {lead ? (
                  <>
                    <b className={`font-semibold ${same ? "text-ink-2" : "text-ink"}`}>{lead.replace(/\s*\(mean people, current → plan\)/, "")}</b>
                    {t.slice(cut)}
                  </>
                ) : (
                  t
                )}
              </span>
            </li>
          );
        })}
      </ul>
      {notes.map((n) => (
        <p key={n} className="mt-2 text-[11px] leading-relaxed text-ink-3">
          {tidy(n)}
        </p>
      ))}
    </div>
  );
}

const when = (iso?: string) => {
  if (!iso) return "";
  const d = new Date(parseStamp(iso));
  return isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};
const PHASE_WORD: Record<string, string> = { done: "finished", failed: "stopped", queued: "running", starting: "running", searching: "running", selecting: "running", evaluating: "running" };

export function RunsList({ jobs, current, labels, onOpen }: { jobs: JobListItem[]; current: string | null; labels: Record<string, string>; onOpen: (id: string) => void }) {
  if (!jobs.length) return null;
  return (
    <section className="glass-solid p-5" data-testid="opt-runs">
      <h3 className="text-[14px] font-semibold text-ink">Earlier searches</h3>
      <ul className="mt-2 divide-y divide-[rgba(20,26,51,0.06)]">
        {jobs.slice(0, 8).map((j) => {
          const goals = (j.goals ?? []).slice().sort((a, b) => a.rank - b.rank);
          return (
            <li key={j.job_id}>
              <button type="button" disabled={j.job_id === current} onClick={() => onOpen(j.job_id)} data-run={j.job_id} className="flex w-full flex-wrap items-center gap-x-3 gap-y-0.5 rounded-lg px-2 py-2 text-left transition-colors hover:bg-accent-soft disabled:bg-[#141a33]/[0.03]">
                <span className="min-w-0 flex-1 text-[12.5px] font-semibold text-ink">{goals.map((g, i) => `${i ? dirWord(g.direction).toLowerCase() : dirWord(g.direction)} ${lowerFirst(splitLabel(labels[g.metric] ?? g.metric)[0])}`).join(", then ") || "No goals recorded"}</span>
                <span className="text-[11px] text-ink-3">
                  {when(j.created)}
                  {j.phase ? ` · ${PHASE_WORD[j.phase] ?? j.phase}` : ""}
                  {j.job_id === current ? " · showing" : ""}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function PlanResult({ job, result, example, onAgain }: { job: OptJob; result: OptResult; example: boolean; onAgain: () => void }) {
  const ids = Object.keys(result.scenarios);
  const [scId, setScId] = useState(ids[0]);
  const sc = result.scenarios[scId] ?? result.scenarios[ids[0]];
  const goals = result.objective.goals.slice().sort((a, b) => a.rank - b.rank);
  const asked = new Set(goals.flatMap((g) => Object.keys(METRIC_PARTS[g.metric] ?? {})));
  const base = result.scenarios[ids[0]];
  const nAsked = goals.filter((g) => {
    const parts = Object.keys(METRIC_PARTS[g.metric] ?? {}).filter((k) => base.metrics[k]);
    return parts.length > 0 && parts.every((k) => verdictFor(base.metrics[k], wantsDown(g)) === "asked");
  }).length;

  const other = Object.entries(sc.metrics)
    .filter(([k]) => !asked.has(k))
    .map(([k, r]) => ({ k, r, reading: readingFor(k, r) }));
  const shown = other.filter((o) => {
    if (o.reading === "flat") return false;
    const twin = SAME_AS[o.k];
    if (!twin || !sc.metrics[twin]) return true;
    // the same quantity counted another way: once is enough when both say the same thing
    return asked.has(twin) ? false : readingFor(twin, sc.metrics[twin]) !== o.reading;
  });
  const bySize = (a: { r: MetricRow }, b: { r: MetricRow }) => Math.abs(b.r.pct ?? 1e9) - Math.abs(a.r.pct ?? 1e9);
  const worse = shown.filter((o) => o.reading === "worse").sort(bySize);
  const better = shown.filter((o) => o.reading === "better").sort(bySize);
  const moved = shown.filter((o) => o.reading === "changed").sort(bySize);
  // an older result's sentence quotes the internal score as a percentage; that is not an improvement anyone can read
  const sentence = result.headline && !/scores [\d.]+% better/.test(result.headline) ? result.headline : null;
  const proto = result.protocol;

  return (
    <div className="flex flex-col gap-4" data-testid="opt-result">
      <section className="glass-solid p-5" aria-labelledby="opt-s3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="eyebrow">Result</span>
            <span className="sim-tag">simulated</span>
            {example && (
              <span className="sim-tag" style={{ background: "#FDEFD8", color: "#8A5A00" }} title="A real search recorded earlier and bundled with the app. It was not run just now.">
                recorded example
              </span>
            )}
          </div>
          <button type="button" className="btn-primary" onClick={onAgain} data-testid="opt-again">
            Try another goal
          </button>
        </div>
        <h2 id="opt-s3" className="mt-2 max-w-[60ch] text-[22px] font-semibold leading-tight tracking-[-0.015em] text-ink" data-testid="opt-headline">
          {result.picked_baseline
            ? "Nothing the search found beats current practice on these goals."
            : nAsked === goals.length
              ? goals.length === 1
                ? "The plan moved your goal the way you asked."
                : `The plan moved ${goals.length === 2 ? "both" : `all ${goals.length}`} of your goals the way you asked.`
              : `The plan moved ${nAsked} of your ${goals.length} goals the way you asked.`}
        </h2>
        {result.picked_baseline ? (
          <p className="mt-2 max-w-[80ch] text-[13px] leading-relaxed text-ink-2">The plan shown below is current practice itself, so every comparison reads as no change. That is an honest answer: with the levers the system is allowed to move, it could not do better on what you asked for.</p>
        ) : (
          sentence && <p className="mt-2 max-w-[90ch] text-[13px] leading-relaxed text-ink-2">{sentence}</p>
        )}
        <p className="mt-2 text-[12px] text-ink-3">
          Compared with current practice on the same simulated patients{proto?.days ? `, ${proto.days} days` : ""}
          {proto?.twins ? `, in ${proto.twins} twin${proto.twins === 1 ? "" : "s"} of the hospital` : ""}. These are fresh patients: none were used in the search. The sentence above counts normal operations; the tabs below show each situation.
        </p>
      </section>

      <section className="glass-solid p-5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <div className="seg max-w-full overflow-x-auto" role="tablist" aria-label="Situation">
            {ids.map((id) => (
              <button key={id} type="button" role="tab" aria-selected={id === scId} data-on={id === scId} data-scenario={id} onClick={() => setScId(id)}>
                {scenarioLabel(id)}
              </button>
            ))}
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-1.5">
            <span
              className="chip cursor-help border border-line bg-white/80 !px-2.5 !py-[3px] !text-[11.5px] text-ink-2"
              title="Public data cannot pin down every detail of this hospital. A twin is one version of the simulated hospital that matches the public record equally well. The plan was tested in each of them, and this counts the twins in which it scored better on your goals than current practice."
              data-testid="opt-twins"
            >
              Better on your goals in <b className="tnum mx-0.5 font-bold text-ink">{sc.twins_improved}</b> of <b className="tnum mx-0.5 font-bold text-ink">{sc.n_twins}</b> twins the public record cannot tell apart
            </span>
            <Guardrails sc={sc} on={result.objective.guardrails} />
          </div>
        </div>
        {sc.guardrails && <MissedGuardrails rows={sc.guardrails.rows.filter((r) => !r.met)} />}

        <h3 className="mt-5 text-[15px] font-semibold text-ink">What you asked for</h3>
        <div className="mt-2.5 grid gap-3 min-[900px]:grid-cols-2">
          {goals.map((g) => (
            <GoalCard key={g.metric} g={g} sc={sc} />
          ))}
        </div>

        <h3 className="mt-6 text-[15px] font-semibold text-ink">What it cost or changed elsewhere</h3>
        <p className="mt-0.5 text-[12px] text-ink-3">Every other measure whose 95% interval excludes no change, with current practice → the plan. Anything not listed did not move measurably.</p>
        <div className="mt-2.5 grid gap-3 min-[900px]:grid-cols-2">
          <SideList title="Got worse" tone="bad" rows={worse.map((o) => [o.k, o.r])} empty="Nothing else got measurably worse in this situation." />
          <SideList title="Got better" tone="good" rows={better.map((o) => [o.k, o.r])} empty="Nothing else got measurably better in this situation." />
        </div>
        {moved.length > 0 && (
          <div className="mt-3">
            <SideList title="Changed, neither good nor bad in itself" tone="flat" rows={moved.map((o) => [o.k, o.r])} empty="" />
          </div>
        )}
      </section>

      <section className="glass-solid p-5">
        <h3 className="text-[15px] font-semibold text-ink">What changes on the floor</h3>
        <p className="mt-0.5 max-w-[80ch] text-[12px] text-ink-3">A staffing and capacity plan with trigger thresholds, compared with current practice in normal operations. No clinical decision is part of it.</p>
        {result.picked_baseline ? (
          <p className="mt-3 text-[13px] text-ink-2">Nothing changes: the plan is current practice.</p>
        ) : (
          <div className="mt-3 grid gap-5 min-[1000px]:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
            {result.staffing ? <StaffChart staffing={result.staffing} /> : <div className="text-[12px] text-ink-3">No staffing breakdown was recorded for this search.</div>}
            {result.what_changes?.length ? <ChangeList lines={result.what_changes} /> : <div className="text-[12px] text-ink-3">No list of changes was recorded for this search.</div>}
          </div>
        )}
        {(result.search?.length ?? 0) > 0 && (
          <details className="mt-4 border-t border-line pt-3">
            <summary className="cursor-pointer text-[12.5px] font-semibold text-accent-dark">How the search went</summary>
            <div className="mt-3">
              <SearchCharts history={result.search!} gens={Math.max(proto?.search?.gens ?? 0, result.search!.length)} objective={result.objective} />
            </div>
            {proto?.search?.pop ? (
              <p className="mt-2 text-[11.5px] text-ink-3">
                {proto.search.pop} plans per round, {proto.search.gens ?? result.search!.length} rounds{result.seconds ? `, ${Math.round(result.seconds / 60)} min in all` : ""}.
              </p>
            ) : null}
          </details>
        )}
      </section>

      <section className="rounded-2xl border border-accent/15 bg-accent-soft/70 px-5 py-4">
        <p className="text-[15px] font-semibold leading-snug text-accent-dark">It handles the scheduling and capacity scaffolding so clinicians can focus on patients.</p>
        <p className="mt-1.5 max-w-[100ch] text-[12px] leading-relaxed text-ink-2">
          <span className="sim-tag mr-1.5 !bg-white/70">simulated</span>
          {proto?.note ?? "Simulated. Calibrated to public aggregates; not validated on the hospital's operational data."}
        </p>
      </section>
      <span className="sr-only" data-job={job.job_id} />
    </div>
  );
}
