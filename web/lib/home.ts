// Numbers for the landing page. Every figure is SIMULATED. Each group starts from the values recorded when the page
// was written (RECORDED below) and is replaced by what the API returns when it answers, so the page reads the same
// with or without a server and nothing moves when the live values land.
import { apiBase, STATIC_SNAPSHOT } from "./api";
import { meanPeople, us, type Headline, type JobListItem, type OptJob } from "./optimize";

export type FactSource = "live" | "recorded";

export interface HomeFacts {
  /** The twin's baseline beside the hospital's published figures. The twin side is the recorded calibration check. */
  calibration: {
    losTwin: number;
    losPublished: number;
    lwbsTwin: number;
    lwbsPublished: number;
    arrivalsTwin: number;
    arrivalsPublished: number;
    days: number;
    /** where the published side came from */
    source: FactSource;
  };
  /** The recommended plan ("same budget, better flow") against current practice, percent changes. */
  plan: {
    wait: number;
    waitCi: [number, number];
    walkouts: number;
    los: number;
    boarding: number;
    labor: number;
    allConstraintsMet: boolean;
    holds: number;
    twins: number;
    source: FactSource;
  };
  /** Two searches that were actually run: a sensible goal and a deliberately nonsensical one. */
  ask: {
    profit: { profit: number; wait: number; walkouts: number; minutes: number };
    nonsense: { wait: number; providersFrom: number; providersTo: number; guardrailsOff: boolean };
    source: FactSource;
  };
}

export const RECORDED: HomeFacts = {
  calibration: { losTwin: 203, losPublished: 206, lwbsTwin: 0.0091, lwbsPublished: 0.01, arrivalsTwin: 222, arrivalsPublished: 222, days: 60, source: "recorded" },
  plan: { wait: -17.0, waitCi: [9.1, 26.2], walkouts: -14.6, los: -4.5, boarding: -59.6, labor: -4.0, allConstraintsMet: true, holds: 20, twins: 24, source: "recorded" },
  ask: { profit: { profit: 1.8, wait: -29.0, walkouts: -24.5, minutes: 4.5 }, nonsense: { wait: 3074, providersFrom: 15, providersTo: 5, guardrailsOff: true }, source: "recorded" },
};

async function getJson<T>(path: string, timeoutMs = 6000): Promise<T> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const url = STATIC_SNAPSHOT ? `${apiBase()}${path.split("?")[0]}.json` : apiBase() + path;
    const res = await fetch(url, STATIC_SNAPSHOT ? { signal: ctl.signal } : { signal: ctl.signal, cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return us((await res.json()) as T);
  } finally {
    clearTimeout(timer);
  }
}
const finite = (...v: unknown[]) => v.every((x) => typeof x === "number" && isFinite(x));

/** The selected "same budget, better flow" plan's figures for a normal week, from /api/headline/{hospital}. */
export function planFromHeadline(h: Headline | null | undefined): HomeFacts["plan"] | null {
  if (!h || h.publishable === false) return null;
  const o = h.objectives?.same_budget_better_flow;
  const c = o?.selected ? o.candidates?.[o.selected]?.normal_week : undefined;
  const m = c?.metrics;
  const w = m?.wait_mean_min;
  if (!m || !w?.pct_ci95) return null;
  const pct = (k: string) => m[k]?.pct as number;
  const ci = w.pct_ci95.map(Math.abs).sort((a, b) => a - b) as [number, number];
  const plan: HomeFacts["plan"] = {
    wait: w.pct as number,
    waitCi: ci,
    walkouts: pct("lwbs_rate"),
    los: pct("ed_los_median_min"),
    boarding: pct("boarding_hours_per_day"),
    labor: pct("labor_cost_per_day"),
    allConstraintsMet: c?.feasibility?.feasible === true,
    holds: c?.ensemble?.holds as number,
    twins: c?.ensemble?.n_members as number,
    source: "live",
  };
  return finite(plan.wait, plan.walkouts, plan.los, plan.boarding, plan.labor, plan.holds, plan.twins) ? plan : null;
}
const livePlan = async (hospitalId: string) => planFromHeadline(await getJson<Headline>(`/api/headline/${encodeURIComponent(hospitalId)}`));

async function liveCalibration(): Promise<HomeFacts["calibration"] | null> {
  const v = await getJson<{ targets?: { name: string; value: number | null }[] }>("/api/validation");
  const t = (name: string) => v.targets?.find((x) => x.name === name)?.value;
  const los = t("median_ed_time_discharged_min");
  const lwbs = t("lwbs_rate");
  const visits = t("ed_visits_per_year");
  if (!finite(los, lwbs, visits)) return null;
  // the published volume is a 2024 (leap-year) count
  return { ...RECORDED.calibration, losPublished: los as number, lwbsPublished: lwbs as number, arrivalsPublished: Math.round((visits as number) / 366), source: "live" };
}

async function liveAsk(): Promise<HomeFacts["ask"] | null> {
  if (STATIC_SNAPSHOT) return null;
  const jobs = (await getJson<JobListItem[]>("/api/optimize")).filter((j) => j.phase === "done");
  const top = (j: JobListItem) => (j.goals ?? []).slice().sort((a, b) => a.rank - b.rank);
  const profitJob = jobs.find((j) => {
    const g = top(j);
    return g[0]?.metric === "profit" && g[0].direction === "max" && g.some((x) => x.metric === "wait" && x.direction === "min");
  });
  const nonsenseJob = jobs.find((j) => j.goals?.length === 1 && j.goals[0].metric === "wait" && j.goals[0].direction === "max");
  if (!profitJob || !nonsenseJob) return null;
  const [a, b] = await Promise.all([profitJob, nonsenseJob].map((j) => getJson<OptJob>(`/api/optimize/${encodeURIComponent(j.job_id)}`, 10000)));
  const ma = a.result?.scenarios?.normal_week?.metrics;
  const mb = b.result?.scenarios?.normal_week?.metrics;
  const md = b.result?.staffing?.md_day;
  if (!ma || !mb || !md || !a.result?.seconds) return null;
  const ask: HomeFacts["ask"] = {
    profit: { profit: ma.margin_per_day?.pct as number, wait: ma.wait_mean_min?.pct as number, walkouts: ma.lwbs_rate?.pct as number, minutes: a.result.seconds / 60 },
    nonsense: { wait: mb.wait_mean_min?.pct as number, providersFrom: Math.round(meanPeople(md, "baseline")), providersTo: Math.round(meanPeople(md, "policy")), guardrailsOff: b.spec?.guardrails === false },
    source: "live",
  };
  return finite(ask.profit.profit, ask.profit.wait, ask.profit.walkouts, ask.nonsense.wait) && ask.profit.profit > 0 && ask.profit.wait < 0 && ask.nonsense.wait > 0 ? ask : null;
}

/** Ask the API for each group; a group that cannot be read keeps its recorded values. */
export function loadHomeFacts(hospitalId: string, onPart: (patch: Partial<HomeFacts>) => void): void {
  void livePlan(hospitalId).then((plan) => plan && onPart({ plan }), () => undefined);
  void liveCalibration().then((calibration) => calibration && onPart({ calibration }), () => undefined);
  void liveAsk().then((ask) => ask && onPart({ ask }), () => undefined);
}

/** "−17.0%", "+3,074%" */
export function pctText(v: number, digits = 1): string {
  const a = Math.abs(v);
  const d = a >= 100 ? 0 : digits;
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${a.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}%`;
}
