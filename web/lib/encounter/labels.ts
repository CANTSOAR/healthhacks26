import type { LlmStatus, ObjectiveLabel } from "./types";

export const RULE_LABEL: Record<string, string> = {
  volunteered: "Volunteered",
  if_asked: "Only if asked",
  after_rapport: "After rapport",
  denied_until_confronted: "Denied until confronted",
  chart_initial: "In the chart from the start",
  known_to_care_team: "Already known to the care team",
  on_request: "On request",
};
export const RULE_HELP: Record<string, string> = {
  volunteered: "The patient offers this as soon as the conversation opens.",
  if_asked: "The patient shares this when a question touches one of its topics.",
  after_rapport: "The patient gives the cover answer until the learner has earned enough rapport, then tells the truth when asked.",
  denied_until_confronted: "The patient denies this until the learner has seen the named evidence and raises the topic again.",
  chart_initial: "Shown in the chart when the encounter starts (triage, vital signs).",
  on_request: "Released when the learner requests the named examination, test or record.",
};
export const RULE_TONE: Record<string, { bg: string; fg: string }> = {
  volunteered: { bg: "#E3F4EA", fg: "#1F7A4D" },
  if_asked: { bg: "#E3E9FF", fg: "#1F3FD1" },
  after_rapport: { bg: "#F3E8FF", fg: "#7A3FC4" },
  denied_until_confronted: { bg: "#FDE7E7", fg: "#B4232C" },
  chart_initial: { bg: "rgba(20,26,51,0.06)", fg: "#4A5275" },
  known_to_care_team: { bg: "rgba(20,26,51,0.06)", fg: "#4A5275" },
  on_request: { bg: "#FFF1D6", fg: "#9A5B00" },
};

export const OBJECTIVE_LABEL: Record<ObjectiveLabel, string> = {
  met: "Met",
  partly_demonstrated: "Partly demonstrated",
  not_observed: "Not observed",
  not_assessable: "Not assessable",
};
export const OBJECTIVE_TONE: Record<ObjectiveLabel, { bg: string; fg: string; dot: string }> = {
  met: { bg: "#E3F4EA", fg: "#1F7A4D", dot: "#2FA36B" },
  partly_demonstrated: { bg: "#FFF1D6", fg: "#9A5B00", dot: "#E0A100" },
  not_observed: { bg: "#FDE7E7", fg: "#B4232C", dot: "#D8434C" },
  not_assessable: { bg: "rgba(20,26,51,0.06)", fg: "#4A5275", dot: "#8089A8" },
};

export const STATUS_TONE: Record<string, { bg: string; fg: string }> = {
  draft: { bg: "#FFF1D6", fg: "#9A5B00" },
  approved: { bg: "#E3E9FF", fg: "#1F3FD1" },
  published: { bg: "#E3F4EA", fg: "#1F7A4D" },
};

const UPPER = new Set(["ecg", "cbc", "bmp", "bnp", "abg", "crp", "lft", "tsh", "ct", "mri", "heent", "msk", "hba1c"]);
/** "order:ct_abdomen" -> "CT abdomen" */
export function requestLabel(req: string): string {
  const name = req.includes(":") ? req.split(":").slice(1).join(":") : req;
  const words = name.split("_").map((w) => (UPPER.has(w.toLowerCase()) ? w.toUpperCase() : w));
  const s = words.join(" ").replace("xray", "X-ray").replace("d dimer", "D-dimer");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
/** Groups for the quick-action panel. */
export function requestGroup(req: string, kind?: string): "exam" | "order" | "record" {
  if (req.startsWith("artifact:") || /prior_records|medication_list/.test(req)) return "record";
  if (kind === "exam" || req.startsWith("exam:")) return "exam";
  return "order";
}

export function providerLabel(llm?: LlmStatus | null): string {
  if (!llm || !llm.live || llm.provider === "offline") return "Offline patient";
  if (llm.provider === "bedrock") return "Bedrock";
  if (llm.provider === "anthropic") return "Anthropic";
  return llm.provider;
}
export function providerHelp(llm?: LlmStatus | null): string {
  if (!llm || !llm.live || llm.provider === "offline")
    return "No language model is connected. The patient answers with the wording the case author approved, chosen by a topic matcher, and the feedback is produced by rule-based heuristics.";
  return `Replies are phrased by a language model (${llm.provider}${llm.model ? `, ${llm.model}` : ""}) from the facts the case releases; it cannot add clinical facts.`;
}

export function initials(name?: string | null): string {
  return (
    (name || "Patient")
      .split(/\s+/)
      .slice(0, 2)
      .map((w) => w[0] || "")
      .join("")
      .toUpperCase() || "P"
  );
}

/** Simulation tick -> "Day 3 14:20" (tick length defaults to the simulator's five minutes). */
export function simClock(t?: number | null, tickMinutes = 5): string | null {
  if (typeof t !== "number") return null;
  const min = t * tickMinutes;
  const day = Math.floor(min / 1440) + 1;
  const hh = Math.floor((min % 1440) / 60);
  const mm = Math.floor(min % 60);
  return `Day ${day} ${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}
/** "bay-014" -> "Bay 14" */
export function bayLabel(bay?: string | null): string | null {
  if (!bay) return null;
  const m = /^([a-z_]+)-0*(\d+)$/i.exec(bay);
  if (!m) return bay;
  const name = m[1].replace(/_/g, " ");
  return `${name.charAt(0).toUpperCase()}${name.slice(1)} ${m[2]}`;
}
export function shortHospital(id?: string | null, name?: string | null): string {
  if (id === "rwjuh_nb") return "RWJUH model";
  return name || id || "Simulated hospital";
}
export function mmss(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}
export const titleCase = (s?: string | null) => (s ? s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "");
export const genderWord = (g?: string | null) => (g ? g.charAt(0).toUpperCase() + g.slice(1) : "");
