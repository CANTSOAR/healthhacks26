// Client for the journey routes (encounter/journey/api.py), served next to the encounter routes under /api.
import { apiBase } from "@/lib/api";
import { ApiError } from "@/lib/encounter/api";
import type { CarePlan, Debrief, JourneyState, StageTurn, StageView, TemplateSummary } from "./types";

async function call<T>(path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiBase() + path, {
      method: body !== undefined ? "POST" : "GET",
      headers: body !== undefined ? { "content-type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, `The server at ${apiBase()} did not answer. Start it with ./run_server.sh and try again.`);
  }
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const d = (data as { detail?: unknown } | null)?.detail;
    const msg = typeof d === "string" ? d : ((d as { message?: string } | undefined)?.message ?? `${res.status} from ${path}`);
    throw new ApiError(res.status, res.status === 404 && path === "/api/journeys/templates" ? "This server does not have the journey routes yet. Restart it to pick them up." : msg, typeof d === "object" && d ? (d as Record<string, unknown>) : undefined);
  }
  return data as T;
}

const e = encodeURIComponent;
export const journeyApi = {
  templates: (caseId?: string) => call<TemplateSummary[]>(`/api/journeys/templates${caseId ? `?case_id=${e(caseId)}` : ""}`),
  start: (body: { case_id: string; template_id?: string } | { run_id: string; patient_id: number; template_id?: string }) => call<JourneyState>("/api/journeys", body),
  get: (id: string) => call<JourneyState>(`/api/journeys/${e(id)}`),
  auto: (id: string, until?: string) => call<JourneyState>(`/api/journeys/${e(id)}/auto`, until ? { until } : {}),
  startStage: (id: string, sid: string, mode: "human" | "auto") => call<StageView>(`/api/journeys/${e(id)}/stages/${e(sid)}/start`, { mode }),
  stage: (id: string, sid: string) => call<StageView>(`/api/journeys/${e(id)}/stages/${e(sid)}`),
  turn: (id: string, sid: string, text: string, request_id: string) => call<StageTurn>(`/api/journeys/${e(id)}/stages/${e(sid)}/turn`, { text, request_id }),
  answer: (id: string, sid: string, text: string) => call<StageView>(`/api/journeys/${e(id)}/stages/${e(sid)}/turn`, { text }),
  request: (id: string, sid: string, request: string, request_id: string) => call<StageTurn>(`/api/journeys/${e(id)}/stages/${e(sid)}/request`, { request, request_id }),
  sbar: (id: string, sid: string, body: Record<string, string>) => call<StageView>(`/api/journeys/${e(id)}/stages/${e(sid)}/sbar`, body),
  finish: (id: string, sid: string, body: Record<string, unknown>) => call<StageView>(`/api/journeys/${e(id)}/stages/${e(sid)}/finish`, body),
  carePlan: (id: string) => call<CarePlan>(`/api/journeys/${e(id)}/care-plan`),
  debrief: (id: string) => call<Debrief>(`/api/journeys/${e(id)}/debrief`),
};

// One colour per professional role, used for every provenance chip and avatar so a role reads the same everywhere.
export const ROLE_TONE: Record<string, { bg: string; fg: string }> = {
  rn: { bg: "#E0F4F1", fg: "#0F6B5E" },
  charge_rn: { bg: "#E0F4F1", fg: "#0F6B5E" },
  resident: { bg: "#E3E9FF", fg: "#1F3FD1" },
  attending: { bg: "#E9E4FB", fg: "#5B3FC4" },
  app: { bg: "#E3E9FF", fg: "#1F3FD1" },
  pharmacist: { bg: "#FBE9F1", fg: "#A8326B" },
};
export const roleTone = (staffRole?: string) => ROLE_TONE[staffRole ?? ""] ?? { bg: "rgba(20,26,51,0.06)", fg: "#4A5275" };
export const ACTOR_LABEL: Record<string, string> = { human: "You", sampled: "Sampled", ai: "AI colleague", sim: "Simulation" };
export const KIND_LABEL: Record<string, string> = {
  fact: "Finding",
  patient_report: "Patient said",
  order: "Request",
  artifact: "Document",
  decision: "Decision",
  note: "Note",
  medication: "Medicine",
  plan: "Plan",
  question: "Open question",
  handoff: "Handoff",
};
export const TYPE_LABEL: Record<string, string> = { triage: "Triage", clinician_encounter: "Clinician encounter", nursing_assessment: "Nursing assessment", handoff: "Handoff", disposition: "Disposition", discharge_planning: "Discharge planning" };
/** "Triage nurse" -> "triage nurse"; "ED pharmacist" keeps its abbreviation. */
export const lc = (label: string) => (/^[A-Z]{2,}\b/.test(label) ? label : label.charAt(0).toLowerCase() + label.slice(1));
