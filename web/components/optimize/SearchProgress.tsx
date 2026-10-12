"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { dirWord, lowerFirst, parseStamp, epLabel, epUnit, epValue, METRIC_PARTS, splitLabel, type HistoryRow, type Objective, type OptJob, type Phase, wantsDown } from "@/lib/optimize";

const ACCENT = "#2F55F5";
const INK3 = "#8089A8";
const GRID = "rgba(20,26,51,0.07)";

function useWidth<T extends HTMLElement>(initial = 480) {
  const ref = useRef<T>(null);
  const [w, setW] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(el.clientWidth));
    ro.observe(el);
    setW(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** One value per search round. The x axis always has `slots` positions, so the chart does not jump as rounds land. */
export function RoundChart({ values, slots, height = 150, reference, referenceLabel, format, ariaLabel }: { values: number[]; slots: number; height?: number; reference?: number | null; referenceLabel?: string; format: (v: number) => string; ariaLabel: string }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const padL = 10;
  const padR = 14;
  const padT = 22;
  const padB = 22;
  const iw = Math.max(10, w - padL - padR);
  const ih = height - padT - padB;
  const all = values.concat(reference != null ? [reference] : []).filter((v) => isFinite(v));
  let lo = all.length ? Math.min(...all) : 0;
  let hi = all.length ? Math.max(...all) : 1;
  if (hi - lo < 1e-9) {
    const pad = Math.abs(hi) * 0.05 || 1;
    lo -= pad;
    hi += pad;
  }
  const span = hi - lo;
  lo -= span * 0.12;
  hi += span * 0.12;
  const n = Math.max(1, slots);
  const x = (i: number) => padL + (n === 1 ? iw / 2 : (iw * (i + 0.5)) / n);
  const y = (v: number) => padT + ih - ((v - lo) / (hi - lo)) * ih;
  const last = values.length - 1;
  return (
    <div ref={ref} style={{ height }} className="relative w-full">
      <svg width={w} height={height} role="img" aria-label={ariaLabel} className="absolute inset-0">
        {Array.from({ length: n }, (_, i) => (
          <g key={i}>
            <line x1={x(i)} x2={x(i)} y1={padT} y2={padT + ih} stroke={GRID} />
            <text x={x(i)} y={height - 6} textAnchor="middle" fontSize="10" fontWeight={600} fill={i <= last ? "#4A5275" : "#B4BAD1"}>
              {n > 8 ? i + 1 : `Round ${i + 1}`}
            </text>
          </g>
        ))}
        {reference != null && isFinite(reference) && (
          <g>
            <line x1={padL} x2={padL + iw} y1={y(reference)} y2={y(reference)} stroke={INK3} strokeWidth={1.2} strokeDasharray="4 4" />
            <text x={padL + 2} y={y(reference) - 5} fontSize="10" fontWeight={600} fill={INK3}>
              {referenceLabel}
            </text>
          </g>
        )}
        {values.length > 1 && <polyline fill="none" stroke={ACCENT} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" points={values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ")} />}
        {values.map((v, i) => (
          <g key={i}>
            <circle cx={x(i)} cy={y(v)} r={i === last ? 5 : 3.5} fill={ACCENT} stroke="#fff" strokeWidth={2}>
              <title>{`Round ${i + 1}: ${format(v)}`}</title>
            </circle>
            {(i === last || n <= 6) && (
              <text x={x(i)} y={y(v) - 10} textAnchor="middle" fontSize="10.5" fontWeight={700} fill="#141A33" className="tnum">
                {format(v)}
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}

/** The chosen measures, as the best plan of each round scored on them. */
export function SearchCharts({ history, gens, objective, compact = false }: { history: HistoryRow[]; gens: number; objective?: Objective; compact?: boolean }) {
  const metrics = useMemo(() => {
    const out: { key: string; want: string }[] = [];
    for (const g of objective?.goals ?? [])
      for (const k of Object.keys(METRIC_PARTS[g.metric] ?? {})) if (!out.some((o) => o.key === k)) out.push({ key: k, want: wantsDown(g) ? "asked: lower" : "asked: higher" });
    return out;
  }, [objective]);
  const baseline = history.find((h) => h.baseline_score != null)?.baseline_score ?? null;
  return (
    <div className={`grid gap-4 ${compact ? "" : "min-[1000px]:grid-cols-2"}`}>
      <div className="rounded-xl bg-[#141a33]/[0.03] p-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <div className="text-[12.5px] font-semibold text-ink">Best score so far, by round</div>
          <div className="text-[10.5px] text-ink-3">higher is better · internal units</div>
        </div>
        <RoundChart values={history.map((h) => h.best_score)} slots={gens} reference={baseline} referenceLabel="current practice" format={(v) => v.toFixed(3)} ariaLabel="Best score on your goals in each search round" />
      </div>
      <div className="grid content-start gap-3 min-[560px]:grid-cols-2">
        {metrics.map((m) => (
          <div key={m.key} className="rounded-xl bg-[#141a33]/[0.03] p-3">
            <div className="truncate text-[12px] font-semibold text-ink" title={epLabel(m.key)}>
              {epLabel(m.key)}
            </div>
            <div className="text-[10.5px] text-ink-3">
              best plan of each round{epUnit(m.key) ? ` · ${epUnit(m.key)}` : ""} · {m.want}
            </div>
            <RoundChart values={history.map((h) => h.best[m.key]).filter((v) => v != null)} slots={gens} height={96} format={(v) => epValue(m.key, v)} ariaLabel={`${epLabel(m.key)} of the best plan in each round`} />
          </div>
        ))}
      </div>
    </div>
  );
}

const STEPS: { id: string; label: string; phases: Phase[] }[] = [
  { id: "search", label: "Searching", phases: ["queued", "starting", "searching"] },
  { id: "choose", label: "Choosing", phases: ["selecting"] },
  { id: "check", label: "Checking on fresh patients", phases: ["evaluating"] },
  { id: "done", label: "Done", phases: ["done"] },
];

/** A rough guess from how long the rounds have taken; before the first round lands there is nothing to base it on. */
function remainingWords(job: OptJob, elapsed: number): string {
  const st = job.status;
  const hist = st.history ?? [];
  const gens = st.gens ?? 0;
  if (!hist.length || !gens) return "usually four to five minutes in all";
  const per = hist.reduce((s, h) => s + h.seconds, 0) / hist.length;
  // choosing and the held-out check have together taken a little less than the search itself
  const left = Math.max(0, 5 + gens * per * 1.9 - elapsed);
  if (left <= 0) return "taking longer than usual";
  if (left < 45) return "under a minute left, roughly";
  return `about ${Math.max(1, Math.round(left / 60))} min left, roughly`;
}

export function SearchProgress({ job, lost, onBack, onRetry }: { job: OptJob; lost: boolean; onBack: () => void; onRetry: () => void }) {
  const st = job.status;
  const failed = st.phase === "failed";
  // The server stamps elapsed time only when the phase or round changes: count on from that stamp. Its own "updated"
  // time is used when it is close to this machine's clock (so a reload mid-phase shows the true time); else local time.
  const stampOf = () => {
    const s = st.elapsed_s ?? 0;
    const upd = parseStamp(st.updated);
    const ago = Date.now() - upd;
    return { s, at: isFinite(ago) && ago >= 0 && ago < 3600_000 ? upd : Date.now() };
  };
  const stamp = useRef(stampOf());
  if ((st.elapsed_s ?? 0) !== stamp.current.s) stamp.current = stampOf();
  const [, tick] = useState(0);
  useEffect(() => {
    if (failed) return;
    const t = setInterval(() => tick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [failed]);
  const elapsed = failed ? stamp.current.s : stamp.current.s + (Date.now() - stamp.current.at) / 1000;

  const stepIx = Math.max(0, STEPS.findIndex((s) => s.phases.includes(st.phase)));
  const hist = st.history ?? [];
  const gens = st.gens ?? 0;
  const round = Math.min(gens, hist.length + 1);
  const goals = st.objective?.goals ?? [];
  const sub =
    st.phase === "queued" || st.phase === "starting"
      ? "Setting up the simulated copies of the hospital."
      : st.phase === "searching"
        ? gens
          ? `Round ${round} of ${gens}`
          : "Searching"
        : st.phase === "selecting"
          ? "Re-running the best plans, and current practice, on days none of them has seen, and keeping the winner."
          : st.phase === "evaluating"
            ? "Comparing the chosen plan with current practice on fresh simulated patients, in three situations."
            : "";

  return (
    <section className="glass-solid p-5" aria-labelledby="opt-s2" data-testid="opt-progress" data-phase={st.phase}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="opt-s2" className="text-[19px] font-semibold tracking-[-0.01em] text-ink">
            {failed ? "The search stopped" : "Searching for a plan"}
          </h2>
          <p className="mt-1 max-w-[70ch] text-[13px] leading-relaxed text-ink-2">Trying 46 staffing and capacity plans per round on simulated copies of the hospital, keeping the best, and repeating.</p>
        </div>
        <button type="button" className="btn-quiet" onClick={onBack}>
          Back to goals
        </button>
      </div>

      {goals.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="eyebrow mr-1">Your goals</span>
          {goals.map((g) => (
            <span key={g.metric} className="chip border border-line bg-white/80 !py-[3px] text-ink-2">
              <b className="tnum font-bold text-accent-dark">{g.rank}</b>
              {dirWord(g.direction)} {lowerFirst(splitLabel(g.label)[0])}
            </span>
          ))}
          <span className="chip bg-[#141a33]/[0.05] text-ink-3">guardrails {st.objective?.guardrails ? "on" : "off"}</span>
        </div>
      )}

      {failed ? (
        <div className="mt-4 rounded-xl border border-[#E5484D]/30 bg-[#FDE7E8] p-4" role="alert" data-testid="opt-failed">
          <div className="text-[13px] font-semibold text-[#B4232A]">The search did not finish.</div>
          <div className="mt-1 break-words text-[12px] leading-relaxed text-[#7A1D22]">{st.error || "The server gave no reason."}</div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="btn-primary" onClick={onRetry}>
              Try again with the same goals
            </button>
            <button type="button" className="btn-quiet" onClick={onBack}>
              Change the goals
            </button>
          </div>
        </div>
      ) : (
        <>
          <ol className="mt-5 grid grid-cols-4 gap-2" aria-label="Progress">
            {STEPS.map((s, i) => {
              const state = i < stepIx ? "done" : i === stepIx ? "now" : "todo";
              return (
                <li key={s.id} aria-current={state === "now" ? "step" : undefined} className="min-w-0">
                  <div className="relative h-1.5 overflow-hidden rounded-full bg-[#141a33]/[0.08]">
                    {s.id === "search" && gens > 0 ? (
                      // one segment per round: filled as each round's result arrives
                      <div className="absolute inset-0 flex gap-[2px]">
                        {Array.from({ length: gens }, (_, k) => (
                          <span key={k} className={`h-full flex-1 rounded-full ${k < hist.length || state === "done" ? "bg-accent" : k === hist.length && state === "now" ? "animate-pulse bg-accent/45" : ""}`} />
                        ))}
                      </div>
                    ) : (
                      <span className={`absolute inset-0 rounded-full ${state === "done" ? "bg-accent" : state === "now" ? "animate-pulse bg-accent/45" : ""}`} />
                    )}
                  </div>
                  <div className={`mt-1.5 text-[12px] font-semibold leading-tight ${state === "todo" ? "text-ink-4" : state === "now" ? "text-accent-dark" : "text-ink-2"}`}>{s.label}</div>
                </li>
              );
            })}
          </ol>
          <div className="mt-3 flex min-h-[40px] flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px]" aria-live="polite">
            <span className="font-semibold text-ink" data-testid="opt-phase-line">
              {sub}
            </span>
            <span className="tnum ml-auto text-ink-2">
              {mmss(elapsed)} elapsed <span className="text-ink-3">· {remainingWords(job, elapsed)}</span>
            </span>
          </div>
          {lost && <div className="mt-1 text-[11.5px] font-medium text-[#8A5A00]">Lost contact with the server. The search carries on there; retrying every two seconds.</div>}
        </>
      )}

      <div className="mt-4 min-h-[230px]">
        {hist.length ? (
          <SearchCharts history={hist} gens={Math.max(gens, hist.length)} objective={st.objective} />
        ) : (
          !failed && <div className="flex h-[230px] items-center justify-center rounded-xl bg-[#141a33]/[0.03] text-[12.5px] text-ink-3">The chart starts when the first round finishes, in about half a minute.</div>
        )}
      </div>
      <p className="mt-4 text-[11.5px] leading-relaxed text-ink-3">
        <span className="sim-tag mr-1.5">simulated</span>
        You can leave this page; the search keeps running on the server and this page picks it up again when you come back.
      </p>
    </section>
  );
}
