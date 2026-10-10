// Colours used by the scene and the interface. One accent (royal blue); everything else is quiet.
import type { ManagerKind } from "./types";

export const GROUND = "#E9ECFB";
export const ACCENT = "#2F55F5";

/** Acuity (ESI 1..5): a five-step scale from critical to minor. Index 0 unused. */
export const ACUITY = ["#9AA3B5", "#E5484D", "#F0843C", "#EDBE3A", "#4FB58A", "#6FA8E8"];
export const ACUITY_LABEL = ["", "ESI 1 · Resuscitation", "ESI 2 · Emergent", "ESI 3 · Urgent", "ESI 4 · Less urgent", "ESI 5 · Non-urgent"];
export const ACUITY_SHORT = ["", "ESI 1", "ESI 2", "ESI 3", "ESI 4", "ESI 5"];

/** Staff by role key (enums.staff_role). Cool, dark, desaturated so patients' acuity colours stay the loudest thing. */
export const ROLE_COLOR: Record<string, string> = {
  attending: "#1E2A5E",
  resident: "#4658A8",
  app: "#7D6BD8",
  rn: "#22A3A0",
  charge_rn: "#0F7676",
  tech: "#7F8AA3",
  registration: "#B39B78",
  pharmacist: "#B866A6",
  imaging_tech: "#5878A3",
  transport: "#98A1B5",
  evs: "#AEB5C6",
};
export const roleColor = (key: string | undefined) => (key && ROLE_COLOR[key]) || "#7F8AA3";

export const SKIN = "#F2D6C2";
export const STAFF_HEAD = "#27304F";

/** Room floor tint by room type: all very pale. */
export const FLOOR: Record<string, string> = {
  waiting_room: "#EEF1FF",
  triage: "#E4EAFF",
  treatment_bay: "#F6F7FD",
  resus_bay: "#FCEBEC",
  fast_track: "#E8F6EF",
  results_waiting: "#EEF1FF",
  xray: "#ECEAFB",
  ct: "#ECEAFB",
  mri: "#ECEAFB",
  ultrasound: "#ECEAFB",
  lab: "#E6F4F6",
  pharmacy: "#FFF5E3",
  operating_room: "#E6F4F6",
  recovery: "#F6F7FD",
  icu_bed: "#FCEBEC",
  stepdown_bed: "#F6F7FD",
  ward_unit: "#F1F4FB",
  ambulance_bay: "#D5DAF0",
  entrance: "#DCE3FF",
  nurse_station: "#E4EAFF",
  corridor: "#F3F5FC",
  decon: "#E6F4F6",
  peds_ed: "#FFF5E3",
  support: "#F0F1F7",
};

/** Manager kinds: three hues (blue / orange / aqua pass the all-pairs colour-vision check together) plus three neutrals.
 * Every kind also has its own marker shape and points are labelled, so identity never rests on colour alone. */
export const KIND: Record<ManagerKind, { color: string; shape: "circle" | "square" | "diamond" | "triangle" | "cross" | "star"; label: string }> = {
  learned: { color: "#2F55F5", shape: "circle", label: "Learned" },
  tuned_heuristic: { color: "#EB6834", shape: "diamond", label: "Tuned heuristic" },
  rule_based: { color: "#1BAF7A", shape: "square", label: "Rule-based" },
  fixed: { color: "#3A4266", shape: "triangle", label: "Fixed" },
  random: { color: "#9AA3B5", shape: "cross", label: "Random" },
  human: { color: "#141A33", shape: "star", label: "Human" },
};
export const kindInfo = (k: string) => KIND[k as ManagerKind] ?? { color: "#8A93AD", shape: "circle" as const, label: k };

/** Two-series comparison: A is the accent, B is orange. */
export const SERIES = ["#2F55F5", "#EB6834"];

export const SOURCE_CHIP: Record<string, { bg: string; fg: string; label: string }> = {
  measured: { bg: "#DFF5EA", fg: "#11734B", label: "measured" },
  literature: { bg: "#E3E9FF", fg: "#1F3FD1", label: "literature" },
  assumed: { bg: "#FDEFD8", fg: "#8A5A00", label: "assumed" },
  surveyed: { bg: "#DFF5EA", fg: "#11734B", label: "surveyed" },
  published: { bg: "#E3E9FF", fg: "#1F3FD1", label: "published" },
  inferred: { bg: "#FDEFD8", fg: "#8A5A00", label: "inferred" },
  fixture: { bg: "#ECEEF6", fg: "#4A5275", label: "fixture" },
};
