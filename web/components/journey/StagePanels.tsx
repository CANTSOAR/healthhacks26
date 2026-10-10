"use client";
// What the stage area shows when nobody is in the middle of playing it: the start card, and the summary of a finished stage.
import { OBJECTIVE_LABEL, OBJECTIVE_TONE } from "@/lib/encounter/labels";
import type { ObjectiveLabel } from "@/lib/encounter/types";
import { lc, roleTone, TYPE_LABEL } from "@/lib/journey/api";
import type { SbarGrading, Stage, StageObjective } from "@/lib/journey/types";
import { Spinner, Tone } from "@/components/encounter/ui";
import { ProvenanceChips } from "./RecordPanel";
import { RoleAvatar } from "./StageRail";

const WRITE_LABEL: Record<string, string> = { acuity: "an acuity (ESI)", note: "a note for the team", orders: "orders", disposition: "a disposition", med_list: "the reconciled medication list", plan: "plan items", open_questions: "open questions", sbar: "an SBAR handoff" };

export function ObjectiveChip({ result }: { result: ObjectiveLabel | null }) {
  if (!result) return <Tone bg="rgba(20,26,51,0.06)" fg="#4A5275">In the debrief</Tone>;
  const t = OBJECTIVE_TONE[result];
  return (
    <Tone bg={t.bg} fg={t.fg}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: t.dot }} />
      {OBJECTIVE_LABEL[result]}
    </Tone>
  );
}

export function ObjectiveList({ objectives }: { objectives: StageObjective[] }) {
  if (!objectives.length) return <p className="text-[12px] text-ink-3">No objectives are defined for this stage.</p>;
  return (
    <ul className="grid gap-2">
      {objectives.map((o) => (
        <li key={o.objective_id} className="rounded-xl border border-line bg-white/70 p-2.5" data-testid="stage-objective" data-result={o.result ?? "held"}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0 flex-1 basis-60 text-[12.5px] font-semibold leading-snug text-ink">{o.criterion}</div>
            <ObjectiveChip result={o.result} />
          </div>
          {o.evidence.slice(0, 2).map((ev, i) =>
            ev.quote ? (
              <blockquote key={i} className="mt-1.5 border-l-2 border-accent/30 pl-2 text-[11.5px] leading-snug text-ink-2">
                “{ev.quote}” <span className="text-ink-3">{ev.location}</span>
              </blockquote>
            ) : null,
          )}
          {o.feedback && <div className="mt-1 text-[11.5px] leading-snug text-ink-3">{o.feedback}</div>}
        </li>
      ))}
    </ul>
  );
}

export function StageStart({ stage, busy, onPlay, onAuto, onAutoBefore }: { stage: Stage; busy: boolean; onPlay: () => void; onAuto: () => void; onAutoBefore: () => void }) {
  const t = roleTone(stage.learner_role.staff_role);
  const blocked = stage.blocked_by.length > 0;
  const other = stage.counterparts.map((c) => (c.kind === "patient" ? `${c.name} (AI patient)` : `${c.name}, ${c.label} (AI colleague)`)).join(" and ");
  return (
    <div className="glass scroll-thin h-full overflow-y-auto p-5" data-testid="stage-start">
      <div className="flex items-start gap-3">
        <RoleAvatar staffRole={stage.learner_role.staff_role} name={stage.learner_role.label} size={48} />
        <div className="min-w-0 flex-1">
          <div className="eyebrow">
            Stage {stage.index + 1} · {TYPE_LABEL[stage.interaction_type] ?? stage.interaction_type}
          </div>
          <h2 className="text-[20px] font-semibold tracking-[-0.02em] text-ink">{stage.title}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Tone bg={t.bg} fg={t.fg}>Learner role: {stage.learner_role.label}</Tone>
            <span className="text-[11.5px] text-ink-3">with {other}</span>
          </div>
        </div>
      </div>
      <p className="mt-4 max-w-2xl text-[13.5px] leading-relaxed text-ink">{stage.brief}</p>
      <div className="mt-3 text-[12px] leading-relaxed text-ink-2">
        This stage must add to the shared record: <b>{stage.writes.required.map((k) => WRITE_LABEL[k] ?? k).join(", ")}</b>
        {stage.writes.optional?.length ? <> (optional: {stage.writes.optional.map((k) => WRITE_LABEL[k] ?? k).join(", ")})</> : null}.
      </div>
      {blocked ? (
        <div className="mt-5 rounded-xl border border-line bg-white/60 p-3 text-[12.5px] text-ink-2" data-testid="stage-blocked">
          Earlier stages come first, because this role starts from what they record.
          <div className="mt-2 flex flex-wrap gap-2">
            <button className="btn-primary" disabled={busy} onClick={onAutoBefore} data-testid="auto-before">
              {busy && <Spinner size={12} />} Let the sampler resolve the stages before this one
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <button className="btn-primary !h-9 !px-4 !text-[13px]" disabled={busy} onClick={onPlay} data-testid="stage-play">
            {busy && <Spinner size={12} />} Play as the {lc(stage.learner_role.label)}
          </button>
          <button className="btn-quiet !h-9" disabled={busy} onClick={onAuto} data-testid="stage-auto">
            Let the sampler resolve it
          </button>
        </div>
      )}
      <p className="mt-3 max-w-2xl text-[11.5px] leading-relaxed text-ink-3">
        A stage nobody plays is filled from the case by a named AI colleague with a sampled quality: a weaker draw finds less, and the next role inherits exactly that. Sampled quality is an assumed distribution, not a measured one.
      </p>
    </div>
  );
}

export function SbarReport({ grading }: { grading: SbarGrading }) {
  return (
    <div className="grid gap-2" data-testid="sbar-report">
      <div className="rounded-xl border border-line bg-white/70 p-2.5 text-[12px] leading-snug text-ink-2">
        <b className="text-ink">{grading.overall.feedback}</b> Graded against {grading.graded_against}.
      </div>
      {Object.values(grading.elements).map((el) => (
        <div key={el.element} className="rounded-xl border border-line bg-white/70 p-2.5" data-testid="sbar-element" data-element={el.element} data-result={el.result}>
          <div className="flex items-center justify-between gap-2">
            <div className="text-[13px] font-semibold text-ink">
              <span className="mr-1.5 inline-flex h-5 w-5 items-center justify-center rounded-md bg-accent text-[11px] text-white">{el.element}</span>
              {el.label}
            </div>
            <ObjectiveChip result={el.result} />
          </div>
          {el.text && <p className="mt-1.5 text-[12px] italic leading-snug text-ink-2">“{el.text}”</p>}
          <div className="mt-2 grid gap-1">
            {el.conveyed.map((c) => (
              <div key={c.item_id} className="flex items-start gap-1.5 text-[11.5px] leading-snug text-ink">
                <span className="chip shrink-0" style={{ background: "#E3F4EA", color: "#1F7A4D" }}>{c.prompted ? "after a question" : "conveyed"}</span>
                <span>{c.text}</span>
              </div>
            ))}
            {el.omitted.filter((o) => o.critical).map((o) => (
              <div key={o.item_id} className="text-[11.5px] leading-snug text-ink" data-testid="sbar-omitted">
                <div className="flex items-start gap-1.5">
                  <span className="chip shrink-0" style={{ background: "#FFF1D6", color: "#8A5200" }}>omitted</span>
                  <span>{o.text}</span>
                </div>
                <div className="ml-[62px] mt-1"><ProvenanceChips p={o.provenance} /></div>
              </div>
            ))}
            {el.unsupported.map((u, i) => (
              <div key={i} className="flex items-start gap-1.5 text-[11.5px] leading-snug" style={{ color: "#8E1B23" }} data-testid="sbar-unsupported">
                <span className="chip shrink-0" style={{ background: "#E5484D", color: "#fff" }}>no support</span>
                <span>“{u.quote}”: {u.reason}.</span>
              </div>
            ))}
            {el.interpretations.map((t, i) => (
              <div key={i} className="flex items-start gap-1.5 text-[11.5px] leading-snug text-ink-2">
                <span className="chip shrink-0" style={{ background: "rgba(20,26,51,0.06)", color: "#4A5275" }}>interpretation</span>
                <span>{t}</span>
              </div>
            ))}
            {el.omitted.filter((o) => !o.critical).length > 0 && <div className="text-[11px] text-ink-3">{el.omitted.filter((o) => !o.critical).length} less critical record item(s) were not mentioned.</div>}
          </div>
        </div>
      ))}
      <div className="rounded-xl border border-line bg-white/70 p-2.5">
        <div className="eyebrow mb-1.5">Communication behaviours</div>
        <ul className="grid gap-1.5">
          {grading.behaviors.map((b) => (
            <li key={b.behavior} className="text-[11.5px] leading-snug text-ink-2">
              <span className="chip mr-1.5" style={b.observed === "yes" ? { background: "#E3F4EA", color: "#1F7A4D" } : b.observed === "no" ? { background: "#FDE7E7", color: "#8E1B23" } : { background: "rgba(20,26,51,0.06)", color: "#4A5275" }}>
                {b.observed === "not_assessable" ? "not assessable" : b.observed}
              </span>
              <b className="text-ink">{b.behavior}.</b> {b.feedback} <span className="text-ink-3">({b.evidence_location})</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function StageSummary({ stage, grading, onNext, nextLabel }: { stage: Stage; grading?: SbarGrading | null; onNext?: () => void; nextLabel?: string }) {
  const r = stage.result;
  const who = stage.played_by === "human" ? "You played this stage" : stage.played_by === "sim" ? "Resolved by the running simulation" : `Sampled: ${stage.player} stood in as the ${lc(stage.learner_role.label)}`;
  const d = r?.decision as { kind?: string; acuity?: number; disposition?: string; orders?: string[]; detail?: string } | undefined;
  return (
    <div className="glass scroll-thin h-full overflow-y-auto p-5" data-testid="stage-summary" data-stage={stage.stage_id}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <RoleAvatar staffRole={stage.learner_role.staff_role} name={stage.played_by === "human" ? stage.learner_role.label : stage.player} size={44} />
          <div>
            <div className="eyebrow">Stage {stage.index + 1} complete</div>
            <h2 className="text-[19px] font-semibold tracking-[-0.02em] text-ink">{stage.title}</h2>
            <div className="text-[12px] text-ink-2" data-testid="stage-who">{who}</div>
          </div>
        </div>
        {onNext && (
          <button className="btn-primary !h-9 !px-4" onClick={onNext} data-testid="stage-next">
            {nextLabel}
          </button>
        )}
      </div>
      {r && (
        <div className="mt-4 rounded-xl border border-line bg-white/70 p-3" data-testid="stage-result">
          <div className="eyebrow mb-2">Interaction result · the same fields the simulator's sampler fills</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-[12px] sm:grid-cols-4">
            <div><div className="text-ink-3">Type</div><div className="font-semibold text-ink">{r.interaction_type}</div></div>
            <div><div className="text-ink-3">Resolver</div><div className="font-semibold text-ink">{r.resolver}</div></div>
            <div><div className="text-ink-3">Duration</div><div className="tnum font-semibold text-ink">{r.duration_min} min</div></div>
            <div><div className="text-ink-3">Quality</div><div className="tnum font-semibold text-ink">{stage.played_by === "sim" ? "kept in the simulation" : r.quality.toFixed(2)}</div></div>
            <div><div className="text-ink-3">Information gained</div><div className="tnum font-semibold text-ink">{r.information_gained.length} facts</div></div>
            <div className="col-span-2 sm:col-span-3"><div className="text-ink-3">Decision</div><div className="font-semibold text-ink">{[d?.kind?.replace(/_/g, " "), d?.acuity ? `ESI ${d.acuity}` : null, d?.disposition && d.disposition !== "undecided" ? d.disposition : null, d?.orders?.length ? d.orders.join(", ") : null].filter(Boolean).join(" · ")}</div></div>
          </div>
          {stage.result_note && <div className="mt-2 text-[11px] leading-snug text-ink-3">{stage.result_note}</div>}
          <div className="mt-2 text-[11px] leading-snug text-ink-3" data-testid="writeback-note">
            {stage.writeback.written_back ? "Written back to the running simulation." : stage.writeback.supported ? (stage.writeback.from_simulation ? (stage.writeback.note ?? "Not written back.") : "This journey was not opened from a simulated patient, so there is nothing to write back to.") : stage.writeback.note}
          </div>
        </div>
      )}
      <h3 className="mb-2 mt-4 text-[13px] font-semibold text-ink">Stage objectives</h3>
      <ObjectiveList objectives={stage.objectives} />
      {!!stage.n_case_objectives_held_back && <p className="mt-2 text-[11.5px] text-ink-3">{stage.n_case_objectives_held_back} of the case's own objectives are held back until the debrief, so later stages are not given the answers.</p>}
      {grading && (
        <>
          <h3 className="mb-2 mt-4 text-[13px] font-semibold text-ink">Handoff, element by element</h3>
          <SbarReport grading={grading} />
        </>
      )}
    </div>
  );
}
