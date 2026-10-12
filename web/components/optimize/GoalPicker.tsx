"use client";
import { useRef, useState } from "react";
import { dirWord, lowerFirst, MENU_GROUPS, ranksOf, splitLabel, weightsOf, type Direction, type Headline, type MenuMetric, type OptMenu, type Picks, type Preset, picksFrom } from "@/lib/optimize";
import { planFromHeadline, pctText } from "@/lib/home";
import { Icon, ICONS } from "../ui/atoms";

const AMBER = { bg: "#FDEFD8", fg: "#8A5A00" };

/** The line under a measure's name: what it counts and in what unit. Always one line, always there. */
function hintWords(m: MenuMetric, paren: string | null): string {
  const detail = paren ? lowerFirst(paren.replace(/^proxy:\s*/, "")).replace(/\bwait and stay\b/, "waits and stays") : "";
  // a proxy or an index has no everyday reading: say which way is the good one
  if (m.proxy || m.unit === "index") return `${m.proxy ? "proxy" : "index"} · ${m.natural === "min" ? "lower" : "higher"} is better${detail ? `: ${detail}` : ""}`;
  const unit = m.unit === "share" ? "share of arrivals" : m.unit;
  return detail ? `${detail} · ${unit}` : unit;
}

function Tri({ value, onChange, label }: { value: Direction | null; onChange: (v: Direction | null) => void; label: string }) {
  const opts: [Direction | null, string][] = [
    ["max", "Maximize"],
    ["min", "Minimize"],
    [null, "Ignore"],
  ];
  return (
    <div className="seg shrink-0" role="group" aria-label={label}>
      {opts.map(([v, text]) => (
        <button key={text} type="button" aria-pressed={value === v} data-on={value === v} data-dir={v ?? "ignore"} onClick={() => onChange(v)} className={value === v ? (v === null ? "!text-ink-2" : "!bg-accent !text-white") : ""}>
          {text}
        </button>
      ))}
    </div>
  );
}

function MetricRow({ m, value, onChange }: { m: MenuMetric; value: Direction | null; onChange: (v: Direction | null) => void }) {
  const [name, paren] = splitLabel(m.label);
  const against = value != null && value !== m.natural;
  // Two fixed rows: the name with its three-way switch, then one hint line. The hint changes its words, never its
  // height, so nothing on the page moves when a measure is switched on, off or against the grain.
  return (
    <div className="py-2" data-metric={m.id}>
      <div className="flex items-center gap-x-3">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1.5 text-[13px] font-semibold leading-snug text-ink">
          <span>{name}</span>
          {m.proxy && (
            <span className="chip shrink-0" style={{ background: AMBER.bg, color: AMBER.fg }}>
              proxy
            </span>
          )}
        </div>
        <Tri value={value} onChange={onChange} label={name} />
      </div>
      <div className={`mt-0.5 h-4 truncate text-[11px] leading-4 max-[520px]:h-8 max-[520px]:whitespace-normal ${against ? "font-medium text-[#8A5A00]" : "text-ink-3"}`} data-hint={against ? "unusual" : "plain"}>
        {against ? "An unusual thing to ask for. The system will still do it." : hintWords(m, paren)}
      </div>
    </div>
  );
}

function Switch({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)} className={`relative h-6 w-10 shrink-0 rounded-full transition-colors ${on ? "bg-accent" : "bg-[#141a33]/[0.18]"}`} data-testid="opt-guardrails">
      <span className={`absolute top-[3px] h-[18px] w-[18px] rounded-full bg-white shadow transition-all ${on ? "left-[19px]" : "left-[3px]"}`} />
    </button>
  );
}

/** The active goals in order of importance: drag by the handle, or use the arrow buttons (or arrow keys on the handle). */
function Priorities({ menu, picks, setPicks }: { menu: OptMenu; picks: Picks; setPicks: (p: Picks) => void }) {
  const rows = useRef(new Map<string, HTMLLIElement>());
  const [drag, setDrag] = useState<string | null>(null);
  const ranks = ranksOf(picks);
  const weights = weightsOf(picks);
  const byId = new Map(menu.metrics.map((m) => [m.id, m]));

  const move = (from: number, to: number) => {
    if (to < 0 || to >= picks.order.length || to === from) return;
    const order = picks.order.slice();
    const [id] = order.splice(from, 1);
    order.splice(to, 0, id);
    setPicks({ ...picks, order });
  };
  const onMove = (y: number) => {
    if (!drag) return;
    const from = picks.order.indexOf(drag);
    const mid = (i: number) => {
      const r = rows.current.get(picks.order[i])?.getBoundingClientRect();
      return r ? r.top + r.height / 2 : NaN;
    };
    for (let i = 0; i < from; i++) if (y < mid(i)) return move(from, i);
    for (let i = picks.order.length - 1; i > from; i--) if (y > mid(i)) return move(from, i);
  };

  // the empty box is as tall as two goals, so the panel below does not move when the first two are added
  if (!picks.order.length)
    return (
      <div className="flex h-[168px] flex-col items-center justify-center rounded-xl border border-dashed border-[#141a33]/[0.14] px-4 text-center text-[12.5px] leading-relaxed text-ink-3" data-testid="opt-empty">
        Nothing chosen yet.
        <br />
        Set at least one measure to Maximize or Minimize, or start from an example.
      </div>
    );
  return (
    <ol className="flex min-h-[168px] flex-col gap-1.5" data-testid="opt-priorities">
      {picks.order.map((id, i) => {
        const m = byId.get(id);
        const [name] = splitLabel(m?.label ?? id);
        const d = picks.dir[id];
        const tied = i > 0 && !!picks.tied[id];
        return (
          <li
            key={id}
            ref={(el) => {
              if (el) rows.current.set(id, el);
              else rows.current.delete(id);
            }}
            data-goal={id}
            className={`rounded-xl border bg-white/80 px-2 py-2 transition-shadow ${drag === id ? "border-accent/40 shadow-pill" : "border-line"}`}
          >
            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-label={`Reorder ${name}: drag, or press the up and down arrow keys`}
                className="flex h-7 w-5 shrink-0 cursor-grab touch-none items-center justify-center rounded text-ink-4 hover:text-ink-2 active:cursor-grabbing"
                onPointerDown={(e) => {
                  e.currentTarget.setPointerCapture(e.pointerId);
                  setDrag(id);
                }}
                onPointerMove={(e) => onMove(e.clientY)}
                onPointerUp={() => setDrag(null)}
                onPointerCancel={() => setDrag(null)}
                onKeyDown={(e) => {
                  if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
                  e.preventDefault();
                  move(i, e.key === "ArrowUp" ? i - 1 : i + 1);
                }}
              >
                <svg width="8" height="14" viewBox="0 0 8 14" aria-hidden fill="currentColor">
                  {[2, 7, 12].flatMap((y) => [1.5, 6.5].map((x) => <circle key={`${x}-${y}`} cx={x} cy={y} r="1.3" />))}
                </svg>
              </button>
              <span className="tnum flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[11.5px] font-bold text-accent-dark" title={`Rank ${ranks[i]}`}>
                {ranks[i]}
              </span>
              {/* room for a two-line name in every row, so all rows are the same height */}
              <div className="flex min-h-[35px] min-w-0 flex-1 items-center">
                <div className="text-[12.5px] font-semibold leading-snug text-ink">
                  <span className="font-medium text-ink-2">{dirWord(d)}</span> {lowerFirst(name)}
                </div>
              </div>
              <div className="flex shrink-0 items-center">
                <button type="button" className="flex h-7 w-7 items-center justify-center rounded-full text-ink-3 hover:bg-accent-soft hover:text-accent-dark disabled:opacity-30 disabled:hover:bg-transparent" aria-label={`Move ${name} up`} disabled={i === 0} onClick={() => move(i, i - 1)}>
                  <Icon d={ICONS.up} size={14} stroke={2.2} />
                </button>
                <button type="button" className="flex h-7 w-7 items-center justify-center rounded-full text-ink-3 hover:bg-accent-soft hover:text-accent-dark disabled:opacity-30 disabled:hover:bg-transparent" aria-label={`Move ${name} down`} disabled={i === picks.order.length - 1} onClick={() => move(i, i + 1)}>
                  <Icon d={ICONS.down} size={14} stroke={2.2} />
                </button>
                <button
                  type="button"
                  className="flex h-7 w-7 items-center justify-center rounded-full text-ink-4 hover:bg-[#FDE7E8] hover:text-[#B4232A]"
                  aria-label={`Stop optimizing ${name}`}
                  onClick={() => {
                    const dir = { ...picks.dir };
                    delete dir[id];
                    setPicks({ ...picks, dir, order: picks.order.filter((x) => x !== id) });
                  }}
                >
                  <Icon d={ICONS.close} size={13} stroke={2.2} />
                </button>
              </div>
            </div>
            <div className="mt-1.5 flex items-center gap-2 pl-7">
              <span className="block h-1.5 flex-1 overflow-hidden rounded-full bg-[#141a33]/[0.07]" aria-hidden>
                <span className="block h-full rounded-full bg-accent transition-[width] duration-200" style={{ width: `${weights[i] * 100}%` }} />
              </span>
              <span className="tnum w-9 shrink-0 text-right text-[11px] font-semibold text-ink-2">
                {Math.round(weights[i] * 100)}%
              </span>
              {/* always the same width: "tied" and "tie" swap words without nudging the bar beside them */}
              <button
                type="button"
                aria-pressed={tied}
                aria-label={tied ? `${name}: tied with the goal above. Press to untie` : `Give ${name} the same importance as the goal above`}
                disabled={i === 0}
                className={`w-[92px] shrink-0 rounded-full py-[2px] text-center text-[10.5px] font-semibold transition-colors ${i === 0 ? "invisible" : tied ? "bg-accent-soft text-accent-dark" : "text-ink-3 hover:bg-accent-soft hover:text-accent-dark"}`}
                onClick={() => setPicks({ ...picks, tied: { ...picks.tied, [id]: !tied } })}
              >
                {tied ? "tied with above" : "tie with above"}
              </button>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** The plan the system recommends for this hospital: the figures first, the server's full sentence on request. */
function Recommended({ headline }: { headline: Headline }) {
  const [open, setOpen] = useState(false);
  const p = planFromHeadline(headline);
  return (
    <section className="glass-solid p-5" data-testid="opt-recommended">
      <div className="flex items-center gap-2">
        <h3 className="text-[14px] font-semibold text-ink">Our recommended plan for RWJ</h3>
        <span className="sim-tag">simulated</span>
      </div>
      {p ? (
        <>
          <p className="mt-1 text-[11.5px] text-ink-3">Same budget, better flow · against current practice, normal week</p>
          <ul className="tnum mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[12px] text-ink-2">
            {(
              [
                ["Mean wait", p.wait],
                ["Walk-outs", p.walkouts],
                ["Median stay", p.los],
                ["Boarding hours", p.boarding],
                ["Labor cost", p.labor],
              ] as [string, number][]
            ).map(([k, v]) => (
              <li key={k} className="flex items-baseline justify-between gap-2">
                <span>{k}</span>
                <b className="font-semibold text-[#11734B]">{pctText(v)}</b>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11.5px] leading-relaxed text-ink-3">
            {p.allConstraintsMet ? "Every safety constraint met. " : ""}Holds in {p.holds} of {p.twins} twins the public record cannot tell apart.
          </p>
        </>
      ) : null}
      {(open || !p) && <p className="mt-2 text-[11.5px] leading-relaxed text-ink-2">{headline.sentence}</p>}
      {p && (
        <button type="button" className="mt-1.5 text-[11.5px] font-semibold text-accent-dark hover:underline" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {open ? "Hide the full statement" : "Read the full statement"}
        </button>
      )}
    </section>
  );
}

export function GoalPicker({
  menu,
  picks,
  setPicks,
  canRun,
  why,
  busy,
  error,
  onRun,
  onExample,
  onAttach,
  headline,
  narrow,
}: {
  menu: OptMenu;
  picks: Picks;
  setPicks: (p: Picks) => void;
  canRun: boolean;
  why: string | null;
  busy: boolean;
  error: string | null;
  onRun: () => void;
  /** open the recorded example (when searches cannot be run here) */
  onExample: (() => void) | null;
  /** a search someone started is still running on the server */
  onAttach: (() => void) | null;
  headline: Headline | null;
  narrow: boolean;
}) {
  const setDir = (id: string, v: Direction | null) => {
    const dir = { ...picks.dir };
    let order = picks.order;
    if (v == null) {
      delete dir[id];
      order = order.filter((x) => x !== id);
    } else {
      dir[id] = v;
      if (!order.includes(id)) order = [...order, id];
    }
    setPicks({ ...picks, dir, order });
  };
  const known = new Set(MENU_GROUPS.flatMap((g) => g.ids));
  const groups = [...MENU_GROUPS.map((g) => ({ title: g.title, metrics: g.ids.map((id) => menu.metrics.find((m) => m.id === id)).filter((m): m is MenuMetric => !!m) })), { title: "Other", metrics: menu.metrics.filter((m) => !known.has(m.id)) }].filter((g) => g.metrics.length);
  const applyPreset = (p: Preset) => {
    const ok = p.goals.filter((g) => menu.metrics.some((m) => m.id === g.metric));
    setPicks(picksFrom(ok, p.guardrails ?? true));
  };
  const presetOn = (p: Preset) => {
    const q = picksFrom(p.goals, p.guardrails ?? true);
    return q.order.length === picks.order.length && q.order.every((id, i) => picks.order[i] === id && picks.dir[id] === q.dir[id]);
  };
  const n = picks.order.length;

  return (
    <div className={`grid gap-4 ${narrow ? "" : "grid-cols-[minmax(0,1fr)_360px] items-start"}`}>
      <section className="glass-solid p-5" aria-labelledby="opt-s1">
        <h2 id="opt-s1" className="text-[19px] font-semibold tracking-[-0.01em] text-ink">
          What do you want?
        </h2>
        <p className="mt-1 max-w-[62ch] text-[13px] leading-relaxed text-ink-2">Pick any goal you like, sensible or not. Mark each measure you care about as something to maximize or minimize, then put them in order on the right.</p>

        <div className="mt-4">
          <div className="eyebrow mb-1.5">Start from an example</div>
          <div className="flex flex-wrap gap-1.5" data-testid="opt-presets">
            {menu.presets.map((p) => (
              <button key={p.id} type="button" aria-pressed={presetOn(p)} onClick={() => applyPreset(p)} data-preset={p.id} className={`inline-flex h-8 items-center rounded-full border px-3 text-[12px] font-semibold transition-colors ${presetOn(p) ? "border-accent/40 bg-accent-soft text-accent-dark" : "border-line bg-white/70 text-ink-2 hover:border-accent/30 hover:text-accent-dark"}`}>
                {p.label}
              </button>
            ))}
            {/* always there (disabled when there is nothing to clear) so the row of examples never re-wraps */}
            <button type="button" className="btn !h-8" disabled={n === 0} onClick={() => setPicks({ ...picks, dir: {}, order: [], tied: {} })}>
              Clear
            </button>
          </div>
        </div>

        <div className={`mt-4 grid gap-x-8 ${narrow ? "" : "min-[1180px]:grid-cols-2"}`}>
          {groups.map((g) => (
            <div key={g.title} className="mb-3">
              <div className="eyebrow border-b border-line pb-1.5">{g.title}</div>
              <div className="divide-y divide-[rgba(20,26,51,0.06)]">
                {g.metrics.map((m) => (
                  <MetricRow key={m.id} m={m} value={picks.dir[m.id] ?? null} onChange={(v) => setDir(m.id, v)} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <aside className={`flex flex-col gap-4 ${narrow ? "" : "sticky top-0"}`}>
        <section className="glass-solid p-5" aria-labelledby="opt-prio">
          <div className="flex items-baseline justify-between">
            <h3 id="opt-prio" className="text-[14px] font-semibold text-ink">
              Your priorities
            </h3>
            <span className="shrink-0 text-[11px] text-ink-3">most important first</span>
          </div>
          <div className="mt-3">
            <Priorities menu={menu} picks={picks} setPicks={setPicks} />
          </div>
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-ink-3">{menu.ranking}</p>

          <div className="mt-4 border-t border-line pt-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-[13px] font-semibold text-ink">Safety guardrails</div>
              <div className="flex items-center gap-2">
                <span className={`text-[11.5px] font-semibold ${picks.guardrails ? "text-[#11734B]" : "text-[#8A5A00]"}`}>{picks.guardrails ? "On" : "Off"}</span>
                <Switch on={picks.guardrails} onChange={(v) => setPicks({ ...picks, guardrails: v })} label="Safety guardrails" />
              </div>
            </div>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-ink-3">{menu.guardrails}</p>
          </div>

          <div className="mt-4 border-t border-line pt-4">
            <button type="button" className="btn-primary !h-11 w-full !text-[14px]" disabled={!canRun || busy || n === 0} onClick={onRun} data-testid="opt-run">
              {busy ? "Starting…" : "Find a plan"}
            </button>
            <div className="mt-2 min-h-[32px] text-center text-[11.5px] leading-snug text-ink-3" aria-live="polite">
              {error ? <span className="font-medium text-[#B4232A]">{error}</span> : !canRun ? why : n === 0 ? "Choose at least one measure first." : "Takes about four to five minutes. Every number is simulated."}
            </div>
            {!canRun && onExample && (
              <button type="button" className="btn-primary mt-1 w-full" onClick={onExample} data-testid="opt-example">
                Open the recorded example
              </button>
            )}
            {canRun && onAttach && (
              <button type="button" className="btn-quiet mt-1 w-full" onClick={onAttach} data-testid="opt-attach">
                A search is running now · watch it
              </button>
            )}
          </div>
        </section>

        {headline?.publishable && headline.sentence && <Recommended headline={headline} />}
      </aside>
    </div>
  );
}
