// Shapes returned by the journey routes (encounter/journey/api.py). Student views only: the shared record, never the case.
import type { AvailableRequest, Chart, InteractionResult, LearnerCase, LedgerEvent, LlmStatus, ObjectiveLabel, PatientView, SimBinding } from "@/lib/encounter/types";

export type Actor = "human" | "ai" | "sampled" | "sim";
export interface By {
  staff_role: string;
  role_label: string;
  actor: Actor;
  name?: string | null;
}
export interface Provenance {
  entry_id: string;
  text: string;
  kind: string;
  by: By;
  stage_id: string;
  stage_title: string;
  turn: number | null;
  source: string;
  time: string;
  status: string;
  /** Set when the entry is flagged, e.g. "unsupported — not in the shared record". */
  flag?: string;
}
export interface UsedIn {
  stage_id: string;
  turn: number | null;
  how: string;
  quote?: string | null;
}
export interface Unsupported {
  quote: string;
  reason: string;
}
export interface RecordEntry extends Provenance {
  stage_index: number;
  fact_id: string | null;
  source_label: string;
  used_in: UsedIn[];
  category?: string;
  section?: string;
  section_title?: string;
  quote?: string | null;
  key?: string;
  value?: string | number;
  request?: string;
  order_status?: string;
  title?: string;
  artifact_id?: string;
  element?: string;
  element_label?: string;
  in_reply_to?: string;
  unsupported?: Unsupported[];
  discrepancy_ids?: string[];
  /** Written by a sampled stage: copied from the case by the sampler, not elicited from the patient. */
  copied_from_case?: boolean;
  after_confrontation?: boolean;
  default_normal?: boolean;
  synthetic?: boolean;
}
export interface Discrepancy {
  discrepancy_id: string;
  kind: string;
  note: string;
  entries: Provenance[];
  resolved: boolean;
  resolved_by: string | null;
  basis: string;
  flagged_in_stage: string;
}
export interface SharedRecord {
  entries: RecordEntry[];
  discrepancies: Discrepancy[];
  counts: Record<string, number>;
  n_unresolved: number;
}
export interface Evidence {
  quote: string | null;
  turn?: number | null;
  entry_id?: string | null;
  location?: string;
}
export interface StageObjective {
  objective_id: string;
  criterion: string | null;
  kind: string;
  result: ObjectiveLabel | null;
  evidence: Evidence[];
  feedback: string;
  behavior?: string | null;
  held_back?: boolean;
  uncertain?: boolean;
}
export interface Counterpart {
  kind: "patient" | "colleague";
  name?: string;
  label?: string;
  staff_role?: string;
  credentials?: string;
  fictional?: boolean;
  source_label?: string;
}
export interface Stage {
  stage_id: string;
  index: number;
  title: string;
  interaction_type: string;
  kind: "patient" | "handoff";
  learner_role: { staff_role: string; label: string };
  counterparts: Counterpart[];
  brief: string;
  writes: { required: string[]; optional?: string[] };
  status: "pending" | "active" | "completed";
  played_by: "human" | "sampled" | "sim" | null;
  player: string | null;
  result: InteractionResult | null;
  result_note?: string | null;
  objectives: StageObjective[];
  n_case_objectives_held_back?: number;
  blocked_by: string[];
  writeback: { supported: boolean; from_simulation: boolean; written_back: boolean; note: string | null };
  sampled_quality?: number | null;
  n_entries: number;
}
export interface JourneyState {
  journey_id: string;
  status: "active" | "complete";
  template: { journey_id: string; version: number; title: string; description?: string };
  case: LearnerCase;
  patient: PatientView;
  stages: Stage[];
  record: SharedRecord;
  sim?: SimBinding | null;
  llm?: LlmStatus;
  next_stage: string | null;
}
export interface SbarItem {
  item_id: string;
  label: string;
  kind: string;
  critical: boolean;
  text: string;
  provenance: Provenance;
  quote?: string;
  prompted?: boolean;
}
export interface SbarElement {
  element: string;
  label: string;
  text: string;
  conveyed: SbarItem[];
  omitted: SbarItem[];
  unsupported: (Unsupported & { element_label: string; prompted: boolean })[];
  interpretations: string[];
  result: ObjectiveLabel;
  feedback: string;
}
export interface SbarGrading {
  elements: Record<string, SbarElement>;
  behaviors: { behavior: string; observed: string; evidence_location: string; quote: string | null; feedback: string }[];
  critical_total: number;
  critical_unprompted: number;
  critical_after_prompt: number;
  n_unsupported: number;
  receiver_understanding: number | null;
  score: number;
  overall: { result: ObjectiveLabel; feedback: string };
  graded_against: string;
  /** What the unsupported-statement rules cover, and what they do not. */
  checked?: string;
}
export interface HandoffMsg {
  who: "colleague" | "learner";
  text: string;
  kind?: string;
  reask?: boolean;
  question_id?: string | null;
  provider?: string;
  wording?: string;
}
export interface HandoffView {
  colleague: { id?: string; name: string; role?: string; label?: string; credentials?: string; communication_style?: string; fictional?: boolean; source_label?: string };
  /** What the unsupported-statement rules cover, and what they do not. */
  checked?: string;
  sbar: Record<string, string> | null;
  phase: "compose" | "questions" | "readback" | "done";
  messages: HandoffMsg[];
  questions: { question_id: string; text: string; about: string; answered: boolean; answer: string | null; unresolved?: boolean | null; attempts?: number | null }[];
  n_questions: number;
  max_questions: number;
  grading: SbarGrading | null;
}
export interface StageEncounter {
  case: LearnerCase;
  chart: Chart;
  ledger: LedgerEvent[];
  rapport: number;
  turn: number;
  available_requests: AvailableRequest[];
  status: string;
}
export interface StageView {
  journey_id: string;
  journey_status: string;
  stage: Stage;
  record: SharedRecord;
  patient: PatientView;
  llm?: LlmStatus;
  next_stage: string | null;
  encounter?: StageEncounter;
  handoff?: HandoffView;
}
export interface StageTurn {
  reply: string | null;
  notes: string[];
  chart: Chart;
  ledger_tail: LedgerEvent[];
  rapport?: number;
  fallback: boolean;
  turn: number;
  request?: string;
  disclosed: { fact_id: string }[];
  released_artifacts: { artifact_id: string }[];
  record: SharedRecord;
  record_added: string[];
}
export interface TemplateSummary {
  journey_id: string;
  version: number;
  title: string;
  description?: string;
  any_case: boolean;
  default?: boolean;
  stages: { stage_id: string; title: string; interaction_type: string; kind: string; learner_role: { staff_role: string; label: string }; counterparts: { kind: string; label?: string }[] }[];
}
export type PlanRow = Provenance & Partial<RecordEntry> & { source_label?: string };
export interface CarePlan {
  complete: boolean;
  assembled_from: string;
  n_entries: number;
  n_sampled_entries?: number;
  /** Clinicians' notes as written. Never problems; an unsupported one carries `flag`. */
  notes?: PlanRow[];
  unsupported_check?: string;
  patient: { name?: string; age?: number; gender?: string };
  problems: PlanRow[];
  findings: { section: string; title: string; items: PlanRow[] }[];
  medications: PlanRow[];
  allergies: PlanRow[];
  orders: (PlanRow & { results: PlanRow[] })[];
  decisions: { acuity: PlanRow | null; disposition: PlanRow | null };
  plan: PlanRow[];
  coordinated_plan: { problem: PlanRow; evidence: PlanRow[]; actions: PlanRow[]; roles: string[] }[];
  other_actions: PlanRow[];
  open_questions: { text: string; why: string; provenance: Provenance | null }[];
  discrepancies: Discrepancy[];
  contributions: { stage_id: string; stage_title: string; role: { label: string; staff_role: string }; played_by: string | null; player: string | null; counts: Record<string, number>; highlights: PlanRow[] }[];
  information_flow: { entry: Provenance; used_in_stage: string; how: string; quote?: string | null }[];
}
export interface DebriefStage {
  stage_id: string;
  title: string;
  kind: string;
  role: { label: string; staff_role: string };
  played_by: string | null;
  player: string | null;
  objectives: StageObjective[];
  behaviors: Record<string, { count: number; not_assessable?: boolean; evidence: { quote: string; entry_id: string; how?: string }[] }>;
  result: InteractionResult | null;
  handoff?: { grading: SbarGrading; colleague: { name: string } };
  encounter_feedback?: { strengths?: string[]; next_time?: string[] };
}
export interface Debrief {
  stages: DebriefStage[];
  roles: { role: { label: string; staff_role: string }; stages: string[]; played_by: (string | null)[]; counts: Record<ObjectiveLabel, number> }[];
  team: {
    information_lost: { text: string; label: string; element: string; how: string; provenance: Provenance }[];
    never_found: { fact_id: string; category?: string; text: string }[];
    discrepancies_unresolved: Discrepancy[];
    discrepancies_resolved: Discrepancy[];
    handoff_omitted: { text: string; label: string; critical: boolean; element: string }[];
    unsupported_statements: { quote: string; reason: string; element: string }[];
    carried_forward: { entry: Provenance; used_in: UsedIn[] }[];
    summary: Record<string, number>;
  };
  case_debrief: { diagnosis?: string; expected_disposition?: string; recorded_disposition?: string | null; teaching_points: string[] };
  formative_note: string;
}
