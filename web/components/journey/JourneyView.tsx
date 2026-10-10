"use client";
// One journey: the stage rail, the stage being played or reviewed, and the shared record that every stage reads and writes.
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Avatar, ErrorCard, InlineError, LoadingCard, ProviderChip, SyntheticLabel } from "@/components/encounter/ui";
import type { ApiError } from "@/lib/encounter/api";
import { journeyApi } from "@/lib/journey/api";
import type { JourneyState, SharedRecord, StageView } from "@/lib/journey/types";
import { HandoffStage } from "./HandoffStage";
import { Outcome } from "./Outcome";
import { PatientStage } from "./PatientStage";
import { RecordPanel } from "./RecordPanel";
import { StageStart, StageSummary } from "./StagePanels";
import { StageRail } from "./StageRail";

const pick = (j: JourneyState) => j.stages.find((s) => s.status === "active")?.stage_id ?? j.next_stage ?? "outcome";

export function JourneyView({ journeyId }: { journeyId: string }) {
  const [journey, setJourney] = useState<JourneyState | null>(null);
  const [record, setRecord] = useState<SharedRecord | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<StageView | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [pane, setPane] = useState<"stage" | "chart" | "record">("stage");
  const [dot, setDot] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ title: string; message: string } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const paneRef = useRef(pane);
  paneRef.current = pane;

  const applyRecord = useCallback((r: SharedRecord, added?: string[]) => {
    setRecord((prev) => {
      const had = new Set((prev?.entries ?? []).map((e) => e.entry_id));
      const ids = added ?? r.entries.filter((e) => !had.has(e.entry_id)).map((e) => e.entry_id);
      if (prev && ids.length) {
        setFresh(new Set(ids));
        if (paneRef.current !== "record") setDot(true);
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => setFresh(new Set()), 2600);
      }
      return r;
    });
    setVersion((v) => v + 1);
  }, []);

  const refresh = useCallback(async () => {
    const j = await journeyApi.get(journeyId);
    setJourney(j);
    applyRecord(j.record);
    return j;
  }, [journeyId, applyRecord]);

  useEffect(() => {
    let dead = false;
    refresh()
      .then((j) => !dead && setSelected(pick(j)))
      .catch((e: ApiError) => !dead && setError({ title: e.status === 404 ? "This journey was not found" : e.status === 0 ? "The server is not reachable" : "The journey could not be loaded", message: e.message }));
    return () => {
      dead = true;
    };
  }, [refresh]);

  const stage = journey?.stages.find((s) => s.stage_id === selected) ?? null;
  const stageStatus = stage?.status;
  const viewRef = useRef<StageView | null>(null);
  viewRef.current = view;
  useEffect(() => {
    let dead = false;
    // an action that just returned this stage's view (start, finish) already has the current state: keep it on screen
    const cur = viewRef.current;
    if (cur && cur.stage.stage_id === selected && cur.stage.status === stageStatus) return;
    setView(null);
    setActionError(null);
    if (!selected || selected === "outcome" || !stageStatus || stageStatus === "pending") return;
    journeyApi
      .stage(journeyId, selected)
      .then((v) => !dead && setView(v))
      .catch((e: ApiError) => !dead && setActionError(e.message));
    return () => {
      dead = true;
    };
  }, [journeyId, selected, stageStatus]);

  async function run(fn: () => Promise<StageView | JourneyState | void>, keepView = false) {
    setBusy(true);
    setActionError(null);
    try {
      const out = await fn();
      if (out && "stage" in out && keepView) setView(out);
      await refresh();
    } catch (e) {
      setActionError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  if (error)
    return (
      <ErrorCard title={error.title} message={error.message}>
        <Link href="/journey" className="btn-primary">
          Choose a patient
        </Link>
      </ErrorCard>
    );
  if (!journey || !record || !selected) return <LoadingCard label="Opening the journey…" />;
  const complete = journey.status === "complete";
  const active = stage?.status === "active" && view?.stage.stage_id === stage.stage_id && view.stage.status === "active";
  const playingPatient = active && stage?.kind === "patient" && !!view?.encounter;
  const next = () => setSelected(journey.next_stage ?? "outcome");

  return (
    <div className="flex h-[100dvh] flex-col" data-testid="journey-view" data-status={journey.status}>
      <header className="shrink-0 px-3 pt-3 sm:px-4">
        <div className="glass flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
          <Link href={journey.sim ? "/" : "/journey"} className="btn !h-7 !px-2" title="Back">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M15 18l-6-6 6-6" />
            </svg>
            {journey.sim ? "Hospital" : "Journeys"}
          </Link>
          <Avatar name={journey.patient.name} image={journey.patient.image} size={32} />
          <div className="min-w-0 flex-1 basis-48">
            <div className="truncate text-[14px] font-semibold tracking-[-0.01em] text-ink" data-testid="journey-title">
              {journey.patient.name} · {journey.template.title}
            </div>
            <div className="truncate text-[11px] text-ink-3">
              Care journey · one patient, {journey.stages.length} connected interactions, one shared record
              {journey.sim ? ` · patient ${journey.sim.patient_id} in the running simulation` : ""}
            </div>
          </div>
          <span className="hidden md:inline-flex">
            <SyntheticLabel review={journey.case.needs_faculty_review !== false} />
          </span>
          <span className="inline-flex md:hidden">
            <SyntheticLabel compact />
          </span>
          <ProviderChip llm={journey.llm} />
        </div>
      </header>
      <div className="shrink-0 px-3 pt-2 sm:px-4">
        <StageRail stages={journey.stages} selected={selected} onSelect={setSelected} complete={complete} />
      </div>
      <div className="shrink-0 px-3 pt-2 sm:px-4 min-[1400px]:hidden">
        <div className={`seg w-full ${playingPatient ? "" : "xl:hidden"}`}>
          <button className="flex-1" data-on={pane === "stage"} onClick={() => setPane("stage")} data-testid="pane-stage">
            {playingPatient ? "Conversation" : "Stage"}
          </button>
          {playingPatient && (
            <button className="flex-1" data-on={pane === "chart"} onClick={() => setPane("chart")} data-testid="pane-chart">
              Chart
            </button>
          )}
          <button
            className="relative flex-1 xl:hidden"
            data-on={pane === "record"}
            onClick={() => {
              setPane("record");
              setDot(false);
            }}
            data-testid="pane-record"
          >
            Shared record ({record.entries.length})
            {dot && pane !== "record" && <span className="absolute right-3 top-1.5 h-2 w-2 rounded-full bg-[#E0A100]" aria-label="New entries" />}
          </button>
        </div>
      </div>
      {actionError && (
        <div className="shrink-0 px-3 pt-2 sm:px-4">
          <InlineError>{actionError}</InlineError>
        </div>
      )}
      <main className="grid min-h-0 flex-1 grid-cols-1 gap-3 p-3 sm:px-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className={`min-h-0 ${pane === "record" ? "hidden xl:block" : ""}`}>
          {selected === "outcome" ? (
            <Outcome journeyId={journeyId} complete={complete} stages={journey.stages} version={version} />
          ) : !stage ? null : stage.status === "pending" ? (
            <StageStart
              stage={stage}
              busy={busy}
              onPlay={() => run(() => journeyApi.startStage(journeyId, stage.stage_id, "human"), true)}
              onAuto={() => run(() => journeyApi.startStage(journeyId, stage.stage_id, "auto"))}
              onAutoBefore={() => run(() => journeyApi.auto(journeyId, stage.stage_id))}
            />
          ) : !view || view.stage.stage_id !== stage.stage_id ? (
            <LoadingCard label="Opening the stage…" />
          ) : active && stage.kind === "patient" && view.encounter ? (
            <PatientStage
              key={stage.stage_id}
              journeyId={journeyId}
              stage={stage}
              view={view}
              pane={pane === "chart" ? "chart" : "stage"}
              onRecord={applyRecord}
              onFinished={(v) => {
                setView(v);
                setPane("stage");
                refresh().catch(() => {});
              }}
            />
          ) : active && stage.kind === "handoff" && view.handoff ? (
            <HandoffStage
              stage={stage}
              handoff={view.handoff}
              busy={busy}
              onSbar={(b) => run(() => journeyApi.sbar(journeyId, stage.stage_id, b), true)}
              onAnswer={(t) => run(() => journeyApi.answer(journeyId, stage.stage_id, t), true)}
              onFinish={() => run(() => journeyApi.finish(journeyId, stage.stage_id, {}), true)}
            />
          ) : (
            <StageSummary stage={stage} grading={view.handoff?.grading} onNext={next} nextLabel={journey.next_stage ? `Next: ${journey.stages.find((s) => s.stage_id === journey.next_stage)?.title}` : "Care plan and debrief"} />
          )}
        </div>
        <div className={`min-h-0 ${pane === "record" ? "" : "hidden xl:block"}`}>
          <RecordPanel record={record} stages={journey.stages} fresh={fresh} />
        </div>
      </main>
    </div>
  );
}
