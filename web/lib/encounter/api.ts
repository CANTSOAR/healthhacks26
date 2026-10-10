// Client for the Encounter section of contracts/api.md (router: encounter/api.py).
// Student pages only ever call the student routes here; the faculty case routes are used by /studio.
import { apiBase } from "@/lib/api";
import type {
  CaseDoc,
  CaseSummary,
  CreatedCase,
  EncounterStart,
  EncounterState,
  FinishResponse,
  RubricSummary,
  RunPatient,
  ServiceStatus,
  StudentCaseView,
  TemplateSummary,
  TurnResponse,
  ValidationReport,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: Record<string, unknown>,
  ) {
    super(message);
  }
  /** A validation report travels with a 422 from approve/publish. */
  get report(): ValidationReport | null {
    const d = this.detail as Partial<ValidationReport> | undefined;
    return d && Array.isArray(d.errors) ? { ok: false, errors: d.errors, warnings: d.warnings ?? [], consistency: d.consistency ?? [] } : null;
  }
}

async function call<T>(path: string, init?: { method?: string; body?: unknown; timeoutMs?: number }): Promise<T> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), init?.timeoutMs ?? 45000);
  let res: Response;
  try {
    res = await fetch(apiBase() + path, {
      method: init?.method ?? (init?.body !== undefined ? "POST" : "GET"),
      headers: init?.body !== undefined ? { "content-type": "application/json" } : undefined,
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
      signal: ctl.signal,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, `The server at ${apiBase()} did not answer. Start it with ./run_server.sh and try again.`);
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 204) return undefined as T;
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* empty or non-JSON body */
  }
  if (!res.ok) {
    const d = (data as { detail?: unknown } | null)?.detail;
    const msg = typeof d === "string" ? d : ((d as { message?: string } | undefined)?.message ?? `${res.status} from ${path}`);
    throw new ApiError(res.status, msg, typeof d === "object" && d ? (d as Record<string, unknown>) : undefined);
  }
  return data as T;
}

const enc = encodeURIComponent;

export const encApi = {
  status: () => call<ServiceStatus>("/api/status", { timeoutMs: 4000 }),

  // ---- cases
  cases: (status?: string) => call<CaseSummary[]>(`/api/cases${status ? `?status=${status}` : ""}`),
  caseStudent: (id: string) => call<StudentCaseView>(`/api/cases/${enc(id)}?view=student`),
  caseFaculty: (id: string, version?: number) => call<CaseDoc>(`/api/cases/${enc(id)}${version ? `?version=${version}` : ""}`),
  createCase: (body: Record<string, unknown>) => call<CreatedCase>("/api/cases", { body }),
  updateCase: (id: string, body: Record<string, unknown>) => call<CaseDoc & { validation: ValidationReport; new_version_created: boolean }>(`/api/cases/${enc(id)}`, { method: "PUT", body }),
  validateCase: (id: string, body?: Record<string, unknown>) => call<ValidationReport>(`/api/cases/${enc(id)}/validate`, { method: "POST", body: body ?? {} }),
  approveCase: (id: string, reviewer?: string) => call<CaseDoc>(`/api/cases/${enc(id)}/approve`, { body: reviewer ? { reviewer } : {} }),
  publishCase: (id: string) => call<CaseDoc>(`/api/cases/${enc(id)}/publish`, { body: {} }),
  templates: () => call<TemplateSummary[]>("/api/templates"),
  rubrics: () => call<RubricSummary[]>("/api/rubrics"),

  // ---- encounters
  start: (body: { case_id: string; version?: number; preview?: boolean } | { run_id: string; patient_id: number }) => call<EncounterStart>("/api/encounters", { body }),
  get: (id: string) => call<EncounterState>(`/api/encounters/${enc(id)}`),
  turn: (id: string, text: string, request_id: string) => call<TurnResponse>(`/api/encounters/${enc(id)}/turn`, { body: { text, request_id }, timeoutMs: 90000 }),
  request: (id: string, request: string, request_id: string) => call<TurnResponse>(`/api/encounters/${enc(id)}/request`, { body: { request, request_id } }),
  finish: (id: string, body: { disposition: string; orders: string[]; summary: string }) => call<FinishResponse>(`/api/encounters/${enc(id)}/finish`, { body, timeoutMs: 120000 }),

  // ---- the running simulation (read-only context for a simulated patient; never the latent truth)
  runPatient: (runId: string, patientId: number) => call<RunPatient>(`/api/runs/${enc(runId)}/patients/${patientId}`, { timeoutMs: 6000 }),
  runs: () => call<{ run_id: string; hospital_id?: string; scenario?: string; t?: number }[]>("/api/runs", { timeoutMs: 4000 }),
  hospitals: () => call<{ id: string; name: string }[]>("/api/hospitals", { timeoutMs: 4000 }),

  /** Server speech when a voice key is configured (200 audio); null on 204 so the browser speaks instead. */
  tts: async (text: string, voice?: string): Promise<Blob | null> => {
    try {
      const res = await fetch(apiBase() + "/api/tts", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, voice }) });
      if (res.status !== 200) return null;
      const b = await res.blob();
      return b.size ? b : null;
    } catch {
      return null;
    }
  },
};

/** Absolute URL for an image path the API returned (e.g. /api/cases/<id>/image). */
export const assetUrl = (path?: string | null) => (!path ? null : /^https?:/.test(path) ? path : apiBase() + path);

export const newRequestId = () => `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
