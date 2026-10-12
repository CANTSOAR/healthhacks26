// What may be said about a manager, and no more. Every number in these sentences is read from the results table the
// server sends (`/api/results`: `rows`, `comparisons`, `protocol`) and the manager list (`/api/managers`); nothing is
// typed in here. When the data is missing, nothing is said.
import { kindInfo } from "./palette";
import { useUI } from "./ui";
import type { ManagerInfo, ResultRow, Results } from "./types";

type Named = { id?: string; manager_id?: string; label: string; kind?: string; objective?: string | null; note?: string; weight_conditioned?: boolean; reward_weights?: Record<string, number> | null };

const text = (v: unknown): string => {
  if (!v) return "";
  if (typeof v === "string") return v.trim();
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    return (["note", "description", "summary", "method"].map((k) => o[k]).find((x) => typeof x === "string") as string | undefined)?.trim() ?? "";
  }
  return "";
};

const state = () => useUI.getState();
const managerOf = (id: string) => state().managers.find((x) => x.id === id) as (ManagerInfo & Record<string, unknown>) | undefined;
const rowOf = (id: string, scenario: string, results: Results | null = state().results): ResultRow | undefined => results?.rows.find((r) => r.manager_id === id && r.scenario === scenario);
const kindOf = (id: string) => managerOf(id)?.kind ?? state().results?.rows.find((r) => r.manager_id === id)?.kind;

/** How the manager was made, in the server's words (`note`, `training` or `description` on the manager or its result row). */
export function managerNote(id: string): string {
  const m = managerOf(id);
  const row = state().results?.rows.find((r) => r.manager_id === id) as Record<string, unknown> | undefined;
  return text(m?.note) || text(m?.training) || text(m?.description) || text(row?.note) || text(row?.training) || "";
}

// ------------------------------------------------------------------ names

/** Objective ids in two or three words, distinguishing part of a manager's name. */
const OBJECTIVE_SHORT: Record<string, string> = {
  min_cost: "Lowest cost",
  min_wait: "Shortest wait",
  max_margin: "Best margin",
  balanced: "Balanced",
  "cost_s.t._p95_wait": "Cost within wait limit",
  cost_p95: "Cost within wait limit",
  same_budget_better_flow: "Same budget, better flow",
  same_service_lower_cost: "Same service, lower cost",
};
const OBJECTIVE_WORDS: Record<string, string> = { min_cost: "lowest cost", min_wait: "shortest waits", max_margin: "best margin", balanced: "balanced", "cost_s.t._p95_wait": "lowest cost within a wait limit", cost_p95: "lowest cost within a wait limit" };
const WEIGHT_WORD: Record<string, string> = { labor: "staffing cost", cost: "total cost", revenue: "revenue", wait: "waits", lwbs: "walk-outs", safety: "safety", boarding: "boarding", staff: "staff strain" };

const hasObjective = (o?: string | null): o is string => !!o && o !== "none";
const objectiveOfLabel = (label: string) => /(?::\s*|\bat\s+)([a-z0-9_.]+)(?:\s+weights)?\s*$/i.exec(label.replace(/\s*\[fixture\]$/, ""))?.[1];
const titleish = (s: string) => s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** How a learned manager was trained, from its own label and note (never from its id). */
function method(m: Named): "scratch" | "conditioned" | "cloned" | "ppo" | "" {
  if (m.kind !== "learned") return "";
  const s = `${m.label} ${m.note ?? ""}`;
  if (m.weight_conditioned || /weight-conditioned|conditioned on the reward weights/i.test(s)) return "conditioned";
  if (/from scratch|no behaviou?r cloning/i.test(s)) return "scratch";
  if (/clon/i.test(s)) return "cloned";
  return "ppo";
}
const METHOD_SHORT = { scratch: "PPO from scratch", conditioned: "PPO conditioned", cloned: "PPO cloned", ppo: "PPO", "": "" } as const;

/**
 * A short display name with the distinguishing part first: "Lowest cost · PPO cloned", "Shortest wait · tuned
 * heuristic", "Lowest cost · PPO from scratch", "Cost dial · PPO conditioned". Server labels differ only at their
 * end ("Learned (PPO, cloned from tuned heuristic then fine-tuned): min_cost"), so truncating them loses the name.
 */
export function shortManager(m: Named | null | undefined): string {
  if (!m) return "";
  const fixture = /\[fixture\]$/.test(m.label) ? " [fixture]" : "";
  const obj = hasObjective(m.objective) ? m.objective : objectiveOfLabel(m.label);
  const what = obj ? (OBJECTIVE_SHORT[obj] ?? titleish(obj)) : "";
  if (m.kind === "learned") {
    const how = METHOD_SHORT[method(m)];
    if (method(m) === "conditioned") return `${what ? `${what} dial` : "Any-objective dial"} · ${how}${fixture}`.replace("Lowest cost dial", "Cost dial").replace("Shortest wait dial", "Wait dial").replace("Best margin dial", "Margin dial");
    return `${what || "Learned"} · ${how}${fixture}`;
  }
  if (m.kind === "tuned_heuristic") return `${what || "Tuned"} · tuned plan${fixture}`;
  if (m.kind === "fixed") return `Current practice${fixture}`;
  if (m.kind === "rule_based") return `Rule-based${fixture}`;
  if (m.kind === "random") return `Random${fixture}`;
  if (m.kind === "human") return "You";
  return prettyManager(m.label) + fixture;
}
/** Short name for a manager id, looked up in the manager list and then the results rows. */
export function shortManagerById(id: string): string {
  const m = managerOf(id) ?? state().results?.rows.find((r) => r.manager_id === id);
  return m ? shortManager(m as Named) : id;
}
/** The full server label with objective ids put into words: for `title` attributes and option text. */
export function prettyManager(label: string): string {
  return label
    .replace(/\s*\[fixture\]$/, "")
    .replace(/:\s*([a-z0-9_.]+)$/i, (m, k: string) => (OBJECTIVE_WORDS[k] ? `: ${OBJECTIVE_WORDS[k]}` : m))
    .replace(/\bat ([a-z0-9_.]+) weights$/i, (m, k: string) => (OBJECTIVE_WORDS[k] ? `at ${OBJECTIVE_WORDS[k]} weights` : m));
}
export const fullManager = (m: Named) => prettyManager(m.label);
/** The short name with its kind where the name does not already say it. */
export const namedManager = (m: ManagerInfo) => (m.kind === "learned" ? `${shortManager(m)} (a learned agent)` : m.kind === "tuned_heuristic" || m.kind === "human" || m.kind === "fixed" ? shortManager(m) : `${shortManager(m)} (${kindInfo(m.kind).label.toLowerCase()} baseline)`);

// ------------------------------------------------------------------ what it was asked to do

/** The objective in plain words, from the reward weights the server lists for it. */
export function objectiveWords(m: Named | undefined, results: Results | null = state().results): string {
  if (!m) return "";
  const obj = hasObjective(m.objective) ? m.objective : "";
  const proto = (results?.protocol ?? {}) as { objectives?: Record<string, Record<string, number>>; p95_wait_threshold_min?: number };
  const w = Object.entries((obj && proto.objectives?.[obj]) || m.reward_weights || {}).filter(([, v]) => Number(v) > 0);
  if (!w.length) return "";
  const names = w.map(([k]) => WEIGHT_WORD[k] ?? k.replace(/_/g, " "));
  const list = names.length === 1 ? `${names[0]} only` : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  const limit = /p95|s\.t\./.test(obj) ? ` while keeping the 95th-percentile wait under ${proto.p95_wait_threshold_min != null ? `${proto.p95_wait_threshold_min} min` : "a limit"}` : "";
  return limit ? list.replace(/ only$/, "") + limit : list;
}
/** The same objective as the thing a score is "on": "staffing cost alone", "waits and walk-outs". */
const scoreWords = (m: Named | undefined, results?: Results | null) => objectiveWords(m, results).replace(/ only$/, " alone");

function trainingWords(m: Named): string {
  const how = method(m);
  if (how === "scratch") return "trained from scratch";
  if (how === "conditioned") return "one network that is told the objective weights, cloned from the tuned plans then fine-tuned";
  if (how === "cloned") return "cloned from the tuned plan, then fine-tuned";
  return "";
}

// ------------------------------------------------------------------ the held-out verdict, with what it cost

const signed = (v: number) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(3)}`;
const mins = (v: number) => `${v >= 100 ? Math.round(v) : +v.toFixed(1)} min`;
const pct = (v: number) => `${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`;
/** Below this absolute difference in score the two are called the same, whatever the significance test says. */
const SAME = 0.01;

type Cmp = NonNullable<Results["comparisons"]>[number] & { paired_diff?: { mean?: number; ci95?: number } };
function comparison(id: string, scenario: string): Cmp | undefined {
  const cmp = state().results?.comparisons;
  if (!Array.isArray(cmp)) return undefined;
  return (cmp as Cmp[]).find((x) => x.a === id && x.scenario === scenario && kindOf(x.b) === "tuned_heuristic");
}

/** "mean wait 695 min (heuristic 131 min), 31% left unseen (8.7%), 94 deaths per 10k (16)" from the two result rows. */
function price(a: ResultRow | undefined, b: ResultRow | undefined): { text: string; worse: boolean } | null {
  if (!a) return null;
  const A = a.metrics;
  const B = b?.metrics;
  const parts: string[] = [];
  let worse = false;
  const item = (key: string, f: (v: number) => string, lead: (s: string) => string, tolerance: number) => {
    if (A[key]?.mean == null) return;
    const va = A[key].mean;
    const vb = B?.[key]?.mean;
    parts.push(lead(f(va)) + (vb != null ? ` (tuned plan ${f(vb)})` : ""));
    if (vb != null && va > vb * 1.1 && va - vb > tolerance) worse = true;
  };
  item("wait_mean_min", mins, (s) => `mean wait ${s}`, 5);
  item("lwbs_rate", pct, (s) => `${s} leaving unseen`, 0.01);
  item("deaths_per_10k", (v) => `${+v.toFixed(1)}`, (s) => `${s} deaths per 10k arrivals`, 2);
  return parts.length ? { text: parts.join(", "), worse } : null;
}

/**
 * The held-out comparison of a learned manager against the tuned heuristic for the same objective: the verdict with
 * its margin and interval on that objective's score, then the mean wait, walk-outs and deaths that came with it,
 * beside the heuristic's. Never a bare "beats".
 */
export function heldOutVerdict(id: string, scenario: string): string {
  if (kindOf(id) !== "learned") return "";
  const c = comparison(id, scenario);
  if (!c?.verdict) return "";
  const m = managerOf(id) as Named | undefined;
  const on = scoreWords(m) || (c.objective ? titleish(c.objective).toLowerCase() : "its objective");
  const d = c.paired_diff?.mean;
  const ci = c.paired_diff?.ci95;
  const margin = d != null ? ` (score ${signed(d)}${ci != null ? ` ± ${ci.toFixed(3)}` : ""})` : "";
  const v = c.verdict.toLowerCase();
  const tiny = d != null && Math.abs(d) < SAME;
  const phrase = tiny
    ? `is effectively the same as the tuned plan for the same goal on ${on}`
    : /beat/.test(v)
      ? `beats the tuned plan for the same goal on ${on}`
      : /lose|worse/.test(v)
        ? `loses to the tuned plan for the same goal on ${on}`
        : `cannot be told apart from the tuned plan for the same goal on ${on} (difference not significant)`;
  const p = price(rowOf(id, scenario), rowOf(c.b, scenario));
  const cost = !p ? "" : /beat/.test(v) && !tiny && p.worse ? `, by letting things slide elsewhere: ${p.text}` : `. With it: ${p.text}`;
  const where = `On fresh simulated patients${scenario ? ` (${scenario.replace(/_/g, " ")})` : ""} it`;
  return `${where} ${phrase}${margin}${cost}.`;
}

/** What the manager is and how it did, in one or two sentences. Empty when the metadata says nothing. */
export function managerStory(id: string, scenario: string): string {
  const m = managerOf(id) as Named | undefined;
  if (!m || m.kind === "human") return "";
  if (m.kind !== "learned") return managerNote(id);
  const goal = objectiveWords(m);
  const how = trainingWords(m);
  const intro = `A learned agent (PPO${how ? `, ${how}` : ""})${goal ? `, rewarded for ${goal}` : ""}.`;
  const verdict = heldOutVerdict(id, scenario);
  return [intro, verdict || (hasObjective(m.objective) ? "" : "It has no single tuned plan to be compared with at its default weights.")].filter(Boolean).join(" ");
}
