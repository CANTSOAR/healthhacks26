// Shapes returned by encounter/api.py (the source of truth) and contracts/case.schema.json.

export interface LlmStatus {
  provider: string; // "offline" | "bedrock" | "anthropic"
  live: boolean;
  model?: string | null;
}
export interface ServiceStatus {
  services: { llm?: LlmStatus; voice?: { live: boolean; provider: string }; sim?: { live: boolean }; encounter?: { live: boolean } };
}

// ---------------------------------------------------------------- case (faculty document)
export type CaseStatus = "draft" | "approved" | "published";
export type DisclosureRule = "volunteered" | "if_asked" | "after_rapport" | "denied_until_confronted" | "chart_initial" | "on_request";
export interface Disclosure {
  rule: DisclosureRule;
  rapport_needed?: number;
  confront_with?: string[];
  request?: string;
}
export interface Fact {
  fact_id: string;
  category: string;
  statement: string;
  value?: unknown;
  unit?: string;
  polarity?: "positive" | "negative" | "unknown";
  patient_knows: boolean;
  patient_answer?: string;
  cover_answer?: string;
  topics?: string[];
  disclosure: Disclosure;
  critical?: boolean;
  chart_section?: string;
  source_ids?: string[];
}
export interface ChartSectionDef {
  section_id: string;
  title: string;
  release: "initial" | "on_fact" | "on_request";
  static_text?: string | null;
}
export interface LabRow {
  test: string;
  value: string | number;
  unit?: string;
  ref_range?: string;
  flag?: string;
  fact_id?: string;
}
export interface ArtifactRelease {
  rule: "initial" | "on_request" | "on_fact";
  request?: string;
  fact_id?: string;
  delay_turns?: number;
}
export interface ArtifactDef {
  artifact_id: string;
  kind: string;
  title: string;
  section_id?: string;
  content?: unknown;
  asset?: string;
  interpretation?: string;
  linked_fact_ids?: string[];
  release: ArtifactRelease;
  synthetic?: boolean;
  source_ids?: string[];
}
export interface Objective {
  objective_id: string;
  criterion: string;
  kind: string;
  linked_fact_ids?: string[];
  linked_requests?: string[];
  evidence_rule?: string;
  critical?: boolean;
  rubric_domain?: string;
  feedback_met?: string;
  feedback_missed?: string;
}
export interface SourceDef {
  source_id: string;
  title: string;
  url?: string;
  date?: string;
  role: string;
  license?: string;
  supports?: string[];
}
export interface Profile {
  name: string;
  age: number;
  gender: string;
  race_ethnicity?: string;
  background?: string;
  personality?: string;
  speech_style?: string;
  image?: string;
  voice?: string;
}
export interface CaseDoc {
  schema_version?: number;
  case_id: string;
  version: number;
  status: CaseStatus;
  title: string;
  origin: { kind: string; condition_template?: string; sim_patient_id?: number; sim_seed?: number; sample_patient_uuid?: string };
  review?: { author?: string; reviewer?: string; reviewed_at?: string; needs_faculty_review?: boolean; synthetic?: boolean };
  intended_learner?: string;
  learner_role?: string;
  setting?: string;
  prebrief?: string;
  profile: Profile;
  faculty_truth?: {
    diagnosis?: string;
    differential?: string[];
    teaching_points?: string[];
    expected_disposition?: string;
    expected_orders?: string[];
    severity?: number;
    acuity?: number;
  };
  facts: Fact[];
  chart: { sections: ChartSectionDef[]; artifacts?: ArtifactDef[] };
  objectives: Objective[];
  rubric_id: string;
  sources: SourceDef[];
  unknown_response?: string;
  updated?: string;
  versions?: number[];
  seed?: boolean;
}
export interface CaseSummary {
  case_id: string;
  version: number;
  status: CaseStatus;
  title: string;
  origin: CaseDoc["origin"];
  profile: { name?: string; age?: number; gender?: string };
  updated?: string;
  versions: number[];
  seed?: boolean;
  n_facts: number;
  n_objectives: number;
  needs_faculty_review?: boolean;
  setting?: string;
  learner_role?: string;
}
export interface Finding {
  path?: string;
  message: string;
}
export interface ConsistencyFinding {
  level: string;
  kind?: string;
  message: string;
  paths?: string[];
}
export interface ValidationReport {
  ok: boolean;
  errors: Finding[];
  warnings: Finding[];
  consistency: ConsistencyFinding[];
}
export type CreatedCase = CaseDoc & { validation: ValidationReport; notes: string[]; created_from: { method?: string; fallback?: boolean; template_id?: string } };
export interface TemplateSummary {
  id: string;
  condition_group: string;
  label: string;
  description: string;
  n_facts: number;
  n_objectives: number;
  typical_concealments?: string[];
  bands?: string[];
}
export interface RubricSummary {
  rubric_id: string;
  title: string;
  source?: string;
  is_default?: boolean;
  n_domains?: number;
  domains?: { key: string; name: string }[];
}

// ---------------------------------------------------------------- encounter (student view)
export interface LearnerCase {
  case_id: string;
  version: number;
  title: string;
  setting?: string;
  learner_role?: string;
  intended_learner?: string;
  prebrief?: string;
  n_objectives?: number;
  rubric?: { rubric_id: string; title: string; domains: { key: string; name: string }[] };
  synthetic?: boolean;
  needs_faculty_review?: boolean;
}
export interface PatientView {
  name?: string;
  age?: number;
  gender?: string;
  image?: string;
  voice?: string;
}
export interface StudentCaseView {
  case: LearnerCase;
  patient: PatientView;
  status: CaseStatus;
}
export interface ChartFact {
  fact_id: string;
  text: string;
  category?: string;
  turn?: number;
  source?: string; // "chart" | "patient" | "result"
  rule?: string;
  polarity?: string | null;
  label?: string;
  value?: string | number;
  unit?: string;
}
export interface ChartNote {
  note_id: string;
  text: string;
  turn?: number;
  kind?: string;
  superseded?: boolean;
}
export interface ChartSection {
  section_id: string;
  title: string;
  release: string;
  static_text?: string | null;
  facts: ChartFact[];
  notes: ChartNote[];
  artifact_ids: string[];
  visible: boolean;
}
export interface ChartArtifact {
  artifact_id: string;
  kind: string;
  title: string;
  content?: unknown;
  interpretation?: string;
  asset?: string;
  synthetic?: boolean;
  section_id?: string;
  turn?: number;
  linked_fact_ids?: string[];
}
export interface Chart {
  sections: ChartSection[];
  artifacts: ChartArtifact[];
  hidden_section_count?: number;
  pending_results?: unknown[];
  n_disclosed?: number;
  turn?: number;
}
export interface AvailableRequest {
  request: string;
  kind: string;
  label: string;
}
export interface SimBinding {
  run_id?: string | null;
  b?: number;
  patient_id: number;
  held?: boolean;
  t_start?: number;
}
export interface LedgerEvent {
  seq: number;
  time: string;
  turn: number;
  actor: string;
  kind: string; // start | turn | request | finish
  text?: string | null;
  request?: string | null;
  request_id?: string | null;
  matched_intents?: string[];
  disclosed_fact_ids: string[];
  released_artifact_ids: string[];
  rule_fired: Record<string, string>;
  result?: string | null;
  rapport?: number;
  rapport_delta?: number;
  rapport_reasons?: string[];
  reply?: string | null;
  provider?: string | null;
  fallback?: boolean;
}
export interface EncounterStart {
  encounter_id: string;
  case: LearnerCase;
  chart: Chart;
  patient: PatientView;
  llm: LlmStatus;
  available_requests: AvailableRequest[];
  rapport?: number;
  status: string;
  preview?: boolean;
  opening_line?: string | null;
  sim?: SimBinding | null;
  held?: boolean;
}
export interface Disclosed {
  fact_id: string;
  chart_section?: string | null;
  text: string;
  category?: string;
  rule?: string;
}
export interface TurnResponse {
  encounter_id: string;
  turn: number;
  request_id?: string;
  reply: string | null;
  notes: string[];
  disclosed: Disclosed[];
  released_artifacts: { artifact_id: string; kind: string; title: string; section_id?: string }[];
  chart: Chart;
  ledger_tail: LedgerEvent[];
  rapport?: number;
  result?: string;
  provider: string;
  fallback: boolean;
  llm?: LlmStatus;
  request?: string;
}
export interface Evidence {
  turn?: number;
  quote: string;
}
export type ObjectiveLabel = "met" | "partly_demonstrated" | "not_observed" | "not_assessable";
export interface ObjectiveResult {
  objective_id: string;
  criterion: string;
  kind?: string;
  result: ObjectiveLabel;
  evidence: Evidence[];
  uncertain?: boolean;
  suggestion?: string;
  critical?: boolean;
  rubric_domain?: string;
  basis?: string;
}
export interface RubricDomainResult {
  key: string;
  name: string;
  score: number | string;
  rationale?: string;
  evidence?: Evidence[];
  uncertain?: boolean;
  descriptor?: string | null;
  triggers_review?: boolean;
}
export interface Feedback {
  objectives: ObjectiveResult[];
  rubric?: {
    rubric_id?: string;
    title?: string;
    source?: string;
    domains: RubricDomainResult[];
    total?: number;
    max_total?: number;
    n_scored?: number;
    review_recommended?: boolean;
    rating_scale?: { score: number; label: string; meaning?: string }[];
    note?: string;
  };
  elicited?: { fact_id: string; text: string; category?: string; critical?: boolean; rule?: string; turn?: number; by?: string }[];
  missed?: { fact_id: string; text: string; category?: string; critical?: boolean; rule?: string; asked?: boolean; how_to_reach?: string }[];
  strengths?: string[];
  next_time?: string[];
  grader?: string; // "offline" | "llm"
  formative_note?: string;
  artifact_interpretations?: { artifact_id: string; title: string; interpretation: string }[];
  debrief?: { diagnosis?: string; teaching_points?: string[]; expected_disposition?: string };
  fallback?: boolean;
  quality?: number;
  quality_parts?: Record<string, number | string>;
  requests_made?: string[];
  writeback_error?: string;
}
export interface InteractionResult {
  interaction_id: string;
  interaction_type: string;
  patient_id: number;
  participants?: { entity_id: number | string; role: string; played_by?: string }[];
  resolver: string; // "played" | "sampled"
  duration_min: number;
  information_gained: string[];
  decision: { kind?: string; orders?: string[]; disposition?: string; detail?: string; acuity?: number };
  quality: number;
  session_ref?: string;
  objective_results?: { objective_id: string; result: string }[];
  t_start?: number;
}
export interface FinishResponse {
  encounter_id: string;
  feedback: Feedback;
  interaction_result: InteractionResult;
  written_back: boolean;
  /** applied = in the simulation now; queued = held until the patient reaches the provider (a success); rejected = refused */
  write_back?: { status: "applied" | "queued" | "rejected" | "not_applicable"; detail?: string } | null;
  already_finished?: boolean;
}
export interface EncounterState {
  encounter_id: string;
  status: string; // active | finished
  started: string;
  finished?: string | null;
  case: LearnerCase;
  patient: PatientView;
  chart: Chart;
  transcript: { turn: number; speaker: string; text: string }[];
  ledger: LedgerEvent[];
  rapport?: number;
  turn: number;
  available_requests: AvailableRequest[];
  preview?: boolean;
  sim?: SimBinding | null;
  feedback?: Feedback | null;
  interaction_result?: InteractionResult | null;
  written_back?: boolean;
  write_back?: { status: "applied" | "queued" | "rejected" | "not_applicable"; detail?: string } | null;
  llm?: LlmStatus;
}
/** GET /api/runs/{run}/patients/{id}: what the simulation shows about a patient (never the latent truth). */
export interface RunPatient {
  live?: {
    patient_id: number;
    display_id?: string;
    acuity?: number;
    condition_group?: string;
    state?: string;
    arrival_mode?: string;
    flag_names?: string[];
    room?: string;
    bay?: string;
    bay_class?: string;
    orders?: string[];
    disposition?: string;
    held_for_play?: boolean;
    encounter_quality?: number;
    door_to_provider_min?: number;
    remaining_min?: number;
  };
  interactions?: InteractionResult[];
  pending_interaction?: {
    interaction_type?: string;
    status?: string;
    held?: boolean;
    t_start?: number;
    sampled_duration_min?: number;
    participants?: { entity_id: number | string; role: string; played_by?: string; playable?: boolean }[];
    playable?: boolean;
  } | null;
}
/** What the sampler had drawn for this patient's clinician encounter before a person took it over. */
export interface SampledBaseline {
  captured_at: string;
  duration_min?: number;
  quality?: number;
  orders?: string[];
  disposition?: string;
  bay?: string;
  acuity?: number;
  condition_group?: string;
  clinician?: string;
  hospital_id?: string;
  hospital_name?: string;
}
