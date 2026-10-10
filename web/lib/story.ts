// What may be said about a manager, and no more: its own description from the server's metadata, and the held-out
// verdict from the results table. Nothing here invents a claim; when the metadata is missing, nothing is said.
import { kindInfo } from "./palette";
import { useUI } from "./ui";
import type { ManagerInfo } from "./types";

const text = (v: unknown): string => {
  if (!v) return "";
  if (typeof v === "string") return v.trim();
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    return (["note", "description", "summary", "method"].map((k) => o[k]).find((x) => typeof x === "string") as string | undefined)?.trim() ?? "";
  }
  return "";
};

/** How the manager was made, in the server's words (`note`, `training` or `description` on the manager or its result row). */
export function managerNote(id: string): string {
  const s = useUI.getState();
  const m = s.managers.find((x) => x.id === id) as (ManagerInfo & Record<string, unknown>) | undefined;
  const row = s.results?.rows.find((r) => r.manager_id === id) as Record<string, unknown> | undefined;
  return text(m?.note) || text(m?.training) || text(m?.description) || text(row?.note) || text(row?.training) || "";
}

/** The held-out comparison of a learned manager against the tuned heuristic for the same objective, as the results file states it. */
export function heldOutVerdict(id: string, scenario: string): string {
  const s = useUI.getState();
  const cmp = s.results?.comparisons;
  if (!Array.isArray(cmp)) return "";
  const kindOf = (mid: string) => s.managers.find((m) => m.id === mid)?.kind ?? s.results?.rows.find((r) => r.manager_id === mid)?.kind;
  if (kindOf(id) !== "learned") return "";
  const c = cmp.find((x) => x.a === id && x.scenario === scenario && kindOf(x.b) === "tuned_heuristic") ?? cmp.find((x) => x.a === id && kindOf(x.b) === "tuned_heuristic");
  if (!c?.verdict) return "";
  const other = s.managers.find((m) => m.id === c.b)?.label ?? c.b;
  return `On held-out seeds it ${c.verdict} “${prettyManager(other)}”.`;
}

/** One or two sentences for a caption or header. Empty when the metadata says nothing. */
export function managerStory(id: string, scenario: string): string {
  return [managerNote(id), heldOutVerdict(id, scenario)].filter(Boolean).join(" ");
}

const OBJECTIVE: Record<string, string> = { min_cost: "lowest cost", min_wait: "shortest waits", balanced: "balanced", "cost_s.t._p95_wait": "lowest cost within a wait limit", cost_p95: "lowest cost within a wait limit" };
/** Server labels carry raw objective ids ("Tuned heuristic: cost_s.t._p95_wait"): put them into words. */
export function prettyManager(label: string): string {
  return label.replace(/\s*\[fixture\]$/, "").replace(/:\s*([a-z0-9_.]+)$/i, (m, k: string) => (OBJECTIVE[k] ? `: ${OBJECTIVE[k]}` : m));
}
export const namedManager = (m: ManagerInfo) => `${prettyManager(m.label)} (${kindInfo(m.kind).label.toLowerCase()})`;
