// Types mirroring contracts/*.schema.json and contracts/api.md. Keep in step with the contracts.

export type Enums = Record<string, string[]> & {
  patient_state: string[];
  patient_exit: string[];
  staff_role: string[];
  staff_state: string[];
  room_type: string[];
  room_status: string[];
  condition_group: string[];
  arrival_mode: string[];
  age_band: string[];
  payer: string[];
  equipment_type: string[];
  equipment_status: string[];
};

export type Provenance = "surveyed" | "published" | "inferred";
export type SourceTag = "measured" | "literature" | "assumed";
export type ManagerKind = "learned" | "tuned_heuristic" | "rule_based" | "fixed" | "random" | "human";
export type Cadence = "hourly" | "daily" | "weekly" | "monthly";

export interface Room {
  id: string;
  type: string;
  label: string;
  zone?: string;
  x: number;
  z: number;
  w: number;
  d: number;
  floor?: number;
  capacity: number;
  physical?: boolean;
  slots?: [number, number][];
  catalog_ref?: string;
  provenance: Provenance;
  source?: string;
  note?: string;
}
export interface Equipment {
  id: string;
  type: string;
  label?: string;
  room: string;
  catalog_ref?: string;
  provenance: Provenance;
  source?: string;
}
export interface Layout {
  schema_version: 1;
  hospital_id: string;
  name: string;
  disclaimer: string;
  version?: number;
  site: {
    w: number;
    d: number;
    roads?: { id: string; label?: string; width?: number; points: [number, number][]; provenance?: Provenance }[];
    buildings?: { id: string; label?: string; height?: number; polygon: [number, number][]; provenance?: Provenance; source?: string }[];
  };
  rooms: Room[];
  equipment: Equipment[];
  walk_speed_m_per_min?: number;
  sources?: { title: string; url: string; used_for?: string; accessed?: string }[];
}

export interface Decision {
  t: number;
  head: string;
  value: number;
  prev?: number;
  label: string;
  cadence: Cadence;
}
export interface SimEvent {
  t: number;
  kind: string;
  text: string;
  entity?: string | number | null;
}
export interface Ambulance {
  id: string;
  x: number;
  z: number;
  state: "approaching" | "unloading" | "leaving" | "diverted";
}
export interface Snapshot {
  t: number;
  clock: { day: number; minute_of_day: number; dow: number };
  layout_version?: number;
  patients: {
    id: number[];
    acuity: number[];
    condition: number[];
    state: number[];
    exit: number[];
    room: number[];
    x: number[];
    z: number[];
    age_min: number[];
    state_min: number[];
    arrival_mode: number[];
    age_band: number[];
    payer?: number[];
    flags: number[];
    staff?: number[];
  };
  staff: {
    id: string[];
    name?: (string | null)[];
    role: number[];
    state: number[];
    room: number[];
    x: number[];
    z: number[];
    patient?: number[];
    fatigue?: number[];
  };
  rooms: { status: number[]; occupancy: number[]; queue?: number[] };
  equipment: { status: number[] };
  ambulances?: Ambulance[];
  kpis: { settings?: Record<string, number> } & Record<string, unknown>;
  events?: SimEvent[];
  decisions?: Decision[];
}

export interface ActionHead {
  name: string;
  cadence: Cadence;
  options: string[];
  default: number;
  desc?: string;
  values?: unknown[];
  /** server extra: false when the simulator accepts the head but does not model it yet */
  implemented?: boolean;
}
export interface ManagerInfo {
  id: string;
  kind: ManagerKind;
  label: string;
  objective?: string;
  reward_weights?: Record<string, number> | null;
  available?: boolean;
  checkpoint?: string;
  /** how it was made, when the server says (e.g. "PPO warm-started by behaviour cloning from the tuned heuristic") */
  note?: string;
  training?: unknown;
  description?: string;
}
export interface RolloutHeader {
  rollout_id: string;
  manager: ManagerInfo;
  scenario: string;
  hospital_id: string;
  seed: number;
  tick_minutes: number;
  days: number;
  created?: string;
  synthetic?: true;
  enums: Enums;
  layout: Layout;
  action_spec: ActionHead[];
  summary?: Record<string, number>;
}
export interface Rollout {
  schema_version: 1;
  header: RolloutHeader;
  hourly: Record<string, number[]>;
  decisions: Decision[];
  structural_changes?: { t_decided: number; t_effective: number; kind: string; label: string; cost?: number; layout?: Layout }[];
  segments: { label?: string; start_t: number; every_ticks: number; snapshots: Snapshot[] }[];
}
export interface RolloutListItem {
  rollout_id: string;
  manager: ManagerInfo;
  scenario: string;
  seed: number;
  days: number;
  summary?: Record<string, number>;
  has_segments: boolean;
}

export interface CatalogAttribute {
  value: unknown;
  unit: string;
  dist?: { kind: string; mean?: number; cv?: number; p?: unknown; low?: number; high?: number };
  index?: string;
  source: SourceTag;
  citation?: string;
  url?: string;
  file?: string;
  note?: string;
  range?: unknown[];
  validation_only?: boolean;
  /** set when the elements of a list/map value do not all share the attribute's source tag */
  mixed_provenance?: string;
}
export interface CatalogRef {
  entity_type: string;
  variant: string;
  label: string;
  attributes: Record<string, CatalogAttribute>;
}
export interface CatalogSummary {
  entity_types: { entity_type: string; description: string; n_variants: number; n_attributes: number; by_source: Record<SourceTag, number> }[];
  totals: Record<string, unknown>;
}

export interface ServiceStatus {
  services: {
    sim: { live: boolean };
    data: { live: boolean; provider: string };
  };
  torch?: string | null;
  device?: string | null;
  version?: string;
}
export interface Scenario {
  id: string;
  label: string;
  description?: string;
  hospital_id: string;
  days_default?: number;
}
export interface Hospital {
  id: string;
  name: string;
  disclaimer: string;
}
export interface Stat {
  mean: number;
  std?: number;
  ci95?: number;
}
export interface ResultRow {
  manager_id: string;
  kind: ManagerKind;
  label: string;
  objective?: string;
  scenario: string;
  n_seeds?: number;
  metrics: Record<string, Stat>;
}
export interface HumanRun {
  label: string;
  scenario: string;
  seed: number;
  days: number;
  summary: Record<string, number>;
  created?: string;
}
export interface Results {
  generated?: string;
  protocol?: { seeds?: number[] | number; days?: number; scenarios?: string[] };
  rows: ResultRow[];
  human_runs: HumanRun[];
  note?: string;
  /** paired held-out comparisons between managers, with the verdict as the evaluation states it */
  comparisons?: { a: string; b: string; scenario: string; objective?: string; verdict?: string }[];
}

export interface ValidationTarget {
  name: string;
  value: number | null;
  range?: [number, number] | null;
  source?: string;
  url?: string;
  unit?: string;
  variant_label?: string;
  attribute?: string;
  citation?: string;
  note?: string;
}
export interface Validation {
  status?: "pending" | "ready" | "error" | "no_targets" | "offline";
  targets: ValidationTarget[];
  simulated: Record<string, number>;
  within: Record<string, boolean>;
  baseline?: { scenario?: string; days?: number; policy?: string; seeds?: number[]; computed?: string };
  stale?: boolean;
}

export type SelKind = "patient" | "staff" | "room" | "equipment" | "ambulance";
export interface Selection {
  kind: SelKind;
  id: string | number;
  feed: string; // feed key ("a" | "b")
}

// websocket messages, server -> client
export type ServerMsg =
  | { type: "header"; run_id: string; scenario: string; seed: number; hospital_id: string; manager: ManagerInfo; tick_minutes: number; enums: Enums; layout: Layout; action_spec: ActionHead[]; metric_defs?: unknown }
  | { type: "snapshot"; snapshot: Snapshot }
  | { type: "hour"; t: number; metrics: Record<string, number>; pending?: Record<string, number>; mask?: Record<string, boolean>; ack?: boolean }
  | { type: "layout"; layout: Layout }
  | { type: "detail"; entity: unknown; live?: unknown; catalog?: unknown; interactions?: unknown[] }
  | { type: "summary"; summary: Record<string, number>; final?: boolean; days?: number }
  | { type: "error"; message: string };
