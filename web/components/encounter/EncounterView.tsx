"use client";
// One encounter: starts (or resumes) a session, runs the conversation, finishes it and shows feedback.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, encApi, newRequestId } from "@/lib/encounter/api";
import { forgetOpenEncounter, giveBack, rememberOpenEncounter } from "@/lib/encounter/open";
import { bayLabel, mmss, requestLabel, shortHospital, simClock } from "@/lib/encounter/labels";
import type { AvailableRequest, Chart, EncounterStart, EncounterState, Feedback, InteractionResult, LearnerCase, LedgerEvent, LlmStatus, PatientView, RunPatient, SampledBaseline, SimBinding } from "@/lib/encounter/types";
import { speak, stopSpeaking } from "@/lib/encounter/voice";
import { ChartPane } from "./ChartPane";
import { ConversationPane, type Msg } from "./ConversationPane";
import { FeedbackView } from "./FeedbackView";
import { SiteDisclaimer } from "../ui/SiteDisclaimer";
import { ErrorCard, Field, InlineError, inputCls, LoadingCard, Modal, ProviderChip, Spinner, SyntheticLabel } from "./ui";

export interface EncounterParams {
  encounterId?: string;
  caseId?: string;
  version?: number;
  preview?: boolean;
  runId?: string;
  patientId?: number;
}

interface Session {
  id: string;
  kase: LearnerCase;
  patient: PatientView;
  chart: Chart;
  requests: AvailableRequest[];
  sim: SimBinding | null;
  preview: boolean;
  llm: LlmStatus | null;
  startedAt: number;
}

const BASE_KEY = (id: string) => `hg.enc.baseline.${id}`;
const VOICE_KEY = "hg.enc.voice";

// A start is a POST with side effects (it holds the simulated patient), so the same parameters never start twice
// in one page load, whatever React does with effects.
/** The encounter id this page put into the address bar itself (so the route does not treat it as a new request). */
export const selfStarted = { id: null as string | null };
const starts = new Map<string, Promise<{ started: EncounterStart; baseline: SampledBaseline | null }>>();

/** Back to the hospital on the same run, with this patient selected (the app rejoins the run it finds in the link). */
export function hospitalHref(sim: { run_id?: string | null; patient_id?: number | string | null }): string {
  if (!sim.run_id) return "/?mode=play";
  return `/?run_id=${encodeURIComponent(sim.run_id)}${sim.patient_id != null ? `&patient_id=${encodeURIComponent(String(sim.patient_id))}` : ""}`;
}

async function captureBaseline(runId: string, patientId: number): Promise<SampledBaseline | null> {
  try {
    const [p, runs, hospitals] = await Promise.all([encApi.runPatient(runId, patientId), encApi.runs().catch(() => []), encApi.hospitals().catch(() => [])]);
    const run = runs.find((r) => r.run_id === runId);
    const hosp = hospitals.find((h) => h.id === run?.hospital_id);
    const md = p.pending_interaction?.participants?.find((x) => x.role !== "patient");
    return {
      captured_at: new Date().toISOString(),
      duration_min: p.pending_interaction?.sampled_duration_min,
      quality: p.live?.encounter_quality,
      orders: p.live?.orders,
      disposition: p.live?.disposition,
      bay: p.live?.bay ?? p.live?.room,
      state: p.live?.state,
      in_bay: !!p.live?.bay,
      acuity: p.live?.acuity,
      condition_group: p.live?.condition_group,
      clinician: md ? `${md.entity_id} (${md.role})` : undefined,
      hospital_id: run?.hospital_id,
      hospital_name: hosp?.name,
    };
  } catch {
    return null;
  }
}

function startOnce(p: EncounterParams) {
  const key = JSON.stringify([p.caseId, p.version, p.preview, p.runId, p.patientId]);
  let pr = starts.get(key);
  if (!pr) {
    pr = (async () => {
      if (p.runId && p.patientId != null) {
        // read what the sampler had drawn for this patient before taking the encounter over
        const baseline = await captureBaseline(p.runId, p.patientId);
        const started = await encApi.start({ run_id: p.runId, patient_id: p.patientId });
        return { started, baseline };
      }
      const started = await encApi.start({ case_id: p.caseId!, ...(p.version ? { version: p.version } : {}), ...(p.preview ? { preview: true } : {}) });
      return { started, baseline: null };
    })();
    starts.set(key, pr);
    // forget it shortly after it settles, so "Try again" on the same case starts a fresh session
    const forget = () => setTimeout(() => starts.delete(key), 1500);
    pr.then(forget, () => starts.delete(key));
  }
  return pr;
}

function messagesFromLedger(ledger: LedgerEvent[]): Msg[] {
  const out: Msg[] = [];
  for (const e of [...ledger].sort((a, b) => a.seq - b.seq)) {
    if (e.kind === "turn") {
      out.push({ id: `s${e.seq}`, who: "student", text: e.text ?? "", turn: e.turn });
      if (e.reply) out.push({ id: `p${e.seq}`, who: "patient", text: e.reply, turn: e.turn, fallback: !!e.fallback, unlocked: e.disclosed_fact_ids.length + e.released_artifact_ids.length || undefined });
    } else if (e.kind === "request") {
      const n = e.disclosed_fact_ids.length + e.released_artifact_ids.length;
      out.push({ id: `r${e.seq}`, who: "system", text: `Requested ${requestLabel(e.request ?? "")}${n ? " · result added to the chart" : e.result === "not_available" ? " · not available in this case" : ""}`, turn: e.turn });
    }
  }
  return out;
}

function mergeLedger(prev: LedgerEvent[], tail: LedgerEvent[]): LedgerEvent[] {
  const m = new Map(prev.map((e) => [e.seq, e]));
  tail.forEach((e) => m.set(e.seq, e));
  return [...m.values()].sort((a, b) => a.seq - b.seq);
}

function noteText(n: string): string {
  // "troponin: result added to the chart." -> "Troponin: result added to the chart."
  const i = n.indexOf(":");
  if (i > 0 && i < 30) return requestLabel(n.slice(0, i).replace(/ /g, "_")) + n.slice(i);
  return n;
}

const STATE_WHERE: Record<string, string> = {
  waiting_triage: "waiting for triage",
  in_triage: "at triage",
  waiting_bay: "in the waiting room, waiting for a treatment bay",
  waiting_provider: "in a treatment bay, waiting for the provider",
  with_provider: "in a treatment bay with the provider",
};
/** Where the simulated patient was when the encounter was taken over, in words that fit that place (never "a bed" for triage). */
function simWhere(b: SampledBaseline | null, finished: boolean): string {
  if (finished) return "this encounter is finished; the patient carries on in the running simulation";
  const where = b?.state ? STATE_WHERE[b.state] : undefined;
  if (where) return `this patient is ${where} in the running simulation`;
  if (b?.in_bay) return "this patient is in a treatment bay in the running simulation";
  return "this patient is in the running simulation";
}

const DISPOSITIONS: { key: string; label: string; hint: string }[] = [
  { key: "discharge", label: "Discharge", hint: "Home with advice and follow-up" },
  { key: "admit", label: "Admit", hint: "Stay in hospital" },
  { key: "transfer", label: "Transfer", hint: "Move to another facility" },
  { key: "undecided", label: "Undecided", hint: "Not ready to decide" },
];

function FinishDialog({ requests, requested, busy, error, onCancel, onSubmit }: { requests: AvailableRequest[]; requested: Set<string>; busy: boolean; error: string | null; onCancel: () => void; onSubmit: (b: { disposition: string; orders: string[]; summary: string }) => void }) {
  const [disposition, setDisposition] = useState("undecided");
  const [orders, setOrders] = useState<string[]>([]);
  const [summary, setSummary] = useState("");
  const [pick, setPick] = useState("");
  const orderable = requests.filter((r) => r.request.startsWith("order:") && !requested.has(r.request) && !orders.includes(r.request));
  const already = [...requested].filter((r) => r.startsWith("order:"));
  return (
    <Modal title="Finish the encounter" onClose={busy ? () => {} : onCancel}>
      <div className="space-y-4" data-testid="finish-form">
        <p className="text-[12.5px] leading-relaxed text-ink-2">Record your decision. The grader reads the transcript, your requests and this form; it does not see anything you did not say or do.</p>
        <div>
          <div className="mb-1.5 text-[11px] font-semibold text-ink-2">Disposition</div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="radiogroup" aria-label="Disposition">
            {DISPOSITIONS.map((d) => (
              <button key={d.key} role="radio" aria-checked={disposition === d.key} onClick={() => setDisposition(d.key)} className={`rounded-xl border px-2.5 py-2 text-left transition-colors ${disposition === d.key ? "border-accent bg-accent-soft" : "border-line bg-white/70 hover:border-accent/30"}`} data-testid={`disposition-${d.key}`}>
                <span className={`block text-[12.5px] font-semibold ${disposition === d.key ? "text-accent-dark" : "text-ink"}`}>{d.label}</span>
                <span className="block text-[10.5px] leading-snug text-ink-3">{d.hint}</span>
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="mb-1.5 text-[11px] font-semibold text-ink-2">Orders</div>
          <div className="flex flex-wrap items-center gap-1.5">
            {already.map((o) => (
              <span key={o} className="chip" style={{ background: "#E3F4EA", color: "#1F7A4D" }} title="Requested during the encounter">
                ✓ {requestLabel(o)}
              </span>
            ))}
            {orders.map((o) => (
              <button key={o} className="chip" style={{ background: "#E3E9FF", color: "#1F3FD1" }} onClick={() => setOrders(orders.filter((x) => x !== o))} title="Remove">
                {requestLabel(o)} ×
              </button>
            ))}
            {already.length + orders.length === 0 && <span className="text-[12px] text-ink-3">None yet.</span>}
          </div>
          {orderable.length > 0 && (
            <select
              className="select mt-2 max-w-full"
              value={pick}
              onChange={(e) => {
                if (e.target.value) setOrders([...orders, e.target.value]);
                setPick("");
              }}
              aria-label="Add an order"
              data-testid="finish-add-order"
            >
              <option value="">Add an order to place now…</option>
              {orderable.map((r) => (
                <option key={r.request} value={r.request}>
                  {requestLabel(r.request)}
                </option>
              ))}
            </select>
          )}
        </div>
        <Field label="Summary" hint="One paragraph: what you think is going on, the findings that support it, and your plan.">
          <textarea className={`${inputCls} min-h-[96px]`} value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={4000} placeholder="e.g. 41-year-old man with central chest pressure at rest, lateral ST depression and a raised first troponin. Admit for serial troponins…" data-testid="finish-summary" />
        </Field>
        {error && <InlineError>{error}</InlineError>}
        <div className="flex items-center justify-end gap-2">
          <button className="btn" onClick={onCancel} disabled={busy}>
            Keep talking
          </button>
          <button className="btn-primary" disabled={busy} onClick={() => onSubmit({ disposition, orders, summary })} data-testid="finish-submit">
            {busy ? (
              <>
                <Spinner size={12} /> Grading…
              </>
            ) : (
              "Finish and get feedback"
            )}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export function EncounterView({ params }: { params: EncounterParams }) {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState<{ title: string; message: string; status?: number } | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [ledger, setLedger] = useState<LedgerEvent[]>([]);
  const [rapport, setRapport] = useState<number | null>(null);
  const [requested, setRequested] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [turnError, setTurnError] = useState<string | null>(null);
  const [fellBack, setFellBack] = useState(false);
  const [voiceOn, setVoiceOn] = useState(false);
  const [pane, setPane] = useState<"talk" | "chart">("talk");
  const [chartDot, setChartDot] = useState(false);
  const [finishOpen, setFinishOpen] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [finishError, setFinishError] = useState<string | null>(null);
  const [done, setDone] = useState<{ feedback: Feedback; result: InteractionResult | null; writtenBack: boolean; writeBack?: { status: "applied" | "queued" | "rejected" | "not_applicable"; detail?: string } | null } | null>(null);
  const [baseline, setBaseline] = useState<SampledBaseline | null>(null);
  const [after, setAfter] = useState<RunPatient | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const voiceRef = useRef(false);
  voiceRef.current = voiceOn;

  const key = JSON.stringify(params);
  useEffect(() => {
    let dead = false;
    try {
      setVoiceOn(window.localStorage.getItem(VOICE_KEY) === "1");
    } catch {
      /* storage blocked */
    }
    const hydrate = (s: EncounterState) => {
      setSession({ id: s.encounter_id, kase: s.case, patient: s.patient, chart: s.chart, requests: s.available_requests, sim: s.sim ?? null, preview: !!s.preview, llm: s.llm ?? null, startedAt: Date.parse(s.started) || Date.now() });
      setLedger(s.ledger);
      setMessages(messagesFromLedger(s.ledger));
      setRapport(typeof s.rapport === "number" ? s.rapport : null);
      setRequested(new Set(s.ledger.filter((e) => e.kind === "request" && e.request).map((e) => e.request!)));
      setFellBack(s.ledger.some((e) => e.fallback));
      try {
        const b = window.sessionStorage.getItem(BASE_KEY(s.encounter_id));
        if (b) setBaseline(JSON.parse(b) as SampledBaseline);
      } catch {
        /* ignore */
      }
      // an unfinished encounter on a simulated patient: the hospital's inspector can find its way back here
      if (s.sim?.run_id && s.sim.patient_id != null) {
        if (s.status === "finished") forgetOpenEncounter(s.sim.run_id, s.sim.patient_id);
        else rememberOpenEncounter(s.sim.run_id, s.sim.patient_id, s.encounter_id);
      }
      if (s.status === "finished" && s.feedback) {
        setElapsed(Math.max(0, ((Date.parse(s.finished ?? "") || Date.now()) - (Date.parse(s.started) || Date.now())) / 1000));
        setDone({ feedback: s.feedback, result: s.interaction_result ?? null, writtenBack: !!s.written_back, writeBack: s.write_back ?? null });
      }
    };
    (async () => {
      try {
        if (params.encounterId) {
          const s = await encApi.get(params.encounterId);
          if (!dead) hydrate(s);
          return;
        }
        const { started, baseline: base } = await startOnce(params);
        if (dead) return;
        if (base) {
          setBaseline(base);
          try {
            window.sessionStorage.setItem(BASE_KEY(started.encounter_id), JSON.stringify(base));
          } catch {
            /* ignore */
          }
        }
        setSession({ id: started.encounter_id, kase: started.case, patient: started.patient, chart: started.chart, requests: started.available_requests, sim: started.sim ?? null, preview: !!started.preview, llm: started.llm, startedAt: Date.now() });
        setRapport(typeof started.rapport === "number" ? started.rapport : null);
        if (started.sim?.run_id && started.sim.patient_id != null) rememberOpenEncounter(started.sim.run_id, started.sim.patient_id, started.encounter_id);
        if (started.opening_line) setMessages([{ id: "open", who: "patient", text: started.opening_line }]);
        // the ledger's first event (what the chart opened with) comes from the session itself
        encApi
          .get(started.encounter_id)
          .then((s) => !dead && setLedger((prev) => mergeLedger(s.ledger, prev)))
          .catch(() => {});
        // a reload resumes this session instead of starting a second one
        selfStarted.id = started.encounter_id;
        router.replace(`/encounter?encounter_id=${encodeURIComponent(started.encounter_id)}`, { scroll: false });
      } catch (e) {
        if (dead) return;
        const a = e as ApiError;
        const sim = params.runId != null;
        setError({
          status: a.status,
          title: a.status === 404 ? (sim ? "That simulation run is no longer live" : "Not found") : a.status === 409 ? (sim ? "This patient cannot be played right now" : "This case cannot be started") : a.status === 0 ? "The server is not reachable" : "The encounter could not be started",
          message:
            a.message +
            (sim && a.status === 409 ? " A simulated patient can be played while they are waiting for or with a clinician, and only once." : "") +
            (sim && a.status === 404 ? " A run stays available for a few minutes after its hospital view closes. Go back to the hospital and pick a patient from the current run." : "") +
            (!sim && a.status === 409 ? " Only published cases can be started by learners. Faculty can preview a draft from the Patient Studio." : ""),
        });
      }
    })();
    return () => {
      dead = true;
      stopSpeaking();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // elapsed clock
  useEffect(() => {
    if (!session || done) return;
    const tick = () => setElapsed((Date.now() - session.startedAt) / 1000);
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [session, done]);

  // A queued result is applied once the run advances and the patient reaches the provider: keep asking until it lands.
  useEffect(() => {
    if (!session || done?.writeBack?.status !== "queued") return;
    const timer = setInterval(() => {
      encApi
        .get(session.id)
        .then((s) => {
          if (s.write_back && s.write_back.status !== "queued") setDone((d) => (d ? { ...d, writtenBack: !!s.written_back, writeBack: s.write_back } : d));
        })
        .catch(() => undefined);
    }, 4000);
    return () => clearInterval(timer);
  }, [session, done?.writeBack?.status]);

  // after a write-back, read the patient's record from the run to show that the simulation took the result
  useEffect(() => {
    if (!done || !session?.sim?.run_id) return;
    let dead = false;
    encApi
      .runPatient(session.sim.run_id, session.sim.patient_id)
      .then((p) => !dead && setAfter(p))
      .catch(() => {});
    return () => {
      dead = true;
    };
  }, [done, session?.sim?.run_id, session?.sim?.patient_id]);

  const setVoice = useCallback((on: boolean) => {
    setVoiceOn(on);
    try {
      window.localStorage.setItem(VOICE_KEY, on ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, []);

  const act = useCallback(
    async (kind: "turn" | "request", value: string) => {
      if (!session || busy) return;
      setBusy(true);
      setTurnError(null);
      const rid = newRequestId();
      const mid = `m-${rid}`;
      if (kind === "turn") setMessages((m) => [...m, { id: mid, who: "student", text: value }]);
      try {
        const r = kind === "turn" ? await encApi.turn(session.id, value, rid) : await encApi.request(session.id, value, rid);
        const n = r.disclosed.length + r.released_artifacts.length;
        setSession((s) => (s ? { ...s, chart: r.chart, llm: r.llm ?? s.llm } : s));
        setLedger((prev) => mergeLedger(prev, r.ledger_tail));
        if (typeof r.rapport === "number") setRapport(r.rapport);
        if (r.fallback) setFellBack(true);
        if (kind === "request") setRequested((s) => new Set(s).add(r.request ?? value));
        setMessages((m) => {
          const next = [...m];
          if (r.reply) next.push({ id: `${mid}-p`, who: "patient", text: r.reply, turn: r.turn, fallback: r.fallback, unlocked: n || undefined });
          if (kind === "request") next.push({ id: `${mid}-n`, who: "system", text: (r.notes ?? []).map(noteText).join(" ") || `Requested ${requestLabel(value)}`, turn: r.turn });
          else (r.notes ?? []).forEach((note, i) => next.push({ id: `${mid}-n${i}`, who: "system", text: note, turn: r.turn }));
          return next;
        });
        if (n > 0) setChartDot(true);
        if (r.reply && voiceRef.current) void speak(r.reply, { gender: session.patient.gender, voice: session.patient.voice });
      } catch (e) {
        const a = e as ApiError;
        if (kind === "turn") setMessages((m) => m.filter((x) => x.id !== mid));
        setTurnError(a.status === 409 ? "This encounter is already finished." : `${a.message} Your message was not sent; try again.`);
      } finally {
        setBusy(false);
      }
    },
    [session, busy],
  );

  const finish = useCallback(
    async (body: { disposition: string; orders: string[]; summary: string }) => {
      if (!session) return;
      setFinishing(true);
      setFinishError(null);
      stopSpeaking();
      try {
        const r = await encApi.finish(session.id, body);
        // pick up the complete ledger and chart as stored
        try {
          const s = await encApi.get(session.id);
          setLedger(s.ledger);
          setSession((x) => (x ? { ...x, chart: s.chart } : x));
        } catch {
          /* keep what we have */
        }
        setDone({ feedback: r.feedback, result: r.interaction_result, writtenBack: r.written_back, writeBack: r.write_back ?? null });
        if (session.sim?.run_id && session.sim.patient_id != null) forgetOpenEncounter(session.sim.run_id, session.sim.patient_id);
        setFinishOpen(false);
        window.scrollTo({ top: 0 });
      } catch (e) {
        setFinishError((e as ApiError).message);
      } finally {
        setFinishing(false);
      }
    },
    [session],
  );

  const simLine = useMemo(() => {
    if (!session?.sim) return null;
    return [bayLabel(baseline?.bay), shortHospital(baseline?.hospital_id, baseline?.hospital_name), simClock(session.sim.t_start)].filter(Boolean).join(" · ");
  }, [session?.sim, baseline]);

  if (error) {
    return (
      <ErrorCard title={error.title} message={error.message}>
        {params.runId != null ? (
          <Link href="/" className="btn-primary">
            Back to the hospital
          </Link>
        ) : (
          <Link href="/encounter" className="btn-primary">
            Choose a case
          </Link>
        )}
        <button className="btn-quiet" onClick={() => window.location.reload()}>
          Try again
        </button>
        <Link href="/studio" className="btn">
          Patient Studio
        </Link>
      </ErrorCard>
    );
  }
  if (!session) return <LoadingCard label={params.runId != null ? "Taking over this patient's encounter from the simulation…" : "Opening the encounter…"} />;

  const transcript = [...ledger]
    .sort((a, b) => a.seq - b.seq)
    .flatMap((e) => (e.kind === "turn" ? [{ turn: e.turn, speaker: "student", text: e.text ?? "" }, ...(e.reply ? [{ turn: e.turn, speaker: "patient", text: e.reply }] : [])] : e.kind === "request" ? [{ turn: e.turn, speaker: "student", text: e.request ?? "" }] : []));

  return (
    <div className={`flex flex-col ${done ? "min-h-screen" : "h-[100dvh]"}`} data-testid="encounter" data-encounter-id={session.id} data-phase={done ? "finished" : "active"}>
      {/* header */}
      <header className="z-20 shrink-0 px-3 pt-3 sm:px-4">
        <div className="glass flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2 sm:px-4">
          <Link
            href={session.sim ? hospitalHref(session.sim) : "/encounter"}
            onClick={(e) => {
              // leaving a simulated patient's encounter unfinished: ask whether to come back later or hand them back
              if (!done && session.sim?.run_id && session.sim.patient_id != null) {
                e.preventDefault();
                setLeaveOpen(true);
              }
            }}
            data-testid="encounter-back"
            className="btn-quiet !h-7 !px-2.5" title={session.sim ? "Back to the hospital" : "Back to the case list"}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M19 12H5M11 6l-6 6 6 6" />
            </svg>
            {session.sim ? "Hospital" : "Cases"}
          </Link>
          <div className="min-w-0 flex-1 basis-40">
            <div className="truncate text-[14px] font-semibold tracking-[-0.01em] text-ink" data-testid="encounter-title">
              {session.kase.title}
            </div>
            <div className="truncate text-[11px] text-ink-3">
              {session.sim ? (
                <span data-testid="sim-context">
                  <span className="font-semibold text-accent-dark">{simLine}</span> · {simWhere(baseline, !!done)}
                </span>
              ) : (
                <>
                  {session.kase.setting}
                  {session.preview ? " · faculty preview of an unpublished version" : ""}
                </>
              )}
            </div>
          </div>
          <span className="hidden md:inline-flex">
            <SyntheticLabel review={session.kase.needs_faculty_review !== false} />
          </span>
          <span className="inline-flex md:hidden">
            <SyntheticLabel compact />
          </span>
          {session.preview && (
            <span className="chip" style={{ background: "#F3E8FF", color: "#7A3FC4" }}>
              Preview
            </span>
          )}
          <ProviderChip llm={session.llm} fallback={fellBack} />
          <span className="tnum inline-flex h-7 items-center gap-1.5 rounded-full bg-[#141a33]/[0.05] px-2.5 text-[12px] font-semibold text-ink-2" title="Time since this encounter started" data-testid="elapsed">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
              <path d="M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z" />
            </svg>
            {mmss(elapsed)}
          </span>
          {!done ? (
            <button className="btn-primary" onClick={() => setFinishOpen(true)} disabled={busy} data-testid="finish-open">
              Finish encounter
            </button>
          ) : (
            <Link href={session.preview ? "/studio" : session.sim ? hospitalHref(session.sim) : `/encounter?case_id=${encodeURIComponent(session.kase.case_id)}`} className="btn-primary" data-testid="after-finish-link">
              {session.preview ? "Back to the Studio" : session.sim ? "Return to hospital" : "Try again"}
            </Link>
          )}
        </div>
      </header>

      {done ? (
        <FeedbackView kase={session.kase} patient={session.patient} feedback={done.feedback} result={done.result} writtenBack={done.writtenBack} writeBack={done.writeBack} sim={session.sim} baseline={baseline} after={after} chart={session.chart} transcript={transcript} preview={session.preview} />
      ) : (
        <>
          {/* narrow screens: one pane at a time */}
          <div className="shrink-0 px-3 pt-2 lg:hidden">
            <div className="seg w-full">
              <button className="flex-1" data-on={pane === "talk"} onClick={() => setPane("talk")} data-testid="pane-talk">
                Conversation
              </button>
              <button
                className="relative flex-1"
                data-on={pane === "chart"}
                onClick={() => {
                  setPane("chart");
                  setChartDot(false);
                }}
                data-testid="pane-chart"
              >
                Chart
                {chartDot && pane !== "chart" && <span className="absolute right-3 top-1.5 h-2 w-2 rounded-full bg-[#E0A100]" aria-label="New chart entries" />}
              </button>
            </div>
          </div>
          {turnError && (
            <div className="shrink-0 px-3 pt-2 sm:px-4">
              <InlineError>{turnError}</InlineError>
            </div>
          )}
          <main className="grid min-h-0 flex-1 grid-cols-1 gap-3 p-3 sm:px-4 lg:grid-cols-2">
            <div className={`min-h-0 ${pane === "talk" ? "" : "hidden lg:block"}`}>
              <ConversationPane kase={session.kase} patient={session.patient} messages={messages} requests={session.requests} requested={requested} rapport={rapport} busy={busy} finished={false} voiceOn={voiceOn} onVoice={setVoice} onSend={(t) => act("turn", t)} onRequest={(r) => act("request", r)} />
            </div>
            <div className={`min-h-0 ${pane === "chart" ? "" : "hidden lg:block"}`}>
              <ChartPane kase={session.kase} patient={session.patient} chart={session.chart} ledger={ledger} simLine={session.sim ? simLine : null} />
            </div>
          </main>
        </>
      )}

      {!done && <SiteDisclaimer className="shrink-0 pb-2 max-sm:line-clamp-2" />}
      {leaveOpen && !done && session.sim?.run_id && (
        <Modal title="Leave this encounter?" onClose={leaving ? () => {} : () => setLeaveOpen(false)}>
          <div className="space-y-3" data-testid="leave-dialog">
            <p className="text-[12.5px] leading-relaxed text-ink-2">
              This patient is held for you in the running hospital. <b className="font-semibold text-ink">Resume later</b> keeps them waiting where they are: select them in the hospital and choose “Resume encounter” (the hold lapses by itself after about thirty minutes). <b className="font-semibold text-ink">Give the patient back</b> lets the simulation decide this encounter itself; nothing you did here is written back.
            </p>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <button className="btn" onClick={() => setLeaveOpen(false)} disabled={leaving} data-testid="leave-stay">
                Stay
              </button>
              <button className="btn-quiet" disabled={leaving} onClick={() => router.push(hospitalHref(session.sim!))} data-testid="leave-resume-later">
                Resume later
              </button>
              <button
                className="btn-primary"
                disabled={leaving}
                data-testid="leave-give-back"
                onClick={async () => {
                  setLeaving(true);
                  await giveBack(session.sim!.run_id!, session.sim!.patient_id!).catch(() => undefined);
                  router.push(hospitalHref(session.sim!));
                }}
              >
                {leaving ? "Releasing…" : "Give the patient back"}
              </button>
            </div>
          </div>
        </Modal>
      )}
      {finishOpen && !done && <FinishDialog requests={session.requests} requested={requested} busy={finishing} error={finishError} onCancel={() => setFinishOpen(false)} onSubmit={finish} />}
    </div>
  );
}
