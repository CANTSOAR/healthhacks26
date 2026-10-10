// Typed client for contracts/api.md, with a fixture fallback.
// Every call resolves to {data, source}: "live" when the server answered, "fixture" when it did not and
// the bundled file under /fixtures was used instead. Screens label fixture data as such.
import type { CatalogRef, CatalogSummary, Enums, Hospital, HumanRun, Layout, ManagerInfo, Results, Rollout, RolloutListItem, Scenario, ServiceStatus, Validation } from "./types";

export type Source = "live" | "fixture";
export interface Sourced<T> {
  data: T;
  source: Source;
}

const DEFAULT_BASE = "http://localhost:8000";
const HUMAN_KEY = "hg.human_runs";

/** Base URL: `?api=` in the address bar (remembered for the tab) > NEXT_PUBLIC_API_URL > http://localhost:8000. */
export function apiBase(): string {
  if (typeof window !== "undefined") {
    try {
      const q = new URLSearchParams(window.location.search).get("api");
      if (q) window.sessionStorage.setItem("hg.api", q);
      const s = window.sessionStorage.getItem("hg.api");
      if (s) return s.replace(/\/$/, "");
    } catch {
      /* storage blocked */
    }
  }
  return (process.env.NEXT_PUBLIC_API_URL || DEFAULT_BASE).replace(/\/$/, "");
}
export const wsBase = () => apiBase().replace(/^http/, "ws");

// ---- reachability: after a network failure, skip the network for a few seconds so screens stay snappy offline.
let downUntil = 0;
const listeners = new Set<(online: boolean) => void>();
let lastOnline: boolean | null = null;
function setOnline(v: boolean) {
  if (!v) downUntil = Date.now() + 8000;
  else downUntil = 0;
  if (lastOnline !== v) {
    lastOnline = v;
    listeners.forEach((f) => f(v));
  }
}
export function onReachability(f: (online: boolean) => void) {
  listeners.add(f);
  return () => {
    listeners.delete(f);
  };
}
export const serverKnownOnline = () => lastOnline === true;

async function live<T>(path: string, init?: RequestInit, timeoutMs = 2500): Promise<T> {
  if (Date.now() < downUntil) throw new Error("server marked unreachable");
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const res = await fetch(apiBase() + path, { ...init, signal: ctl.signal, cache: "no-store" });
    setOnline(true);
    if (!res.ok) throw new HttpError(res.status, path);
    return (await res.json()) as T;
  } catch (e) {
    if (!(e instanceof HttpError)) setOnline(false);
    throw e;
  } finally {
    clearTimeout(timer);
  }
}
export class HttpError extends Error {
  constructor(public status: number, path: string) {
    super(`${status} from ${path}`);
  }
}

const cache = new Map<string, Promise<unknown>>();
function fixture<T>(file: string): Promise<T> {
  let p = cache.get(file) as Promise<T> | undefined;
  if (!p) {
    p = fetch(`/fixtures/${file}`).then((r) => {
      if (!r.ok) throw new Error(`missing fixture ${file}`);
      return r.json() as Promise<T>;
    });
    cache.set(file, p);
    p.catch(() => cache.delete(file));
  }
  return p;
}

async function get<T>(path: string, fallback: () => Promise<T>, timeoutMs?: number): Promise<Sourced<T>> {
  try {
    return { data: await live<T>(path, undefined, timeoutMs), source: "live" };
  } catch {
    return { data: await fallback(), source: "fixture" };
  }
}

function localHumanRuns(): HumanRun[] {
  try {
    return JSON.parse(window.localStorage.getItem(HUMAN_KEY) || "[]") as HumanRun[];
  } catch {
    return [];
  }
}

export const api = {
  status: () => get<ServiceStatus>("/api/status", () => fixture("status.json"), 1500),
  enums: () => get<Enums>("/api/enums", () => fixture("enums.json")),
  metrics: () => get<{ metrics: Record<string, { unit: string; desc: string; window?: string; episode?: string }>; episode_summary?: Record<string, string> }>("/api/metrics", () => fixture("metrics.json")),
  catalog: () => get<CatalogSummary>("/api/catalog", () => fixture("catalog.json")),
  catalogRef: async (ref: string): Promise<Sourced<CatalogRef | null>> => {
    try {
      return { data: await live<CatalogRef>(`/api/catalog/ref/${ref.split("/").map(encodeURIComponent).join("/")}`), source: "live" };
    } catch (e) {
      // the server answered "no such entry": that is the truth, do not paper over it with a fixture
      if (e instanceof HttpError && e.status === 404) return { data: null, source: "live" };
      const all = await fixture<Record<string, CatalogRef>>("catalog-refs.json");
      return { data: all[ref] ?? null, source: "fixture" };
    }
  },
  /** Baseline simulator outputs against published benchmarks. Offline there is nothing honest to show. */
  validation: () => get<Validation>("/api/validation", async () => ({ status: "offline", targets: [], simulated: {}, within: {} }), 6000),
  scenarios: () => get<Scenario[]>("/api/scenarios", () => fixture("scenarios.json")),
  hospitals: () => get<Hospital[]>("/api/hospitals", () => fixture("hospitals.json")),
  layout: (hospitalId: string) => get<Layout>(`/api/layout/${encodeURIComponent(hospitalId)}`, () => fixture(hospitalId === "rwjuh_nb" ? "rwjuh_nb.layout.json" : "layout.fixture.json")),
  managers: () => get<ManagerInfo[]>("/api/managers", () => fixture("managers.json")),
  rollouts: () => get<RolloutListItem[]>("/api/rollouts", () => fixture("rollouts.json")),
  rollout: (id: string) =>
    get<Rollout>(`/api/rollouts/${encodeURIComponent(id)}`, () => fixture(id === "fixture_b" ? "rollout.fixture_b.json" : "rollout.fixture.json"), 15000),
  results: async (): Promise<Sourced<Results>> => {
    const r = await get<Results>("/api/results", () => fixture("results.json"));
    if (r.source === "fixture") {
      // offline: the human player's runs are kept in this browser only
      return { source: "fixture", data: { ...r.data, human_runs: [...(r.data.human_runs || []), ...localHumanRuns()] } };
    }
    return r;
  },
  /** Stores the human player's last run. Offline it is kept in localStorage so the trade-off chart can still show it. */
  postHumanRun: async (run: HumanRun): Promise<Source> => {
    try {
      await live("/api/results/human", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(run) });
      return "live";
    } catch {
      try {
        const runs = localHumanRuns().filter((r) => r.scenario !== run.scenario).concat([{ ...run, created: new Date().toISOString() }]);
        window.localStorage.setItem(HUMAN_KEY, JSON.stringify(runs));
      } catch {
        /* storage blocked */
      }
      return "fixture";
    }
  },
  runPatient: (runId: string, patientId: number) => live<Record<string, unknown>>(`/api/runs/${encodeURIComponent(runId)}/patients/${patientId}`),
  runStaff: (runId: string, staffId: string) => live<Record<string, unknown>>(`/api/runs/${encodeURIComponent(runId)}/staff/${encodeURIComponent(staffId)}`),
};
