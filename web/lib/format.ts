import type { Enums, Snapshot } from "./types";

export const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const DOW_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export const pad2 = (n: number) => String(n).padStart(2, "0");
export const hhmm = (minuteOfDay: number) => `${pad2(Math.floor(minuteOfDay / 60) % 24)}:${pad2(Math.floor(minuteOfDay % 60))}`;

/** Tick index -> clock parts. Tick 0 is day 0, 00:00, a Monday. */
export function tickClock(t: number, tickMinutes = 5) {
  const min = t * tickMinutes;
  const day = Math.floor(min / 1440);
  return { day, minute_of_day: ((min % 1440) + 1440) % 1440, dow: ((day % 7) + 7) % 7 };
}
export const tickLabel = (t: number, tickMinutes = 5) => {
  const c = tickClock(t, tickMinutes);
  return `${DOW[c.dow]} ${hhmm(c.minute_of_day)}`;
};
export const tickLabelLong = (t: number, tickMinutes = 5) => {
  const c = tickClock(t, tickMinutes);
  return `Day ${c.day + 1} · ${DOW[c.dow]} ${hhmm(c.minute_of_day)}`;
};

export function duration(min: number): string {
  if (!isFinite(min)) return "–";
  const m = Math.max(0, Math.round(min));
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h} h ${pad2(m % 60)} m`;
  return `${Math.floor(h / 24)} d ${h % 24} h`;
}

export const patientId = (id: number | string) => `P-${String(id).padStart(6, "0")}`;

export function titleCase(s: string): string {
  const t = s.replace(/_/g, " ").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

const PATIENT_STATE: Record<string, string> = {
  waiting_triage: "Waiting for triage",
  in_triage: "In triage",
  waiting_bay: "Waiting for a bay",
  waiting_provider: "Waiting for provider",
  with_provider: "In treatment",
  waiting_test: "Waiting for test",
  in_test: "In imaging",
  waiting_results: "Awaiting results",
  boarding: "Boarding",
  in_ward: "On ward",
  walking: "Walking",
  exited: "Exited",
};
const EXIT: Record<string, string> = {
  none: "In hospital",
  discharged_ed: "Discharged from ED",
  discharged_ward: "Discharged from ward",
  lwbs: "Left without being seen",
  transferred: "Transferred out",
  died: "Died",
  diverted: "Diverted",
};
const ROLE: Record<string, string> = {
  attending: "Attending",
  resident: "Resident",
  app: "APP",
  rn: "Nurse",
  charge_rn: "Charge nurse",
  tech: "Tech",
  registration: "Registration",
  pharmacist: "Pharmacist",
  imaging_tech: "Imaging tech",
  transport: "Transport",
  evs: "Cleaning",
};
const ROOM_STATUS: Record<string, string> = {
  closed: "Closed",
  open_empty: "Free",
  occupied: "Occupied",
  cleaning: "Cleaning",
  out_of_service: "Out of service",
};
const CONDITION: Record<string, string> = {
  chest_pain: "Chest pain",
  respiratory: "Respiratory",
  abdominal_pain: "Abdominal pain",
  injury_trauma: "Injury / trauma",
  neuro: "Neuro",
  infection_fever: "Infection / fever",
  mental_health_substance: "Mental health / substance",
  musculoskeletal: "Musculoskeletal",
  other_medical: "Other medical",
};
const AGE: Record<string, string> = { age_0_17: "0–17", age_18_44: "18–44", age_45_64: "45–64", age_65_plus: "65+" };

const look = (map: Record<string, string>, list: string[] | undefined, i: number) => {
  const key = list?.[i];
  if (key == null) return `#${i}`;
  return map[key] ?? titleCase(key);
};
export const L = {
  patientState: (e: Enums, i: number) => look(PATIENT_STATE, e.patient_state, i),
  exit: (e: Enums, i: number) => look(EXIT, e.patient_exit, i),
  role: (e: Enums, i: number) => look(ROLE, e.staff_role, i),
  staffState: (e: Enums, i: number) => look({}, e.staff_state, i),
  roomStatus: (e: Enums, i: number) => look(ROOM_STATUS, e.room_status, i),
  condition: (e: Enums, i: number) => look(CONDITION, e.condition_group, i),
  ageBand: (e: Enums, i: number) => look(AGE, e.age_band, i),
  payer: (e: Enums, i: number) => look({}, e.payer, i),
  arrival: (e: Enums, i: number) => look({ walk_in: "Walk-in" }, e.arrival_mode, i),
  equipStatus: (e: Enums, i: number) => look({}, e.equipment_status, i),
  roomType: (key: string) => titleCase(key),
};

export function money(v: number, compact = true): string {
  if (!isFinite(v)) return "–";
  const a = Math.abs(v);
  const sign = v < 0 ? "−" : "";
  if (compact && a >= 1e6) return `${sign}$${(a / 1e6).toFixed(a >= 1e7 ? 1 : 2)}M`;
  if (compact && a >= 1e4) return `${sign}$${(a / 1e3).toFixed(a >= 1e5 ? 0 : 1)}k`;
  return `${sign}$${Math.round(a).toLocaleString("en-US")}`;
}
export function num(v: number, digits = 0): string {
  if (!isFinite(v)) return "–";
  return v.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}
export const pct = (v: number, digits = 0) => (isFinite(v) ? `${(v * 100).toFixed(digits)}%` : "–");

/** Format a metric by its contracts/metrics.yaml unit. */
export function metricValue(v: number, unit?: string): string {
  if (v == null || !isFinite(v)) return "–";
  switch (unit) {
    case "usd":
      return money(v);
    case "fraction":
    case "index_0_1":
      return pct(v, v < 0.1 ? 1 : 0);
    case "minutes":
      return `${num(v, v < 10 ? 1 : 0)} min`;
    default:
      return num(v, Math.abs(v) < 10 && v % 1 !== 0 ? 1 : 0);
  }
}

export function formatValue(v: unknown): string {
  if (v == null) return "–";
  if (typeof v === "number") return Math.abs(v) >= 10000 ? v.toLocaleString("en-US") : String(+v.toFixed(4));
  if (typeof v === "string" || typeof v === "boolean") return String(v);
  if (Array.isArray(v)) {
    if (v.length <= 6) return v.map(formatValue).join(", ");
    return `${v.slice(0, 5).map(formatValue).join(", ")}, … (${v.length} values)`;
  }
  if (typeof v === "object") {
    const ent = Object.entries(v as Record<string, unknown>);
    const s = ent.slice(0, 5).map(([k, x]) => `${k}: ${formatValue(x)}`).join(" · ");
    return ent.length > 5 ? `${s} · … (${ent.length} keys)` : s;
  }
  return String(v);
}

export const snapClock = (s: Snapshot) => `Day ${s.clock.day + 1} · ${DOW[s.clock.dow] ?? ""} ${hhmm(s.clock.minute_of_day)}`;
