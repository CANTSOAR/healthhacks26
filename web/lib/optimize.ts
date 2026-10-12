// Client for the "optimize for your goals" jobs (server/optimize.py, rl/custom.py). Every number is simulated.
// Kept apart from lib/api.ts; it reuses that file's base-URL helper and snapshot switches.
import { apiBase, BASE_PATH, STATIC_SNAPSHOT } from "./api";
import { money, num, titleCase } from "./format";

export type Direction = "max" | "min";
export interface MenuMetric {
  id: string;
  label: string;
  unit: string;
  natural: Direction;
  proxy: boolean;
}
export interface GoalSpec {
  metric: string;
  direction: Direction;
  rank: number;
}
export interface Preset {
  id: string;
  label: string;
  goals: GoalSpec[];
  guardrails?: boolean;
}
export interface OptMenu {
  metrics: MenuMetric[];
  presets: Preset[];
  ranking: string;
  guardrails: string;
  running: string | null;
}
export interface ObjectiveGoal extends GoalSpec {
  weight: number;
  label: string;
  against_the_grain: boolean;
}
export interface Objective {
  goals: ObjectiveGoal[];
  signed_weights: Record<string, number>;
  guardrails: boolean;
}
export interface HistoryRow {
  gen: number;
  best_score: number;
  baseline_score?: number | null;
  seconds: number;
  best: Record<string, number>;
}
export type Phase = "queued" | "starting" | "searching" | "selecting" | "evaluating" | "done" | "failed";
export interface OptStatus {
  phase: Phase;
  gen?: number;
  gens?: number;
  elapsed_s?: number;
  /** when the status was last written (the server writes it only when the phase or round changes) */
  updated?: string;
  error?: string;
  history?: HistoryRow[];
  objective?: Objective;
}
export interface MetricRow {
  baseline: number;
  policy: number;
  diff: number;
  diff_ci95: [number, number];
  pct: number | null;
  pct_ci95: [number, number] | null;
  reading: "better" | "worse" | "no significant change";
  chosen_weight: number;
}
export interface GuardrailRow {
  metric?: string;
  label: string;
  baseline: number;
  limit: number;
  candidate: number;
  met: boolean;
  status: string;
}
export interface ScenarioResult {
  metrics: Record<string, MetricRow>;
  twins_improved: number;
  n_twins: number;
  guardrails: { all_met: boolean; rows: GuardrailRow[] } | null;
}
export interface StaffingHead {
  values: number[];
  baseline: number[];
  policy: number[];
}
export interface OptResult {
  headline: string;
  objective: Objective;
  picked_baseline: boolean;
  scenarios: Record<string, ScenarioResult>;
  what_changes?: string[];
  staffing?: Record<string, StaffingHead> | null;
  search?: HistoryRow[];
  protocol?: { held_out_seeds?: number[]; days?: number; twins?: number; scenarios?: string[]; search?: { pop?: number; gens?: number; seeds?: number; days?: number }; note?: string };
  menu?: Record<string, Omit<MenuMetric, "id">>;
  generated?: string;
  seconds?: number;
}
export interface OptJob {
  job_id: string;
  spec: { goals: GoalSpec[]; guardrails: boolean; created?: string; created_ts?: number };
  status: OptStatus;
  result?: OptResult | null;
}
export interface JobListItem {
  job_id: string;
  created?: string;
  goals?: GoalSpec[];
  phase?: Phase;
  headline?: string | null;
}
export interface Headline {
  sentence?: string;
  publishable?: boolean;
  hospital_label?: string;
  caveats?: string[];
  /** per-objective tables (rl/headline.py); the landing page and the recommended-plan card read the selected plan's rows */
  objectives?: Record<
    string,
    {
      label?: string;
      selected?: string;
      sentence?: string;
      candidates?: Record<string, Record<string, { metrics?: Record<string, MetricRow>; feasibility?: { feasible?: boolean }; ensemble?: { holds?: number; n_members?: number } }>>;
    }
  >;
}

// The server's sentences were first written in British English and results recorded earlier still are: every string
// that reaches the page goes through this, so old and new results read the same. Values only; keys are left alone.
const US_WORDS: [RegExp, string][] = [
  [/(m)aximis/gi, "$1aximiz"],
  [/(m)inimis/gi, "$1inimiz"],
  [/(o)ptimis/gi, "$1ptimiz"],
  [/(l)abour/gi, "$1abor"],
  [/(c)olour/gi, "$1olor"],
  [/(b)ehaviour/gi, "$1ehavior"],
  [/(f)avour/gi, "$1avor"],
  [/(a)nnualis/gi, "$1nnualiz"],
  [/(n)ormalis/gi, "$1ormaliz"],
  [/(u)tilis/gi, "$1tiliz"],
  [/(p)rioritis/gi, "$1rioritiz"],
  [/(m)odelled/gi, "$1odeled"],
  [/(p)rogramme/gi, "$1rogram"],
  [/\b(c)entre/gi, "$1enter"],
];
export const usText = (s: string) => US_WORDS.reduce((t, [re, to]) => t.replace(re, to), s);
/** usText over every string value of a JSON document. */
export function us<T>(x: T): T {
  if (typeof x === "string") return usText(x) as unknown as T;
  if (Array.isArray(x)) return x.map(us) as unknown as T;
  if (x && typeof x === "object") return Object.fromEntries(Object.entries(x as Record<string, unknown>).map(([k, v]) => [k, us(v)])) as T;
  return x;
}

/** Where what is on screen came from: the server, the bundled sample files, or the recorded static copy of the site. */
export type OptSource = "live" | "fixture" | "snapshot";

export class OptHttpError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(`HTTP ${status}`);
  }
}

async function req<T>(path: string, init?: RequestInit, timeoutMs = 8000): Promise<T> {
  const write = !!init?.method && init.method !== "GET";
  if (STATIC_SNAPSHOT && write) throw new OptHttpError(503, "static copy");
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const url = STATIC_SNAPSHOT ? `${apiBase()}${path.split("?")[0]}.json` : apiBase() + path;
    const res = await fetch(url, STATIC_SNAPSHOT ? { signal: ctl.signal } : { ...init, signal: ctl.signal, cache: "no-store" });
    if (!res.ok) {
      let detail: unknown = null;
      try {
        detail = ((await res.json()) as { detail?: unknown }).detail;
      } catch {
        /* no body */
      }
      throw new OptHttpError(res.status, detail);
    }
    return us((await res.json()) as T);
  } finally {
    clearTimeout(timer);
  }
}
const fixtureFile = async <T,>(file: string): Promise<T> => {
  const r = await fetch(`${BASE_PATH}/fixtures/${file}`);
  if (!r.ok) throw new Error(`missing fixture ${file}`);
  return us((await r.json()) as T);
};

// Used only when the server cannot be asked (offline, or a static copy without a recorded menu). Mirrors server/optimize.py.
const FALLBACK_PRESETS: Preset[] = [
  { id: "margin_first", label: "Profit first, then waits", goals: [{ metric: "profit", direction: "max", rank: 1 }, { metric: "wait", direction: "min", rank: 2 }, { metric: "patient_experience", direction: "max", rank: 3 }] },
  { id: "patients_first", label: "Patients first", goals: [{ metric: "walkouts", direction: "min", rank: 1 }, { metric: "wait", direction: "min", rank: 1 }, { metric: "length_of_stay", direction: "min", rank: 2 }, { metric: "boarding", direction: "min", rank: 3 }] },
  { id: "lean", label: "Leanest staffing that holds service", goals: [{ metric: "labor_cost", direction: "min", rank: 1 }, { metric: "wait_p95", direction: "min", rank: 2 }] },
  { id: "nonsense", label: "Something that makes no sense (longest waits)", goals: [{ metric: "wait", direction: "max", rank: 1 }], guardrails: false },
];
const FALLBACK_RANKING = "Rank 1 is most important. Each rank is worth half the rank above it; ties share a rank. Weights sum to 1.";
const FALLBACK_GUARDRAILS =
  "On: deaths, adverse events and high-acuity waiting no worse than current practice, no extra ambulance diversion, bounded overtime, no extra transfers out. Ambulance diversion and the admission cap are never used as levers.";

/** The recorded example: a real job's status and result, bundled with the app. */
export async function exampleJob(): Promise<OptJob> {
  if (STATIC_SNAPSHOT) {
    try {
      return await req<OptJob>("/api/optimize/example");
    } catch {
      /* not in this snapshot: use the bundled sample */
    }
  }
  const [status, result] = await Promise.all([fixtureFile<OptStatus>("optimize_status.fixture.json"), fixtureFile<OptResult>("optimize_result.fixture.json")]);
  return { job_id: "example", spec: { goals: result.objective.goals.map(({ metric, direction, rank }) => ({ metric, direction, rank })), guardrails: result.objective.guardrails, created: result.generated }, status, result };
}

export const optApi = {
  /** The menu, and whether searches can be run from here. `why` says why not, in words for the page. */
  menu: async (): Promise<{ menu: OptMenu; source: OptSource; why: string | null }> => {
    try {
      const menu = await req<OptMenu>("/api/optimize/menu", undefined, 4000);
      if (STATIC_SNAPSHOT) return { menu: { ...menu, running: null }, source: "snapshot", why: "This is a recorded copy of the app, so new searches cannot be run here. A recorded example is ready to open." };
      return { menu, source: "live", why: null };
    } catch (e) {
      const ex = await exampleJob().catch(() => null);
      const metrics = Object.entries(ex?.result?.menu ?? {}).map(([id, m]) => ({ id, ...m }));
      const menu: OptMenu = { metrics, presets: FALLBACK_PRESETS, ranking: FALLBACK_RANKING, guardrails: FALLBACK_GUARDRAILS, running: null };
      if (STATIC_SNAPSHOT) return { menu, source: "snapshot", why: "This is a recorded copy of the app, so new searches cannot be run here. A recorded example is ready to open." };
      const why = e instanceof OptHttpError ? "The server that answered does not offer the optimizer, so new searches cannot be run here. A recorded example is ready to open." : "The API is unreachable, so new searches cannot be run right now. A recorded example is ready to open.";
      return { menu, source: "fixture", why };
    }
  },
  start: (goals: GoalSpec[], guardrails: boolean) => req<{ job_id: string }>("/api/optimize", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ goals, guardrails }) }, 15000),
  job: (id: string) => req<OptJob>(`/api/optimize/${encodeURIComponent(id)}`, undefined, 10000),
  jobs: async (): Promise<JobListItem[]> => {
    if (STATIC_SNAPSHOT) return [];
    return req<JobListItem[]>("/api/optimize");
  },
  headline: async (hospitalId: string): Promise<Headline | null> => {
    try {
      return await req<Headline>(`/api/headline/${encodeURIComponent(hospitalId)}`, undefined, 5000);
    } catch {
      return null;
    }
  },
};

// ---------------------------------------------------------------- what the user picked

/** `order` lists the active goals from most to least important; `tied[id]` = as important as the one above it. */
export interface Picks {
  dir: Record<string, Direction>;
  order: string[];
  tied: Record<string, boolean>;
  guardrails: boolean;
}
export const EMPTY_PICKS: Picks = { dir: {}, order: [], tied: {}, guardrails: true };

/** Dense ranks (1, 2, 2, 3, …) in list order. */
export function ranksOf(p: Picks): number[] {
  let r = 0;
  return p.order.map((id, i) => (i > 0 && p.tied[id] ? r : ++r));
}
/** Each rank is worth half the one above; normalized to sum to 1 (the same rule as rl/custom.py goal_weights). */
export function weightsOf(p: Picks): number[] {
  const raw = ranksOf(p).map((r) => 0.5 ** (r - 1));
  const tot = raw.reduce((a, b) => a + b, 0) || 1;
  return raw.map((x) => x / tot);
}
export function goalsOf(p: Picks): GoalSpec[] {
  const ranks = ranksOf(p);
  return p.order.map((id, i) => ({ metric: id, direction: p.dir[id], rank: ranks[i] }));
}
export function picksFrom(goals: GoalSpec[], guardrails: boolean): Picks {
  const sorted = goals.map((g, i) => ({ g, i })).sort((a, b) => a.g.rank - b.g.rank || a.i - b.i).map((x) => x.g);
  const p: Picks = { dir: {}, order: [], tied: {}, guardrails };
  sorted.forEach((g, i) => {
    p.dir[g.metric] = g.direction;
    p.order.push(g.metric);
    if (i > 0 && sorted[i - 1].rank === g.rank) p.tied[g.metric] = true;
  });
  return p;
}

const K_PICKS = "hg.opt.picks";
const K_JOB = "hg.opt.job";
export const store = {
  picks: (): Picks | null => {
    try {
      const p = JSON.parse(window.localStorage.getItem(K_PICKS) || "null") as Picks | null;
      return p && Array.isArray(p.order) && p.dir ? { ...EMPTY_PICKS, ...p } : null;
    } catch {
      return null;
    }
  },
  savePicks: (p: Picks) => {
    try {
      window.localStorage.setItem(K_PICKS, JSON.stringify(p));
    } catch {
      /* storage blocked */
    }
  },
  job: (): string | null => {
    try {
      return window.localStorage.getItem(K_JOB);
    } catch {
      return null;
    }
  },
  saveJob: (id: string | null) => {
    try {
      if (id) window.localStorage.setItem(K_JOB, id);
      else window.localStorage.removeItem(K_JOB);
    } catch {
      /* storage blocked */
    }
  },
};

// ---------------------------------------------------------------- metrics

/** Menu metric -> the episode metrics it is built from (rl/custom.py METRIC_MENU[...]["parts"]). */
export const METRIC_PARTS: Record<string, Record<string, number>> = {
  profit: { margin_per_day: 1 },
  revenue: { revenue_per_day: 1 },
  total_cost: { cost_per_day: 1 },
  labor_cost: { labor_cost_per_day: 1 },
  wait: { wait_mean_min: 1 },
  wait_p95: { wait_p95_min: 1 },
  length_of_stay: { ed_los_median_min: 1 },
  walkouts: { lwbs_rate: 1 },
  boarding: { boarding_hours_per_day: 1 },
  deaths: { deaths_per_10k: 1 },
  adverse_events: { adverse_events_per_day: 1 },
  high_acuity_wait: { hi_acuity_wait_hours_per_day: 1 },
  patients_treated: { treated_per_day: 1 },
  overtime: { overtime_hours_per_day: 1 },
  staff_hours: { staff_hours_per_day: 1 },
  patient_experience: { wait_mean_min: 0.4, ed_los_median_min: 0.3, lwbs_rate: 0.3 },
};

/** Groups for the picker, in reading order. A metric the client does not know lands in "Other". */
export const MENU_GROUPS: { title: string; ids: string[] }[] = [
  { title: "Money", ids: ["profit", "revenue", "total_cost", "labor_cost"] },
  { title: "Patients' time", ids: ["wait", "wait_p95", "length_of_stay", "walkouts", "boarding", "patient_experience"] },
  { title: "Safety", ids: ["deaths", "adverse_events", "high_acuity_wait"] },
  { title: "Throughput and staff", ids: ["patients_treated", "overtime", "staff_hours"] },
];

type Fmt = "usd" | "min" | "share" | "num";
/** Episode metrics in plain words. `up` = which way is normally good (null = neither). */
const EP: Record<string, { label: string; fmt: Fmt; unit?: string; good: "up" | "down" | null }> = {
  wait_mean_min: { label: "Mean wait to see a provider", fmt: "min", good: "down" },
  wait_p95_min: { label: "Worst-case wait (95th percentile)", fmt: "min", good: "down" },
  ed_los_median_min: { label: "ED length of stay (median)", fmt: "min", good: "down" },
  ed_los_mean_min: { label: "ED length of stay (mean)", fmt: "min", good: "down" },
  lwbs_rate: { label: "Left without being seen", fmt: "share", good: "down" },
  lwbs_per_day: { label: "Walk-outs", fmt: "num", unit: "per day", good: "down" },
  cost_per_day: { label: "Total cost", fmt: "usd", unit: "per day", good: "down" },
  margin_per_day: { label: "Profit (operating margin)", fmt: "usd", unit: "per day", good: "up" },
  revenue_per_day: { label: "Revenue", fmt: "usd", unit: "per day", good: "up" },
  cost_per_treated: { label: "Cost per patient treated", fmt: "usd", good: "down" },
  labor_cost_per_day: { label: "Labor cost", fmt: "usd", unit: "per day", good: "down" },
  fixed_cost_per_day: { label: "Fixed cost", fmt: "usd", unit: "per day", good: "down" },
  operating_cost_per_day: { label: "Operating cost", fmt: "usd", unit: "per day", good: "down" },
  deaths_per_10k: { label: "Deaths", fmt: "num", unit: "per 10,000 arrivals", good: "down" },
  deaths_per_day: { label: "Deaths", fmt: "num", unit: "per day", good: "down" },
  adverse_events_per_day: { label: "Adverse events", fmt: "num", unit: "per day", good: "down" },
  boarding_hours_per_day: { label: "Boarding (admitted patients held in the ED)", fmt: "num", unit: "patient-hours per day", good: "down" },
  diversion_hours_per_day: { label: "Ambulance diversion", fmt: "num", unit: "hours per day", good: "down" },
  diverted_per_day: { label: "Ambulances diverted", fmt: "num", unit: "per day", good: "down" },
  overtime_hours_per_day: { label: "Staff overtime", fmt: "num", unit: "hours per day", good: "down" },
  staff_hours_per_day: { label: "Staff hours scheduled", fmt: "num", unit: "hours per day", good: "down" },
  hi_acuity_wait_hours_per_day: { label: "Sickest patients (ESI 1-2) waiting", fmt: "num", unit: "patient-hours per day", good: "down" },
  wait_patient_hours_per_day: { label: "Total time patients spend waiting", fmt: "num", unit: "patient-hours per day", good: "down" },
  ed_patient_hours_per_day: { label: "Total time patients spend in the ED", fmt: "num", unit: "patient-hours per day", good: "down" },
  treated_per_day: { label: "Patients treated", fmt: "num", unit: "per day", good: "up" },
  arrivals_per_day: { label: "Arrivals", fmt: "num", unit: "per day", good: null },
  admissions_per_day: { label: "Admissions", fmt: "num", unit: "per day", good: null },
  transfers_per_day: { label: "Transfers out", fmt: "num", unit: "per day", good: "down" },
};
/** The same quantity counted another way: listed once when both moved the same way. */
export const SAME_AS: Record<string, string> = { deaths_per_day: "deaths_per_10k", lwbs_per_day: "lwbs_rate" };

export const epLabel = (k: string) => EP[k]?.label ?? titleCase(k.replace(/_per_day$/, "").replace(/_min$/, ""));
export const epUnit = (k: string) => EP[k]?.unit ?? (k.endsWith("_per_day") && !EP[k] ? "per day" : "");
export function epValue(k: string, v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return "–";
  const f = EP[k]?.fmt ?? (k.endsWith("_min") ? "min" : "num");
  if (f === "usd") return money(v);
  if (f === "share") return `${(v * 100).toFixed(1)}%`;
  const a = Math.abs(v);
  const s = num(v, a >= 100 ? 0 : a >= 10 ? 1 : 2);
  return f === "min" ? `${s} min` : s;
}
export const signedPct = (v: number, digits = 1) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}%`;

export type Verdict = "asked" | "flat" | "against";
/** Did the metric move the way that was asked? Judged on the 95% interval of the paired difference. */
export function verdictFor(row: MetricRow, wantDown: boolean): Verdict {
  const [lo, hi] = row.diff_ci95;
  if (wantDown ? hi < 0 : lo > 0) return "asked";
  if (wantDown ? lo > 0 : hi < 0) return "against";
  return "flat";
}
/** better / worse / flat for a metric nobody asked about. The usual good direction is the client's table (which follows
 * the menu's "natural" direction); for a metric it does not know, the server's own reading is used. */
export function readingFor(k: string, row: MetricRow): "better" | "worse" | "flat" | "changed" {
  const good = EP[k]?.good;
  const [lo, hi] = row.diff_ci95;
  if (good === undefined) return row.reading === "better" ? "better" : row.reading === "worse" ? "worse" : "flat";
  if (!(hi < 0 || lo > 0)) return "flat";
  if (good === null) return "changed";
  return (good === "down") === hi < 0 ? "better" : "worse";
}

export const SCENARIO_LABEL: Record<string, string> = { normal_week: "Normal operations", flu_surge: "Flu surge", nursing_absences: "Nursing absences" };
export const scenarioLabel = (id: string) => SCENARIO_LABEL[id] ?? titleCase(id);

/** "Patient experience (proxy: wait, …)" -> ["Patient experience", "proxy: wait, …"] */
export function splitLabel(label: string): [string, string | null] {
  const m = label.match(/^(.*?)\s*\((.*)\)\s*$/);
  return m ? [m[1], m[2]] : [label, null];
}
/** "Door-to-provider wait" -> "door-to-provider wait", but "ED length of stay" stays as it is. */
export const lowerFirst = (s: string) => (/^[A-Z][a-z]/.test(s) ? s.charAt(0).toLowerCase() + s.slice(1) : s);
/** Server timestamps look like 2026-10-10T23:27:56-0400; browsers want the offset with a colon. */
export const parseStamp = (iso?: string | null) => (iso ? new Date(iso.replace(/([+-]\d{2})(\d{2})$/, "$1:$2")).getTime() : NaN);
export const dirWord = (d: Direction) => (d === "max" ? "Maximize" : "Minimize");

/** Mean people on a shift = sum over levels of (share of days at that level × people at that level). */
export const meanPeople = (h: StaffingHead, which: "baseline" | "policy") => h.values.reduce((s, v, i) => s + v * (h[which][i] ?? 0), 0);

/** Menu metrics whose parts fall when the metric improves (mirrors `invert` in rl/custom.py): asking to maximize
 *  patient experience means asking for shorter waits and stays and fewer walk-outs. */
export const INVERTED: Record<string, boolean> = { patient_experience: true };
/** True when the goal asks for its underlying episode metrics to go DOWN. */
export const wantsDown = (g: { metric: string; direction: string }) => (g.direction === "min") !== !!INVERTED[g.metric];
