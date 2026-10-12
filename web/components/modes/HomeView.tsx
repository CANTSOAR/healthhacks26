"use client";
// The landing page: what this is, how it works, what it has found so far (all simulated), and where to go next.
import { useEffect, useState, type ReactNode } from "react";
import { loadHomeFacts, pctText, RECORDED, type FactSource, type HomeFacts } from "@/lib/home";
import { useUI, type Mode } from "@/lib/ui";
import { Icon, ICONS } from "../ui/atoms";
import { SiteDisclaimer } from "../ui/SiteDisclaimer";

const GOOD = "#11734B";
const BAD = "#B4232A";

function SourceTag({ source }: { source: FactSource }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="sim-tag">simulated</span>
      <span className="sim-tag w-[62px] justify-center" title={source === "live" ? "Read from the API just now" : "Values recorded when this page was written; the API did not supply them just now"}>
        {source === "live" ? "live" : "recorded"}
      </span>
    </span>
  );
}

function Section({ id, eyebrow, title, lead, children }: { id: string; eyebrow: string; title: string; lead?: ReactNode; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-5">
      <div className="max-w-[720px] px-1">
        <div className="eyebrow !text-accent-dark">{eyebrow}</div>
        <h2 id={id} className="mt-1.5 text-[24px] font-semibold leading-tight tracking-[-0.02em] text-ink min-[700px]:text-[28px]">
          {title}
        </h2>
        {lead && <p className="mt-2 text-[14.5px] leading-relaxed text-ink-2">{lead}</p>}
      </div>
      {children}
    </section>
  );
}

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`glass-solid p-5 min-[700px]:p-6 ${className}`}>{children}</div>;
}

function CardHead({ title, sub, source }: { title: string; sub: string; source: FactSource }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
      <div className="min-w-0 max-w-[640px]">
        <h3 className="text-[16.5px] font-semibold tracking-[-0.01em] text-ink">{title}</h3>
        <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{sub}</p>
      </div>
      <SourceTag source={source} />
    </div>
  );
}

/** One figure. Fixed height, so a live value replacing a recorded one never moves the page. */
function Stat({ label, value, note, tone }: { label: string; value: string; note: string; tone?: "good" | "bad" }) {
  return (
    <div className="flex h-[112px] flex-col justify-between rounded-2xl border border-line bg-white/85 px-4 py-3.5">
      <div className="text-[12px] font-semibold leading-snug text-ink-2">{label}</div>
      <div>
        <div className="tnum text-[26px] font-semibold leading-none tracking-[-0.02em]" style={{ color: tone === "good" ? GOOD : tone === "bad" ? BAD : "#141A33" }}>
          {value}
        </div>
        <div className="tnum mt-1.5 truncate text-[11.5px] text-ink-3">{note}</div>
      </div>
    </div>
  );
}

const STEPS: { n: number; title: string; body: string }[] = [
  {
    n: 1,
    title: "Twin",
    body: "A working model of the emergency department, built from public data alone: the ED times the hospital reports to CMS, its volumes, beds and costs, and its clinician roster by specialty. It is calibrated until its baseline reproduces the hospital's own published figures.",
  },
  {
    n: 2,
    title: "Simulate",
    body: "Every patient, staff member, bay and scanner is in the model. It runs thousands of hospital-days in minutes, so a plan can be tried on many versions of the same week before anyone is asked to work it.",
  },
  {
    n: 3,
    title: "Optimize",
    body: "You choose what matters. The system searches staffing and capacity plans, then shows what it found, including what that cost elsewhere.",
  },
];

const PAGES: { mode: Mode; title: string; body: string; cta: string }[] = [
  { mode: "optimize", title: "Optimize", body: "Pick the measures you care about and rank them. Watch the search run, then read the plan it found and the trade-offs that came with it.", cta: "Pick a goal" },
  { mode: "play", title: "Play", body: "Run the hospital yourself, hour by hour. Set staffing, open overflow, call people in, throw a surge at it, or hand the controls to a plan and take them back.", cta: "Run the hospital" },
  { mode: "watch", title: "Watch", body: "Replay a recorded 30-day run in the 3D hospital and see each staffing and capacity decision as it happens.", cta: "Watch a run" },
  { mode: "compare", title: "Compare", body: "Two plans side by side, facing the same patients, with the totals and the difference between them.", cta: "Compare two plans" },
  { mode: "tradeoff", title: "Trade-off", body: "Every plan on one chart, cost against wait. Switch to Resources to see what one more provider, nurse, bay or scanner is worth.", cta: "See the trade-off" },
  { mode: "watch", title: "The inspector", body: "In any 3D view, click a patient, a staff member, a bed or a scanner to see its state and where every number behind it comes from.", cta: "Open the hospital" },
];

export function HomeView({ narrow, top, onMode }: { narrow: boolean; top: ReactNode; onMode: (m: Mode) => void }) {
  const hospitalId = useUI((s) => s.hospitalId);
  const online = useUI((s) => s.online);
  const [facts, setFacts] = useState<HomeFacts>(RECORDED);
  useEffect(() => {
    let dead = false;
    loadHomeFacts(hospitalId, (patch) => !dead && setFacts((f) => ({ ...f, ...patch })));
    return () => {
      dead = true;
    };
    // `online` flips when the API comes back: ask again then
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hospitalId, online === false]);
  const { calibration: cal, plan, ask } = facts;

  return (
    <div className="fixed inset-0 flex flex-col gap-3 p-2 min-[901px]:p-3" data-testid="home">
      {top}
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto [scrollbar-gutter:stable]">
        <div className="mx-auto flex w-full max-w-[1120px] flex-col gap-14 px-2 pb-12 pt-6 min-[700px]:gap-20 min-[700px]:px-4 min-[700px]:pt-12">
          {/* hero */}
          <header className="grid items-center gap-8 min-[1000px]:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
            <div>
              <div className="eyebrow !text-accent-dark">Twin · simulate · optimize</div>
              <h1 className="mt-3 text-[34px] font-semibold leading-[1.08] tracking-[-0.03em] text-ink min-[700px]:text-[46px]">A digital twin of the emergency department, built to find better plans.</h1>
              <p className="mt-4 max-w-[60ch] text-[15.5px] leading-relaxed text-ink-2">
                HospitalGym builds a working model of a hospital&rsquo;s emergency department from public data, runs it thousands of times, and searches for staffing and capacity plans that do better on whatever you choose. It is the twin, simulate, optimize loop used for warehouses, applied to a
                hospital.
              </p>
              <div className="mt-6 flex flex-wrap gap-2.5">
                <button type="button" className="btn-primary !h-11 !px-5 !text-[14px]" onClick={() => onMode("optimize")} data-testid="home-cta-optimize">
                  Pick a goal and watch it optimize
                  <Icon d={ICONS.chevron} size={14} stroke={2.4} />
                </button>
                <button type="button" className="btn-quiet !h-11 !px-5 !text-[14px]" onClick={() => onMode("watch")} data-testid="home-cta-watch">
                  See the hospital
                </button>
              </div>
              <p className="mt-5 max-w-[62ch] text-[12.5px] leading-relaxed text-ink-3">
                First hospital: Robert Wood Johnson University Hospital, New Brunswick. This is a model built from public data. It is not affiliated with or endorsed by the hospital, and everything shown is simulated.
              </p>
            </div>
            <Card className="!p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="eyebrow">Recommended plan vs. current practice</div>
                <span className="sim-tag">simulated</span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                {(
                  [
                    ["Wait to see a provider", plan.wait],
                    ["Boarding hours", plan.boarding],
                    ["Labor cost", plan.labor],
                  ] as [string, number][]
                ).map(([label, v]) => (
                  <div key={label} className="rounded-xl bg-[#141a33]/[0.035] px-3 py-3">
                    <div className="tnum text-[22px] font-semibold leading-none tracking-[-0.02em] min-[700px]:text-[24px]" style={{ color: GOOD }}>
                      {pctText(v)}
                    </div>
                    <div className="mt-1.5 text-[11.5px] leading-snug text-ink-2">{label}</div>
                  </div>
                ))}
              </div>
              <p className="mt-3.5 text-[13px] leading-relaxed text-ink-2">
                It sets the scheduling and capacity scaffolding: staff per shift, when fast track and overflow open, call-in triggers, discharge-round timing. <span className="font-semibold text-ink">Clinicians stay focused on patients. It never makes a clinical decision.</span>
              </p>
            </Card>
          </header>

          {/* how it works */}
          <Section id="home-how" eyebrow="How it works" title="Three steps, each one visible">
            <ol className="grid gap-4 min-[860px]:grid-cols-3">
              {STEPS.map((s) => (
                <li key={s.n} className="glass-solid p-5 min-[700px]:p-6">
                  <span className="tnum flex h-8 w-8 items-center justify-center rounded-full bg-accent text-[14px] font-bold text-white shadow-pill">{s.n}</span>
                  <h3 className="mt-3.5 text-[18px] font-semibold tracking-[-0.01em] text-ink">{s.title}</h3>
                  <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-2">{s.body}</p>
                </li>
              ))}
            </ol>
          </Section>

          {/* results */}
          <Section id="home-results" eyebrow="Results so far · simulated" title="What the twin has shown" lead="Every number here comes from the simulation, not from the hospital's own operational data. Each one can be opened and checked in the app.">
            <Card>
              <CardHead title="The twin matches the public record" sub={`Its baseline, on fresh simulated days it was not fitted to, beside the hospital's own published figures. It holds steady over ${cal.days} simulated days.`} source={cal.source} />
              <div className="mt-4 grid gap-3 min-[720px]:grid-cols-3">
                <Stat label="Median ED time, discharged patients" value={`${Math.round(cal.losTwin)} min`} note={`published: ${Math.round(cal.losPublished)} min`} />
                <Stat label="Left without being seen" value={`${(cal.lwbsTwin * 100).toFixed(2)}%`} note={`published: ${+(cal.lwbsPublished * 100).toFixed(1)}%`} />
                <Stat label="Arrivals per day" value={`${Math.round(cal.arrivalsTwin)}`} note={`published: ${Math.round(cal.arrivalsPublished)}`} />
              </div>
            </Card>

            <Card>
              <CardHead title="Recommended plan: same budget, better flow" sub="The plan the system recommends for this hospital, compared with current practice on the same simulated patients over a normal week." source={plan.source} />
              <div className="mt-4 grid grid-cols-2 gap-3 min-[720px]:grid-cols-3 min-[1000px]:grid-cols-5">
                <Stat label="Mean wait to see a provider" value={pctText(plan.wait)} note={`95% CI ${plan.waitCi[0].toFixed(1)} to ${plan.waitCi[1].toFixed(1)}`} tone="good" />
                <Stat label="Walk-outs" value={pctText(plan.walkouts)} note="left without being seen" tone="good" />
                <Stat label="Median length of stay" value={pctText(plan.los)} note="in the ED" tone="good" />
                <Stat label="Boarding hours" value={pctText(plan.boarding)} note="held in the ED" tone="good" />
                <Stat label="Labor cost" value={pctText(plan.labor)} note="within budget" tone={plan.labor <= 0 ? "good" : undefined} />
              </div>
              <div className="mt-3.5 flex flex-wrap gap-2">
                <span className="chip !px-2.5 !py-[3px] !text-[11.5px]" style={plan.allConstraintsMet ? { background: "#DFF5EA", color: GOOD } : { background: "#FDEFD8", color: "#8A5A00" }}>
                  {plan.allConstraintsMet ? "Every safety constraint met" : "Not every safety constraint met"}
                </span>
                <span className="chip border border-line bg-white/80 !px-2.5 !py-[3px] !text-[11.5px] text-ink-2">
                  Holds in <b className="tnum mx-1 font-bold text-ink">{plan.holds} of {plan.twins}</b> twins
                </span>
              </div>
              <p className="mt-2.5 text-[12px] leading-relaxed text-ink-3">A twin is one version of the model that the public record cannot tell apart from the others. The plan was tested in each of them.</p>
            </Card>

            <div className="grid gap-4 min-[860px]:grid-cols-2">
              <Card>
                <CardHead title="Ask for anything" sub="Two searches that were actually run. The system follows whatever goal it is given, so the goal is yours to choose." source={ask.source} />
                <div className="mt-4 flex flex-col gap-3">
                  <div className="rounded-2xl border border-line bg-white/85 p-4">
                    <div className="text-[13px] font-semibold text-ink">&ldquo;Profit first, then waits&rdquo;</div>
                    <div className="tnum mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-ink-2">
                      <span>
                        profit <b style={{ color: GOOD }}>{pctText(ask.profit.profit)}</b>
                      </span>
                      <span>
                        wait <b style={{ color: GOOD }}>{pctText(ask.profit.wait, 0)}</b>
                      </span>
                      <span>
                        walk-outs <b style={{ color: GOOD }}>{pctText(ask.profit.walkouts)}</b>
                      </span>
                    </div>
                    <div className="tnum mt-1.5 text-[11.5px] text-ink-3">Found in about {ask.profit.minutes.toFixed(1)} minutes.</div>
                  </div>
                  <div className="rounded-2xl border border-line bg-white/85 p-4">
                    <div className="text-[13px] font-semibold text-ink">&ldquo;Maximize waiting&rdquo;, deliberately nonsensical</div>
                    <div className="tnum mt-2 text-[13px] text-ink-2">
                      wait <b style={{ color: BAD }}>{pctText(ask.nonsense.wait, 0)}</b>
                    </div>
                    <div className="tnum mt-1.5 text-[11.5px] text-ink-3">
                      It cut providers on the day shift from {ask.nonsense.providersFrom} to {ask.nonsense.providersTo}.{ask.nonsense.guardrailsOff ? " Safety guardrails were switched off for this one." : ""}
                    </div>
                  </div>
                </div>
              </Card>

              <Card>
                <CardHead title="What each resource is worth" sub="The twin is run with and without one unit at a time, on the same simulated patients." source="recorded" />
                <ul className="mt-4 flex flex-col gap-3">
                  {[
                    ["Night provider", "Removing one night provider adds 6.6 minutes to the median stay."],
                    ["Triage station", "A triage station is the most valuable single unit in a normal week."],
                    ["Fast track", "Closing fast track helps on a normal week, but hurts in a flu surge."],
                  ].map(([k, text]) => (
                    <li key={k} className="rounded-2xl border border-line bg-white/85 p-4">
                      <div className="text-[13px] font-semibold text-ink">{k}</div>
                      <div className="mt-1 text-[13px] leading-relaxed text-ink-2">{text}</div>
                    </li>
                  ))}
                </ul>
                <button type="button" className="btn-quiet mt-4" onClick={() => onMode("tradeoff")}>
                  See every resource in Trade-off
                </button>
              </Card>
            </div>
          </Section>

          {/* pages */}
          <Section id="home-pages" eyebrow="Find your way around" title="What each page does">
            <div className="grid gap-4 min-[640px]:grid-cols-2 min-[1000px]:grid-cols-3">
              {PAGES.map((p) => (
                <div key={p.title} className="glass-solid flex flex-col p-5 min-[700px]:p-6">
                  <h3 className="text-[17px] font-semibold tracking-[-0.01em] text-ink">{p.title}</h3>
                  <p className="mt-1.5 flex-1 text-[13.5px] leading-relaxed text-ink-2">{p.body}</p>
                  <button type="button" className={`${p.mode === "optimize" ? "btn-primary" : "btn-quiet"} mt-4 self-start`} onClick={() => onMode(p.mode)} data-home-page={p.title}>
                    {p.cta}
                    <Icon d={ICONS.chevron} size={12} stroke={2.4} />
                  </button>
                </div>
              ))}
            </div>
          </Section>

          {/* honesty */}
          <section aria-labelledby="home-honest" className="rounded-2xl border border-accent/15 bg-accent-soft/70 p-5 min-[700px]:p-7">
            <h2 id="home-honest" className="text-[20px] font-semibold tracking-[-0.015em] text-accent-dark">
              What this is and isn&rsquo;t
            </h2>
            <ul className={`mt-3.5 grid gap-x-8 gap-y-3 text-[13.5px] leading-relaxed text-ink-2 ${narrow ? "" : "grid-cols-2"}`}>
              {[
                ["Built from public aggregates.", "Published ED times, volumes, bed counts, costs and the clinician roster by specialty. No patient records and no internal hospital data."],
                ["Staffing schedules are fitted.", "Current practice here is our reconstruction from public figures, not the hospital's real roster."],
                ["Simulated results.", "Nothing has been validated on operational data, and no number is a forecast of what would happen in the real department."],
                ["Sharper with real data.", "With the hospital's own timestamps and rosters, the same pipeline refits the twin and reruns every result."],
              ].map(([lead, rest]) => (
                <li key={lead} className="flex gap-2.5">
                  <span className="mt-[8px] h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                  <span>
                    <b className="font-semibold text-ink">{lead}</b> {rest}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <SiteDisclaimer />
        </div>
      </div>
    </div>
  );
}
