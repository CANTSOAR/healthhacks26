// Marginal value of one resource unit (rl/attribution.py -> GET /api/attribution/{hospital_id}). All numbers simulated.
// `minus_one` in the report is (without the unit) − (baseline): the value of the unit is its negative.
import type { FeedState } from "./feed";
import { enumsOf } from "./describe";
import type { Selection } from "./types";

export interface Stat {
  mean: number;
  lo: number | null;
  hi: number | null;
}
export interface AttrEffect {
  metric: string;
  label: string;
  unit: string;
  delta: number;
  lo: number | null;
  hi: number | null;
  pct: number | null;
  significant: boolean;
  direction: "worse" | "better" | "none";
}
interface Profile {
  mean: number[];
  hw: number[];
}
export interface AttrDirection {
  description?: string;
  delta: Record<string, Stat>;
  reward: Record<string, Stat>;
  flow_index_pct?: Stat;
  top_effects: AttrEffect[];
  verdict: string;
  money: {
    margin_per_day: Stat;
    unit_cost_per_day: number;
    net_value_per_day: Stat;
    net_value_per_year: Stat;
    net_value_per_dollar: Stat | null;
    /** the unit's effect on the reward in dollars of daily cost at the objective's exchange rate (net of its own cost) */
    reward_value_per_day?: Stat;
    reward_value_per_dollar?: Stat | null;
    n_units: number;
  };
  by_hour: Record<string, Profile> & { terms?: unknown };
}
export interface AttrUtil {
  mean: number;
  full_share: number;
  by_hour: number[];
  definition?: string;
}
export interface AttrUnit {
  id: string;
  label: string;
  unit_label: string;
  resource_class: string;
  kind: "staff" | "space" | "equipment";
  shift?: string | null;
  unit_cost_per_day: number;
  cost_basis?: string;
  count?: number;
  scenarios: Record<string, { minus_one: AttrDirection | null; plus_one: AttrDirection | null }>;
  utilisation?: Record<string, AttrUtil | null>;
}
export interface AttrRankSide {
  reward_value_per_day?: Stat;
  reward_value_per_dollar?: Stat | null;
  net_value_per_day: Stat;
  net_value_per_dollar: Stat | null;
  reward: Stat;
  /** change in the money-free patient-flow index, % of baseline; positive = worse flow */
  flow_index_pct?: Stat;
  verdict: string;
  top_effects: AttrEffect[];
}
export interface AttrRankRow {
  rank: number;
  unit: string;
  label: string;
  resource_class: string;
  kind: string;
  unit_cost_per_day: number;
  n_units: number;
  existing: AttrRankSide | null;
  next: AttrRankSide | null;
}
interface Finding {
  unit: string;
  label: string;
  reward: Stat;
  net_value_per_day?: Stat;
  reward_value_per_day?: Stat;
  margin_per_day?: Stat;
  verdict?: string;
}
export interface AttributionReport {
  simulated: boolean;
  generated: string;
  hospital_id: string;
  disclaimer: string;
  manager: { id: string; label: string; kind: string };
  protocol: { n_seeds: number; days: number; scenarios: string[]; ci: string };
  reward: { default_objective: string; cost_scale_per_hour?: number; scales?: Record<string, number> };
  units: AttrUnit[];
  ranking: Record<string, AttrRankRow[]>;
  findings: Record<string, { binding: Finding | null; worth_adding: Finding[]; slack: Finding[]; needed: Finding[]; not_shown_either_way: Finding[]; rule: string;
    revenue_rises_when_removed?: { unit: string; label: string }[]; flow_most_hurt_by_removing?: { label: string; flow_index_pct: Stat }[]; flow_most_helped_by_adding?: { label: string; flow_index_pct: Stat }[] }>;
  identifiability?: string[];
  location?: { rooms?: Record<string, { vs_class_waiting_m: number; vs_class_ct_m: number; walk_seconds_vs_class: number }> | null };
}

/** What the inspector shows for one entity. The server sends the same shape as `attribution` on a live entity. */
export interface EntityValue {
  available: boolean;
  reason?: string;
  unit?: string;
  label?: string;
  unit_label?: string;
  resource_class?: string;
  scenario?: string;
  existing?: boolean;
  n_units?: number;
  basis?: string;
  /** value to the objective, $-equivalent per day (net of its own cost) */
  reward_value_per_day?: Stat | null;
  reward_value_per_dollar?: Stat | null;
  /** margin alone */
  net_value_per_day?: Stat;
  unit_cost_per_day?: number;
  net_value_per_dollar?: Stat | null;
  reward?: Stat | null;
  /** patient-flow index change from removing (existing unit) or adding it, % of baseline; positive = worse */
  flow_index_pct?: Stat | null;
  verdict?: string;
  top_effects?: AttrEffect[];
  effects_of?: string;
  now?: { hour: number; margin_per_hour: { mean: number; hw: number }; reward_per_hour: { mean: number; hw: number }; reward_value_per_hour?: { mean: number; hw: number } };
  by_hour?: { margin: number[]; margin_hw: number[]; reward: number[]; reward_hw: number[]; reward_value?: number[]; reward_value_hw?: number[] };
  utilisation_typical?: { mean: number; at_hour: number; full_share: number; definition?: string } | null;
  utilisation_now?: { value: number | null; in_use?: number; of?: number; basis: string } | null;
  next_unit?: { net_value_per_day: Stat; reward_value_per_day?: Stat | null; reward: Stat; verdict: string } | null;
  protocol?: { n_seeds: number; days: number; ci: string };
  note?: string;
  location?: { vs_class_waiting_m: number; vs_class_ct_m: number; walk_seconds_vs_class: number; modelled?: boolean };
}

const ROOM_UNIT: Record<string, string> = {
  resus_bay: "bay_resus", fast_track: "bay_fast", peds_ed: "bay_peds", triage: "triage_station", ward_unit: "ward_bed", icu_bed: "ward_bed",
  stepdown_bed: "ward_bed", ct: "ct_scanner", xray: "xray_room",
};
const PROVIDERS = new Set(["attending", "resident", "app"]);
export const shiftOf = (hour: number) => (hour >= 7 && hour < 15 ? "day" : hour >= 15 && hour < 23 ? "evening" : "night");
export const hourOf = (f: FeedState) => Math.floor((f.snap?.clock.minute_of_day ?? 0) / 60) % 24;

/** The resource unit an inspected entity stands for; `held` = a role the model keeps constant; null = not a resource. */
export function unitIdFor(sel: Selection, f: FeedState): string | "held" | null {
  const e = enumsOf(f);
  const snap = f.snap;
  const layout = f.layout;
  if (sel.kind === "staff") {
    const i = snap ? snap.staff.id.indexOf(String(sel.id)) : -1;
    if (!snap || i < 0) return null;
    const role = e.staff_role[snap.staff.role[i]];
    const shift = shiftOf(hourOf(f));
    if (PROVIDERS.has(role)) return `provider_${shift}`;
    if (role === "rn") return layout?.rooms[snap.staff.room[i]]?.type === "triage" ? "triage_station" : `nurse_${shift}`;
    return "held";
  }
  if (sel.kind === "room") {
    const r = layout?.rooms.find((x) => x.id === sel.id);
    if (!r) return null;
    if (r.type === "treatment_bay") return (r.catalog_ref ?? "").includes("hallway") ? "bay_hall" : "bay_main";
    return ROOM_UNIT[r.type] ?? null;
  }
  if (sel.kind === "equipment") {
    const q = layout?.equipment.find((x) => x.id === sel.id);
    return q?.type === "ct" ? "ct_scanner" : q?.type === "xray" ? "xray_room" : null;
  }
  return null;
}

const neg = (s: Stat): Stat => ({ mean: -s.mean, lo: s.hi == null ? null : -s.hi, hi: s.lo == null ? null : -s.lo });

/** The same lookup the server does for a live entity, for recorded runs and for when it sent nothing. */
export function entityValue(rep: AttributionReport | null, sel: Selection, f: FeedState): EntityValue | null {
  if (!rep) return null;
  const uid = unitIdFor(sel, f);
  if (uid == null) return null;
  if (uid === "held") return { available: false, reason: "Held constant in the model: this role is not a decision the simulator can change, so it has no simulated marginal value." };
  const u = rep.units.find((x) => x.id === uid);
  const scs = rep.protocol.scenarios;
  const sc = f.header && scs.includes(f.header.scenario) ? f.header.scenario : scs[0];
  const row = u?.scenarios[sc];
  if (!u || !row) return null;
  const existing = !!row.minus_one;
  const a = row.minus_one ?? row.plus_one;
  if (!a) return null;
  const obj = rep.reward.default_objective;
  const sgn = existing ? -1 : 1;
  const h = hourOf(f);
  const bh = a.by_hour;
  const cs = rep.reward.cost_scale_per_hour ?? rep.reward.scales?.cost ?? 0;
  const t = u.utilisation?.[sc] ?? null;
  const loc = sel.kind === "room" ? rep.location?.rooms?.[String(sel.id)] : undefined;
  return {
    available: true, unit: uid, label: u.label, unit_label: u.unit_label, resource_class: u.resource_class, scenario: sc, existing, n_units: a.money.n_units,
    reward_value_per_day: a.money.reward_value_per_day ?? null, reward_value_per_dollar: a.money.reward_value_per_dollar ?? null,
    net_value_per_day: a.money.net_value_per_day, unit_cost_per_day: a.money.unit_cost_per_day, net_value_per_dollar: a.money.net_value_per_dollar,
    reward: a.reward[obj] ? (existing ? neg(a.reward[obj]) : a.reward[obj]) : null, flow_index_pct: a.flow_index_pct ?? null, verdict: a.verdict, top_effects: a.top_effects.slice(0, 3),
    effects_of: existing ? "removing it" : "adding it",
    now: { hour: h, margin_per_hour: { mean: sgn * bh.margin.mean[h], hw: bh.margin.hw[h] }, reward_per_hour: { mean: sgn * bh.reward.mean[h], hw: bh.reward.hw[h] }, reward_value_per_hour: { mean: sgn * bh.reward.mean[h] * cs, hw: bh.reward.hw[h] * cs } },
    by_hour: { margin: bh.margin.mean.map((x) => sgn * x), margin_hw: bh.margin.hw, reward: bh.reward.mean.map((x) => sgn * x), reward_hw: bh.reward.hw, reward_value: bh.reward.mean.map((x) => sgn * x * cs), reward_value_hw: bh.reward.hw.map((x) => x * cs) },
    utilisation_typical: t ? { mean: t.mean, at_hour: t.by_hour[h], full_share: t.full_share, definition: t.definition } : null,
    utilisation_now: null,
    next_unit: existing && row.plus_one ? { net_value_per_day: row.plus_one.money.net_value_per_day, reward_value_per_day: row.plus_one.money.reward_value_per_day ?? null, reward: row.plus_one.reward[obj], verdict: row.plus_one.verdict } : null,
    protocol: rep.protocol,
    location: loc ? { ...loc, modelled: false } : undefined,
  };
}

const usd = (v: number) => `${v < 0 ? "−" : v > 0 ? "+" : ""}$${Math.abs(v) >= 1e4 ? `${(Math.abs(v) / 1e3).toFixed(Math.abs(v) >= 1e5 ? 0 : 1)}k` : Math.round(Math.abs(v)).toLocaleString("en-US")}`;
export const signedUsd = usd;
/** "+$1.2k [−$300, +$2.7k]" */
export function statUsd(s?: Stat | null): string {
  if (!s || s.mean == null) return "–";
  return s.lo == null || s.hi == null ? usd(s.mean) : `${usd(s.mean)} [${usd(s.lo)}, ${usd(s.hi)}]`;
}
export function signed(v: number, unit = ""): string {
  const a = Math.abs(v);
  const d = a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3;
  return `${v < 0 ? "−" : v > 0 ? "+" : ""}${unit.startsWith("$") ? "$" : ""}${a.toLocaleString("en-US", { maximumFractionDigits: d })}${unit && !unit.startsWith("$") ? ` ${unit}` : unit.replace("$", "")}`;
}
export const excludesZero = (s?: Stat | null) => !!s && s.lo != null && s.hi != null && (s.lo > 0 || s.hi < 0);

export const VERDICT: Record<string, { label: string; bg: string; fg: string; title: string }> = {
  needed: { label: "needed", bg: "#DFF5EA", fg: "#11734B", title: "Removing one worsens flow or safety by more than a negligible amount and lowers the balanced reward (95% interval below zero)" },
  slack: { label: "slack", bg: "#E3E9FF", fg: "#1F3FD1", title: "Removing one saves money and every flow and safety metric is shown to get at most negligibly worse (interval inside the equivalence margin)" },
  "trade-off": { label: "trade-off", bg: "#FDEFD8", fg: "#8A5A00", title: "Removing one costs something real (a flow or safety metric, or the balanced reward, measurably worsens) but the evidence does not make it clearly needed" },
  "costs more than it returns": { label: "costs more than it returns", bg: "#FDEFD8", fg: "#8A5A00", title: "Removing one worsens a flow or safety metric, yet the balanced reward rises: it costs more than the harm it prevents, by these weights" },
  inconclusive: { label: "not shown either way", bg: "#ECEEF6", fg: "#4A5275", title: "The intervals are too wide to call it needed or slack" },
  "no measurable effect": { label: "no measurable effect", bg: "#ECEEF6", fg: "#4A5275", title: "No flow, safety or money effect outside the intervals" },
  "worth adding": { label: "worth adding", bg: "#DFF5EA", fg: "#11734B", title: "Adding one raises the balanced reward with a 95% interval above zero" },
  "not worth adding": { label: "not worth adding", bg: "#FDE7E8", fg: "#B4232A", title: "Adding one lowers the balanced reward with a 95% interval below zero" },
  "not shown either way": { label: "not shown either way", bg: "#ECEEF6", fg: "#4A5275", title: "The interval of the reward change includes zero" },
};
