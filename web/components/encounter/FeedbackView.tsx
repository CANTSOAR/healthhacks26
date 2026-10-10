"use client";
// Shown after "Finish encounter": the grader's output and, for a simulated patient, what went back to the simulation.
// The grader is separate from the patient role-play; which grader ran (offline heuristics or a model) is stated.
import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import { bayLabel, OBJECTIVE_LABEL, OBJECTIVE_TONE, requestLabel, RULE_LABEL, shortHospital, simClock, titleCase } from "@/lib/encounter/labels";
import type { Chart, Evidence, Feedback, InteractionResult, LearnerCase, ObjectiveLabel, PatientView, RunPatient, SampledBaseline, SimBinding } from "@/lib/encounter/types";
import { Avatar, SyntheticLabel, Tone } from "./ui";

function Quote({ e }: { e: Evidence }) {
  const bracket = /^\[(.+?)\]\s*(.*)$/.exec(e.quote);
  const isReq = /^(order|exam|artifact):/.test(e.quote);
  return (
    <li className="flex items-start gap-2 text-[12.5px] leading-snug" data-testid="evidence">
      <span className="tnum mt-px inline-flex h-[18px] shrink-0 items-center rounded bg-[#141a33]/[0.06] px-1.5 text-[10px] font-semibold text-ink-2">{e.turn != null ? `turn ${e.turn}` : "–"}</span>
      {bracket ? (
        <span className="text-ink-2">
          <span className="font-semibold">{bracket[1].charAt(0).toUpperCase() + bracket[1].slice(1)}:</span> {/^(order|exam|artifact):/.test(bracket[2]) ? requestLabel(bracket[2]) : bracket[2]}
        </span>
      ) : isReq ? (
        <span className="text-ink-2">
          <span className="font-semibold">Requested:</span> {requestLabel(e.quote)}
        </span>
      ) : (
        <q className="italic text-ink">{e.quote}</q>
      )}
    </li>
  );
}

function dedupe(ev?: Evidence[]): Evidence[] {
  const seen = new Set<string>();
  return (ev ?? []).filter((e) => {
    const k = `${e.turn}|${e.quote}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

function Uncertain() {
  return (
    <Tone bg="#FFF1D6" fg="#9A5B00" title="The evidence for this judgement is thin or indirect. Treat it as a prompt for discussion with a teacher, not as a score.">
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" aria-hidden>
        <path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 1-1 1.7M12 17h.01" />
      </svg>
      Uncertain
    </Tone>
  );
}

function Card({ title, eyebrow, right, children, testid }: { title: string; eyebrow?: string; right?: ReactNode; children: ReactNode; testid?: string }) {
  return (
    <section className="glass p-4 sm:p-5" data-testid={testid}>
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <div className="min-w-0 flex-1">
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <h2 className="text-[16px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div className="rounded-xl border border-line bg-white/65 px-3 py-2.5">
      <div className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-3">{label}</div>
      <div className="tnum mt-0.5 text-[20px] font-semibold leading-tight tracking-[-0.015em] text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-[11px] leading-snug text-ink-3">{sub}</div>}
    </div>
  );
}

const pct = (q?: number | null) => (typeof q === "number" ? `${Math.round(q * 100)}` : "–");
const dispWord = (d?: string | null) => (d && d !== "undecided" ? titleCase(d) : "Undecided");

// ---------------------------------------------------------------- write-back
function ContractRow({ label, hint, sampled, played }: { label: string; hint: string; sampled: ReactNode; played: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-x-3 gap-y-1.5 border-t border-line py-3 first:border-t-0 sm:grid-cols-[150px_1fr_22px_1fr] sm:items-start" data-testid="contract-row">
      <div>
        <div className="text-[12.5px] font-semibold text-ink">{label}</div>
        <div className="text-[11px] leading-snug text-ink-3">{hint}</div>
      </div>
      <div className="rounded-lg bg-[#141a33]/[0.04] px-3 py-2 text-[12.5px] leading-snug text-ink-2">
        <span className="mb-0.5 block text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-3 sm:hidden">Sampled</span>
        {sampled}
      </div>
      <div className="hidden items-center justify-center pt-2 text-ink-4 sm:flex" aria-hidden>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      </div>
      <div className="rounded-lg border border-accent/20 bg-accent-soft/70 px-3 py-2 text-[12.5px] font-medium leading-snug text-ink">
        <span className="mb-0.5 block text-[10px] font-semibold uppercase tracking-[0.06em] text-accent-dark sm:hidden">Played by you</span>
        {played}
      </div>
    </div>
  );
}

function OrdersList({ orders }: { orders?: string[] }) {
  if (!orders?.length) return <span className="text-ink-3">No orders</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {orders.map((o) => (
        <span key={o} className="rounded bg-white/80 px-1.5 py-px text-[11.5px] font-medium text-ink-2 ring-1 ring-line">
          {/^(order|exam):/.test(o) ? requestLabel(o) : titleCase(o)}
        </span>
      ))}
    </span>
  );
}

type WriteBack = { status: "applied" | "queued" | "rejected" | "not_applicable"; detail?: string } | null | undefined;

export function WriteBackCard({
  result,
  writtenBack,
  writeBack,
  error,
  sim,
  baseline,
  after,
  chart,
}: {
  result: InteractionResult;
  writtenBack: boolean;
  /** newer servers say how the result landed; "queued" is a success: it is applied when the patient reaches the provider */
  writeBack?: WriteBack;
  error?: string;
  sim: SimBinding;
  baseline: SampledBaseline | null;
  after: RunPatient | null;
  chart: Chart;
}) {
  const [open, setOpen] = useState(false);
  const factText = useMemo(() => {
    const m = new Map<string, string>();
    chart.sections.forEach((s) => s.facts.forEach((f) => m.set(f.fact_id, f.text)));
    return m;
  }, [chart]);
  const recorded = after?.interactions?.find((i) => i.interaction_id === result.interaction_id) ?? null;
  const where = [bayLabel(baseline?.bay), shortHospital(baseline?.hospital_id, baseline?.hospital_name), simClock(sim.t_start)].filter(Boolean).join(" · ");
  const none = <span className="text-ink-3">Not captured before the encounter started</span>;
  const status: "applied" | "queued" | "rejected" = writeBack?.status === "applied" || writeBack?.status === "queued" ? writeBack.status : writtenBack ? "applied" : "rejected";
  void error; // the raw server error is not shown to the learner
  const good = status !== "rejected";
  const heading = status === "applied" ? "Written back to the simulation" : status === "queued" ? "Queued for the simulation" : "Not written back to the simulation";
  const flag = status === "applied" ? "Applied" : status === "queued" ? "Queued" : "Not applied";
  const outcome =
    status === "applied"
      ? "The simulation carries on from your decision."
      : status === "queued"
        ? "This patient has not reached the provider yet, so your result is queued: it will be applied when they do, in place of the sampled one. This card updates when that happens; return to the hospital and let the clock run."
        : writeBack?.detail
          ? `The simulation did not take the result: ${writeBack.detail.replace(/\.$/, "")}.`
          : "The simulation did not take the result (the run may have ended), so it was stored with this session only.";
  return (
    <section className="glass overflow-hidden" data-testid="writeback-card" data-written-back={String(writtenBack)} data-write-back={status}>
      <div className="flex flex-wrap items-center gap-3 border-b border-line bg-gradient-to-r from-accent-soft/80 to-white/40 px-4 py-3.5 sm:px-5">
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white ${status === "applied" ? "bg-[#2FA36B]" : status === "queued" ? "bg-[#2F55F5]" : "bg-[#D8434C]"}`}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            {good ? <path d="M5 12.5l4.5 4.5L19 7.5" /> : <path d="M6 6l12 12M18 6L6 18" />}
          </svg>
        </span>
        <div className="min-w-0 flex-1">
          <div className="eyebrow">One hospital, two fidelities</div>
          <h2 className="text-[17px] font-semibold tracking-[-0.01em] text-ink">{heading}</h2>
          <p className="mt-0.5 text-[12px] leading-snug text-ink-2">
            Patient {String(result.patient_id).padStart(6, "0")} in run <span className="tnum">{sim.run_id}</span>
            {where ? ` · ${where}` : ""}
          </p>
        </div>
        <Tone bg={status === "applied" ? "#E3F4EA" : status === "queued" ? "#E3E9FF" : "#FDE7E7"} fg={status === "applied" ? "#1F7A4D" : status === "queued" ? "#1F3FD1" : "#B4232C"}>
          <span data-testid="written-back-flag">{flag}</span>
        </Tone>
      </div>
      <div className="px-4 py-3 sm:px-5">
        <p className="text-[12.5px] leading-relaxed text-ink-2">
          Every clinician–patient encounter in the hospital fills the same four outputs. The simulation normally <b className="font-semibold text-ink">samples</b> them from its catalog; for this patient you <b className="font-semibold text-ink">played</b> the encounter{good ? ", and your result takes the place of the sampled one." : "."} {outcome}
        </p>
        <div className="mt-3 hidden grid-cols-[150px_1fr_22px_1fr] gap-x-3 pb-1 sm:grid">
          <span />
          <span className="eyebrow">Sampled (what the simulation had drawn)</span>
          <span />
          <span className="eyebrow" style={{ color: "#1F3FD1" }}>
            Played by you (written back)
          </span>
        </div>
        <ContractRow
          label="Duration"
          hint="duration_min"
          sampled={baseline?.duration_min != null ? <span className="tnum">{baseline.duration_min} min</span> : none}
          played={<span className="tnum" data-testid="wb-duration">{result.duration_min} min</span>}
        />
        <ContractRow
          label="Information gained"
          hint="information_gained"
          sampled={<span>Not itemised: the sampler draws a quality score instead of individual findings.</span>}
          played={
            <span>
              <span className="tnum" data-testid="wb-info">{result.information_gained.length}</span> findings now known to the care team{" "}
              <button className="font-semibold text-accent-dark underline-offset-2 hover:underline" onClick={() => setOpen((v) => !v)}>
                {open ? "hide" : "show"}
              </button>
              {open && (
                <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-[12px] font-normal text-ink-2">
                  {result.information_gained.map((id) => (
                    <li key={id}>{factText.get(id) ?? id}</li>
                  ))}
                </ul>
              )}
            </span>
          }
        />
        <ContractRow
          label="Decision"
          hint="decision"
          sampled={
            baseline ? (
              <span className="space-y-1">
                <span className="block">{baseline.disposition && baseline.disposition !== "undecided" ? `Disposition: ${dispWord(baseline.disposition)}` : "Disposition: not drawn yet (sampled when the encounter ends)"}</span>
                <OrdersList orders={baseline.orders} />
              </span>
            ) : (
              none
            )
          }
          played={
            <span className="space-y-1">
              <span className="block" data-testid="wb-disposition">Disposition: {dispWord(result.decision.disposition)}</span>
              <OrdersList orders={result.decision.orders} />
            </span>
          }
        />
        <ContractRow
          label="Quality"
          hint="quality (0 to 1)"
          sampled={baseline?.quality != null ? <span className="tnum">{baseline.quality.toFixed(2)}</span> : none}
          played={
            <span>
              <span className="tnum" data-testid="wb-quality">{result.quality.toFixed(2)}</span> <span className="text-[11.5px] font-normal text-ink-2">computed from critical findings reached, objectives and the decision</span>
            </span>
          }
        />
        {recorded && (
          <div className="mt-1 flex flex-wrap items-center gap-2 rounded-lg border border-[#BFE5CF] bg-[#F1FAF5] px-3 py-2 text-[12px] text-[#1F7A4D]" data-testid="wb-confirmed">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M5 12.5l4.5 4.5L19 7.5" />
            </svg>
            <span>
              Read back from the run: the simulation&apos;s record for this patient lists interaction <span className="tnum font-semibold">{recorded.interaction_id}</span> with resolver <b className="font-semibold">{recorded.resolver}</b>
              {after?.live?.disposition ? `, disposition ${after.live.disposition}` : ""}
              {after?.live?.flag_names?.includes("played") ? ", flag “played”" : ""}.
            </span>
          </div>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Link href={sim.run_id ? `/?run_id=${encodeURIComponent(sim.run_id)}&patient_id=${encodeURIComponent(String(result.patient_id ?? sim.patient_id ?? ""))}` : "/?mode=play"} className="btn-primary" data-testid="return-hospital">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M19 12H5M11 6l-6 6 6 6" />
            </svg>
            Return to hospital
          </Link>
          <span className="text-[11.5px] text-ink-3">All values are simulated. No language model produced or changed any of these numbers.</span>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- feedback
export function FeedbackView({
  kase,
  patient,
  feedback,
  result,
  writtenBack,
  writeBack,
  sim,
  baseline,
  after,
  chart,
  transcript,
  preview,
}: {
  kase: LearnerCase;
  patient: PatientView;
  feedback: Feedback;
  result: InteractionResult | null;
  writtenBack: boolean;
  writeBack?: WriteBack;
  sim: SimBinding | null;
  baseline: SampledBaseline | null;
  after: RunPatient | null;
  chart: Chart;
  transcript: { turn: number; speaker: string; text: string }[];
  preview?: boolean;
}) {
  const offline = feedback.grader !== "llm";
  const counts = useMemo(() => {
    const c: Record<ObjectiveLabel, number> = { met: 0, partly_demonstrated: 0, not_observed: 0, not_assessable: 0 };
    feedback.objectives.forEach((o) => (c[o.result] = (c[o.result] ?? 0) + 1));
    return c;
  }, [feedback]);
  const rub = feedback.rubric;
  const scale = new Map((rub?.rating_scale ?? []).map((s) => [s.score, s.label]));
  const missedCritical = (feedback.missed ?? []).filter((m) => m.critical);
  const missedOther = (feedback.missed ?? []).filter((m) => !m.critical);

  return (
    <div className="mx-auto w-full max-w-[1080px] space-y-4 px-3 pb-10 pt-4 sm:px-5" data-testid="feedback">
      {/* summary */}
      <section className="glass p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-3">
          <Avatar name={patient.name} image={patient.image} size={48} />
          <div className="min-w-0 flex-1">
            <div className="eyebrow">Feedback{preview ? " · faculty preview of a draft" : ""}</div>
            <h1 className="text-[20px] font-semibold tracking-[-0.015em] text-ink">{kase.title}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <Tone bg={offline ? "rgba(20,26,51,0.06)" : "#E3F4EA"} fg={offline ? "#4A5275" : "#1F7A4D"} title={offline ? "No language model graded this. Rules read the ledger and the transcript: which findings were reached, which requests were made, and wording patterns." : "A language model graded the transcript against the objectives; scores that feed the simulation are still computed by fixed rules."}>
                <span data-testid="grader-kind">{offline ? "Grader: offline heuristics" : "Grader: language model"}</span>
              </Tone>
              {feedback.fallback && (
                <Tone bg="#FFF1D6" fg="#9A5B00" title="The model grader did not answer, so the heuristic grader produced this feedback.">
                  fallback
                </Tone>
              )}
              <SyntheticLabel />
            </div>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2.5 md:grid-cols-4">
          <Stat label="Objectives met" value={`${counts.met} / ${feedback.objectives.length}`} sub={`${counts.partly_demonstrated} partly · ${counts.not_observed} not observed${counts.not_assessable ? ` · ${counts.not_assessable} not assessable` : ""}`} />
          <Stat label="Rubric" value={rub?.total != null ? `${rub.total} / ${rub.max_total}` : "–"} sub={rub?.n_scored != null ? `${rub.n_scored} of ${rub.domains.length} domains scored` : undefined} />
          <Stat label="Findings elicited" value={`${feedback.elicited?.length ?? 0}`} sub={`${feedback.missed?.length ?? 0} not reached${missedCritical.length ? `, ${missedCritical.length} of them key` : ""}`} />
          <Stat label="Encounter time" value={result ? `${result.duration_min} min` : "–"} sub="Simulated clinical time, from turns and requests" />
        </div>
        {feedback.formative_note && <p className="mt-3 text-[12px] leading-relaxed text-ink-3">{feedback.formative_note}</p>}
      </section>

      {sim && result && <WriteBackCard result={result} writtenBack={writtenBack} writeBack={writeBack} error={feedback.writeback_error} sim={sim} baseline={baseline} after={after} chart={chart} />}

      {/* objectives */}
      <Card title="Learning objectives" eyebrow="Objective by objective" testid="objectives" right={<span className="text-[11.5px] text-ink-3">Met · Partly demonstrated · Not observed · Not assessable</span>}>
        <ul className="space-y-2.5">
          {feedback.objectives.map((o) => {
            const t = OBJECTIVE_TONE[o.result] ?? OBJECTIVE_TONE.not_assessable;
            const ev = dedupe(o.evidence);
            return (
              <li key={o.objective_id} className="rounded-xl border border-line bg-white/65 p-3" data-testid="objective" data-result={o.result}>
                <div className="flex flex-wrap items-start gap-2">
                  <span className="mt-[5px] h-2 w-2 shrink-0 rounded-full" style={{ background: t.dot }} />
                  <span className="min-w-0 flex-1 basis-64 text-[13.5px] font-semibold leading-snug text-ink">{o.criterion}</span>
                  {o.critical && (
                    <Tone bg="rgba(20,26,51,0.06)" fg="#4A5275" title="The case author marked this objective as key.">
                      Key
                    </Tone>
                  )}
                  {o.uncertain && <Uncertain />}
                  <Tone bg={t.bg} fg={t.fg}>
                    <span data-testid="objective-label">{OBJECTIVE_LABEL[o.result] ?? o.result}</span>
                  </Tone>
                </div>
                <div className="mt-2 pl-4">
                  {ev.length > 0 ? (
                    <ul className="space-y-1">
                      {ev.map((e, i) => (
                        <Quote key={i} e={e} />
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[12px] text-ink-3">No evidence in the transcript.</p>
                  )}
                  {o.basis && o.basis !== "ledger" && <p className="mt-1.5 text-[11.5px] text-ink-3">Basis: {o.basis}</p>}
                  {o.suggestion && o.result !== "met" && (
                    <p className="mt-1.5 text-[12.5px] leading-snug text-ink-2">
                      <span className="font-semibold text-ink">Next time: </span>
                      {o.suggestion.replace(/^next time:\s*/i, "").replace(/^./, (c) => c.toUpperCase())}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
          {feedback.objectives.length === 0 && <li className="text-[12.5px] text-ink-3">This case has no learning objectives; feedback covers the rubric domains only.</li>}
        </ul>
      </Card>

      {/* rubric */}
      {rub && (
        <Card
          title={rub.title ?? "Rubric"}
          eyebrow="Rubric domains"
          testid="rubric"
          right={
            rub.rating_scale?.length ? (
              <span className="text-[11.5px] text-ink-3">
                {rub.rating_scale
                  .slice()
                  .sort((a, b) => b.score - a.score)
                  .map((s) => `${s.score} ${s.label}`)
                  .join(" · ")}
              </span>
            ) : undefined
          }
        >
          <ul className="grid gap-2.5 md:grid-cols-2">
            {rub.domains.map((d) => {
              const n = typeof d.score === "number" ? d.score : null;
              const color = n == null ? "#8089A8" : n >= 4 ? "#2FA36B" : n === 3 ? "#2F55F5" : n === 2 ? "#E0A100" : "#D8434C";
              const ev = dedupe(d.evidence).slice(0, 3);
              return (
                <li key={d.key} className="rounded-xl border border-line bg-white/65 p-3" data-testid="rubric-domain">
                  <div className="flex items-start gap-3">
                    <span className="tnum flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-[16px] font-semibold text-white" style={{ background: color }} title={n != null ? scale.get(n) : "Not assessable in this encounter"}>
                      {n ?? "N/A"}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[13px] font-semibold leading-snug text-ink">{d.name}</span>
                        {n != null && scale.get(n) && <span className="text-[11px] font-medium text-ink-3">{scale.get(n)}</span>}
                        {d.uncertain && <Uncertain />}
                        {d.triggers_review && (
                          <Tone bg="#FDE7E7" fg="#B4232C" title="The rubric asks for a teacher to review this domain.">
                            Review with faculty
                          </Tone>
                        )}
                      </div>
                      {d.rationale && <p className="mt-1 text-[12.5px] leading-snug text-ink-2">{d.rationale.charAt(0).toUpperCase() + d.rationale.slice(1)}</p>}
                    </div>
                  </div>
                  {ev.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {ev.map((e, i) => (
                        <Quote key={i} e={e} />
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
          {rub.note && <p className="mt-3 text-[11.5px] leading-relaxed text-ink-3">{rub.note}</p>}
        </Card>
      )}

      {/* findings */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card title={`Elicited (${feedback.elicited?.length ?? 0})`} eyebrow="Findings you reached" testid="elicited">
          <ul className="space-y-1.5">
            {(feedback.elicited ?? []).map((f) => (
              <li key={f.fact_id} className="rounded-lg border border-line bg-white/60 px-2.5 py-2 text-[12.5px] leading-snug" data-testid="elicited-item">
                <div className="flex items-start gap-2">
                  <span className="min-w-0 flex-1 text-ink">{f.text}</span>
                  {f.critical && (
                    <Tone bg="#E3F4EA" fg="#1F7A4D">
                      Key
                    </Tone>
                  )}
                </div>
                <div className="mt-1 text-[11.5px] text-ink-3">
                  {f.rule ? `${RULE_LABEL[f.rule] ?? f.rule}` : ""}
                  {f.turn != null ? ` · turn ${f.turn}` : ""}
                  {f.by ? (
                    <>
                      {" · "}
                      {/^(order|exam|artifact):/.test(f.by) ? `requested ${requestLabel(f.by)}` : <q className="italic">{f.by}</q>}
                    </>
                  ) : null}
                </div>
              </li>
            ))}
            {!feedback.elicited?.length && <li className="text-[12.5px] text-ink-3">Nothing was elicited.</li>}
          </ul>
        </Card>
        <Card title={`Missed (${feedback.missed?.length ?? 0})`} eyebrow="Findings you did not reach" testid="missed">
          <ul className="space-y-1.5">
            {[...missedCritical, ...missedOther].map((f) => (
              <li key={f.fact_id} className="rounded-lg border border-line bg-white/60 px-2.5 py-2 text-[12.5px] leading-snug" data-testid="missed-item">
                <div className="flex items-start gap-2">
                  <span className="min-w-0 flex-1 text-ink">{f.text}</span>
                  {f.critical && (
                    <Tone bg="#FDE7E7" fg="#B4232C">
                      Key
                    </Tone>
                  )}
                </div>
                <div className="mt-1 text-[11.5px] text-ink-3">
                  {f.asked ? "You asked, but it was not released" : "Not asked"}
                  {f.how_to_reach ? ` · To reach it: ${f.how_to_reach}` : ""}
                </div>
              </li>
            ))}
            {!feedback.missed?.length && <li className="text-[12.5px] text-ink-3">Nothing was missed.</li>}
          </ul>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Strengths" eyebrow="Keep doing" testid="strengths">
          <ul className="space-y-1.5">
            {(feedback.strengths ?? []).map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-[12.5px] leading-snug text-ink">
                <span className="mt-[3px] text-[#2FA36B]">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M5 12.5l4.5 4.5L19 7.5" />
                  </svg>
                </span>
                <span>{s}</span>
              </li>
            ))}
            {!feedback.strengths?.length && <li className="text-[12.5px] text-ink-3">No strengths were detected in this short encounter.</li>}
          </ul>
        </Card>
        <Card title="For your next attempt" eyebrow="Try this" testid="next-time">
          <ol className="space-y-1.5">
            {(feedback.next_time ?? []).map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-[12.5px] leading-snug text-ink">
                <span className="tnum mt-px inline-flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full bg-accent-soft text-[10.5px] font-semibold text-accent-dark">{i + 1}</span>
                <span>{s}</span>
              </li>
            ))}
            {!feedback.next_time?.length && <li className="text-[12.5px] text-ink-3">No suggestions.</li>}
          </ol>
        </Card>
      </div>

      {/* debrief: released by the API only after the encounter is finished */}
      {(feedback.debrief?.diagnosis || feedback.debrief?.teaching_points?.length || feedback.artifact_interpretations?.length) && (
        <Card title="Debrief" eyebrow="Released after you finish" testid="debrief">
          {feedback.debrief?.diagnosis && (
            <p className="text-[13px] leading-snug text-ink">
              <span className="font-semibold">Working diagnosis in this case: </span>
              {feedback.debrief.diagnosis}
              {feedback.debrief.expected_disposition ? ` (expected disposition: ${feedback.debrief.expected_disposition})` : ""}
            </p>
          )}
          {!!feedback.debrief?.teaching_points?.length && (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-[12.5px] leading-snug text-ink-2">
              {feedback.debrief.teaching_points.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          )}
          {!!feedback.artifact_interpretations?.length && (
            <div className="mt-3">
              <div className="eyebrow mb-1">How the author reads the results you requested</div>
              <ul className="space-y-1 text-[12.5px] leading-snug text-ink-2">
                {feedback.artifact_interpretations.map((a) => (
                  <li key={a.artifact_id}>
                    <span className="font-semibold text-ink">{a.title}: </span>
                    {a.interpretation}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="mt-3 text-[11.5px] text-ink-3">Authored for teaching; synthetic and not yet reviewed by faculty unless the case says so.</p>
        </Card>
      )}

      {!sim && result && (
        <Card title="Interaction result" eyebrow="The same four outputs every encounter fills" testid="interaction-result">
          <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
            <Stat label="Duration" value={`${result.duration_min} min`} />
            <Stat label="Information gained" value={`${result.information_gained.length}`} sub="findings" />
            <Stat label="Decision" value={dispWord(result.decision.disposition)} sub={result.decision.orders?.length ? result.decision.orders.map((o) => (/^(order|exam):/.test(o) ? requestLabel(o) : o)).join(", ") : "No orders"} />
            <Stat label="Quality" value={result.quality.toFixed(2)} sub="0 to 1, rule-based" />
          </div>
          <p className="mt-3 text-[12px] leading-relaxed text-ink-3">
            This case was opened on its own, not from a patient in a running simulation, so nothing was written back. Open a patient from the{" "}
            <Link href="/" className="font-semibold text-accent-dark hover:underline">
              hospital view
            </Link>{" "}
            and choose “Play this encounter” to see these values replace the sampled ones.
          </p>
        </Card>
      )}

      <Card title="Transcript" eyebrow={`${transcript.filter((t) => t.speaker === "student").length} learner turns`} testid="transcript">
        <details>
          <summary className="cursor-pointer text-[12.5px] font-semibold text-accent-dark">Show the full transcript</summary>
          <ol className="mt-3 space-y-1.5">
            {transcript.map((t, i) => (
              <li key={i} className="flex items-start gap-2 text-[12.5px] leading-snug">
                <span className="tnum mt-px inline-flex h-[18px] min-w-[18px] shrink-0 items-center justify-center rounded bg-[#141a33]/[0.06] px-1 text-[10px] font-semibold text-ink-2">{t.turn}</span>
                <span className="w-14 shrink-0 font-semibold text-ink-2">{t.speaker === "student" ? "You" : t.speaker === "patient" ? "Patient" : titleCase(t.speaker)}</span>
                <span className="min-w-0 flex-1 text-ink">{/^(order|exam|artifact):/.test(t.text) ? `Requested: ${requestLabel(t.text)}` : t.text}</span>
              </li>
            ))}
          </ol>
        </details>
      </Card>
    </div>
  );
}
