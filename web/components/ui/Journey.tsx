"use client";
import type { FeedState } from "@/lib/feed";
import { enumsOf } from "@/lib/describe";
import { duration, L, patientId, tickLabel } from "@/lib/format";
import { ACUITY, ACUITY_SHORT } from "@/lib/palette";
import { useUI } from "@/lib/ui";
import { SimTag } from "./atoms";

interface Step {
  label: string;
  /** tick when the step began, if known */
  t: number | null;
  status: "done" | "current" | "todo" | "skipped";
  note?: string;
}

/** Patient journey from what the snapshots show: arrival, triage, bay, provider, tests, disposition, ward / discharge. */
export function journeySteps(f: FeedState, id: number): { steps: Step[]; found: boolean; acuity: number } {
  const e = enumsOf(f);
  const snap = f.snap;
  const now = snap?.t ?? 0;
  const hist = (f.journeys.get(id) ?? []).filter((j) => j.t <= now);
  const idx = snap ? snap.patients.id.indexOf(id) : -1;
  const S = (name: string) => e.patient_state.indexOf(name);
  const first = (...names: string[]) => {
    const set = new Set(names.map(S));
    const h = hist.find((j) => set.has(j.s));
    return h ? h.t : null;
  };
  const acuity = idx >= 0 && snap ? snap.patients.acuity[idx] : 0;
  const arrival = idx >= 0 && snap ? now - Math.round(snap.patients.age_min[idx] / (f.header?.tick_minutes ?? 5)) : (hist[0]?.t ?? null);
  // current state, ignoring "walking" (use the last real state)
  let curName = "";
  for (let i = hist.length - 1; i >= 0; i--) {
    const nm = e.patient_state[hist[i].s];
    if (nm && nm !== "walking") {
      curName = nm;
      break;
    }
  }
  if (!curName && idx >= 0 && snap) curName = e.patient_state[snap.patients.state[idx]] ?? "";
  const lastExit = hist.length ? hist[hist.length - 1].exit : 0;
  const exitName = e.patient_exit[idx >= 0 && snap ? snap.patients.exit[idx] : lastExit] ?? "none";
  const gone = curName === "exited" || (idx < 0 && hist.length > 0);
  const rank: Record<string, number> = { waiting_triage: 0, in_triage: 1, waiting_bay: 1.5, waiting_provider: 2, with_provider: 3, waiting_test: 4, in_test: 4, waiting_results: 5, boarding: 5.5, in_ward: 6, exited: 7 };
  const r = gone ? 7 : (rank[curName] ?? 0);
  const admitted = idx >= 0 && snap ? (snap.patients.flags[idx] & 2) !== 0 : false;
  const tests = first("waiting_test", "in_test");
  const mk = (label: string, pos: number, t: number | null, note?: string): Step => ({
    label,
    t,
    note,
    status: r > pos + 0.6 || (gone && pos < 7) ? (t == null && label === "Tests" ? "skipped" : "done") : Math.abs(r - pos) <= 0.5 ? "current" : "todo",
  });
  const steps: Step[] = [
    mk("Arrival", 0, arrival),
    mk("Triage", 1, first("in_triage"), curName === "waiting_bay" ? "waiting for a bay" : undefined),
    mk("Bay", 2, first("waiting_provider")),
    mk("Provider", 3, first("with_provider")),
    mk("Tests", 4, tests),
    mk("Disposition", 5, first("waiting_results", "boarding"), curName === "boarding" ? "admitted · boarding" : admitted ? "admit" : undefined),
    {
      label: gone ? L.exit(e, e.patient_exit.indexOf(exitName)) : admitted || curName === "in_ward" ? "Ward" : "Ward / discharge",
      t: first("in_ward") ?? (gone ? (hist[hist.length - 1]?.t ?? null) : null),
      status: gone ? "done" : curName === "in_ward" ? "current" : "todo",
    },
  ];
  if (curName === "waiting_bay") steps[1].status = "current";
  if (curName === "boarding") steps[5].status = "current";
  return { steps, found: idx >= 0 || hist.length > 0, acuity };
}

export function JourneyStepper({ f, className = "" }: { f: FeedState; className?: string }) {
  const sel = useUI((s) => s.selection);
  const isPatient = sel?.kind === "patient" && sel.feed === f.key;
  if (!isPatient)
    return (
      <div className={`glass pointer-events-auto flex items-center gap-3 px-4 py-3 ${className}`} data-testid="journey">
        <div className="flex gap-1">
          {[0, 1, 2, 3, 4, 5, 6].map((i) => (
            <span key={i} className="h-1.5 w-5 rounded-full bg-[#141a33]/[0.07]" />
          ))}
        </div>
        <span className="text-[12px] text-ink-3">Select a patient to follow their journey.</span>
      </div>
    );
  const id = Number(sel.id);
  const { steps, found, acuity } = journeySteps(f, id);
  const tm = f.header?.tick_minutes ?? 5;
  const now = f.snap?.t ?? 0;
  return (
    <div className={`glass pointer-events-auto px-4 pb-3 pt-3 ${className}`} data-testid="journey">
      <div className="mb-2.5 flex items-center gap-2">
        <span className="eyebrow">Patient journey</span>
        <span className="h-2 w-2 rounded-full" style={{ background: ACUITY[acuity] }} />
        <span className="text-[12px] font-semibold text-ink">{patientId(id)}</span>
        {acuity ? <span className="text-[11px] text-ink-3">{ACUITY_SHORT[acuity]}</span> : null}
        <span className="ml-auto">
          <SimTag />
        </span>
      </div>
      {!found ? (
        <div className="text-[12px] text-ink-3">No record of this patient in the snapshots loaded so far.</div>
      ) : (
        <ol className="flex items-start">
          {steps.map((s, i) => {
            const done = s.status === "done";
            const cur = s.status === "current";
            const next = steps[i + 1];
            const lineOn = done && next && next.status !== "todo";
            const dur = s.t != null ? (cur ? (now - s.t) * tm : next?.t != null ? (next.t - s.t) * tm : null) : null;
            return (
              <li key={i} className="relative min-w-0 flex-1">
                {i < steps.length - 1 && <span className="absolute left-[9px] right-[-9px] top-[8px] h-[2px] rounded-full" style={{ background: lineOn ? "#2F55F5" : "rgba(20,26,51,0.1)" }} />}
                <span
                  className="relative z-[1] flex h-[18px] w-[18px] items-center justify-center rounded-full"
                  style={{
                    background: cur ? "#2F55F5" : done ? "#2F55F5" : "#fff",
                    border: done || cur ? "none" : `2px ${s.status === "skipped" ? "dashed" : "solid"} rgba(20,26,51,0.16)`,
                    boxShadow: cur ? "0 0 0 4px rgba(47,85,245,0.2)" : undefined,
                  }}
                >
                  {done && (
                    <svg width="9" height="9" viewBox="0 0 10 10" aria-hidden>
                      <path d="M2 5.2l2 2 4-4.4" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                  {cur && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
                </span>
                <div className={`mt-1.5 truncate pr-1 text-[11px] font-semibold ${cur ? "text-accent-dark" : done ? "text-ink" : "text-ink-3"}`}>{s.label}</div>
                <div className="tnum truncate pr-1 text-[10.5px] text-ink-3">{s.status === "skipped" ? "none seen" : s.t != null ? tickLabel(s.t, tm).slice(4) : done ? "earlier" : "–"}</div>
                {(cur || s.note) && <div className="tnum truncate pr-1 text-[10.5px] font-medium text-ink-2">{s.note ?? (dur != null ? duration(dur) : "")}</div>}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
