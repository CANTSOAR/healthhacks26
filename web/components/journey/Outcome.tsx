"use client";
// The end of the journey: a care plan assembled only from the shared record, and the debrief per stage, per role and for the team.
import { useEffect, useState } from "react";
import { OBJECTIVE_LABEL, OBJECTIVE_TONE } from "@/lib/encounter/labels";
import type { ObjectiveLabel } from "@/lib/encounter/types";
import { journeyApi, roleTone } from "@/lib/journey/api";
import type { CarePlan, Debrief, PlanRow, Stage } from "@/lib/journey/types";
import { InlineError, Spinner, Tone } from "@/components/encounter/ui";
import { DiscrepancyCard, ProvenanceChips } from "./RecordPanel";
import { ObjectiveList, SbarReport } from "./StagePanels";
import { RoleAvatar } from "./StageRail";

function Row({ r }: { r: PlanRow }) {
  return (
    <li className="rounded-lg border border-line bg-white/70 p-2" data-testid="plan-row">
      <div className="text-[12.5px] leading-snug text-ink">{r.kind === "patient_report" ? `“${r.text}”` : r.text}</div>
      <div className="mt-1">
        <ProvenanceChips p={r} sourceLabel={r.source_label} />
      </div>
    </li>
  );
}

function Card({ title, note, children, testid }: { title: string; note?: string; children: React.ReactNode; testid?: string }) {
  return (
    <section className="glass p-4" data-testid={testid}>
      <h3 className="text-[14px] font-semibold tracking-[-0.01em] text-ink">{title}</h3>
      {note && <p className="mt-0.5 text-[11.5px] leading-snug text-ink-3">{note}</p>}
      <div className="mt-2.5">{children}</div>
    </section>
  );
}

const Empty = ({ children }: { children: React.ReactNode }) => <p className="text-[12px] text-ink-3">{children}</p>;

function Plan({ cp, stages }: { cp: CarePlan; stages: Stage[] }) {
  const title = (id: string) => stages.find((s) => s.stage_id === id)?.title ?? id;
  const d = cp.decisions;
  return (
    <div className="grid gap-3" data-testid="care-plan">
      <div className="glass flex flex-wrap items-center gap-x-6 gap-y-2 p-4">
        <div>
          <div className="eyebrow">Integrated care plan{cp.complete ? "" : " so far"}</div>
          <div className="text-[18px] font-semibold tracking-[-0.02em] text-ink">
            {cp.patient.name}
            {cp.patient.age ? `, ${cp.patient.age}` : ""}
          </div>
        </div>
        <div className="text-[12px] text-ink-2">
          <div className="text-ink-3">Acuity</div>
          <div className="font-semibold text-ink">{d.acuity ? `ESI ${d.acuity.value} · ${d.acuity.by.role_label}` : "not recorded"}</div>
        </div>
        <div className="text-[12px] text-ink-2">
          <div className="text-ink-3">Disposition</div>
          <div className="font-semibold text-ink" data-testid="plan-disposition">{d.disposition ? `${String(d.disposition.value)} · ${d.disposition.by.role_label}` : "not recorded"}</div>
        </div>
        <div className="ml-auto max-w-sm text-[11.5px] leading-snug text-ink-3" data-testid="plan-source">
          Assembled from {cp.n_entries} entries of {cp.assembled_from}.
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <Card title="Problems, with the evidence and the actions that answer them" note="Each problem is a record entry; evidence and actions are linked by shared wording, not by a model." testid="plan-coordinated">
          {cp.coordinated_plan.length ? (
            <ul className="grid gap-2.5">
              {cp.coordinated_plan.map((c) => (
                <li key={c.problem.entry_id} className="rounded-xl border border-line bg-white/60 p-2.5">
                  <div className="text-[13px] font-semibold leading-snug text-ink">{c.problem.text}</div>
                  <div className="mt-1"><ProvenanceChips p={c.problem} sourceLabel={c.problem.source_label} /></div>
                  {c.evidence.length > 0 && <div className="mt-2 text-[11.5px] leading-snug text-ink-2"><b>Evidence:</b> {c.evidence.map((e) => `${e.text} (${e.by.role_label})`).join("; ")}</div>}
                  {c.actions.length > 0 && <div className="mt-1 text-[11.5px] leading-snug text-ink-2"><b>Actions:</b> {c.actions.map((e) => `${e.text} (${e.by.role_label})`).join("; ")}</div>}
                </li>
              ))}
            </ul>
          ) : (
            <Empty>No problem has been recorded yet.</Empty>
          )}
        </Card>
        <div className="grid content-start gap-3">
          <Card title="Open questions" note="Pending results, unsettled conflicts, unanswered questions and unsupported statements." testid="plan-open">
            {cp.open_questions.length ? (
              <ul className="grid gap-1.5">
                {cp.open_questions.map((q, i) => (
                  <li key={i} className="rounded-lg border px-2 py-1.5 text-[12px] leading-snug" style={{ background: "#FFF6E0", borderColor: "#F1D58A", color: "#5C4100" }}>
                    {q.text} <span className="opacity-70">· {q.why}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>Nothing is open on the record.</Empty>
            )}
          </Card>
          <Card title="Medicines and allergies">
            {cp.medications.length + cp.allergies.length ? <ul className="grid gap-1.5">{[...cp.allergies, ...cp.medications].map((r) => <Row key={r.entry_id} r={r} />)}</ul> : <Empty>Not recorded by any role.</Empty>}
          </Card>
          <Card title="Plan and orders">
            {cp.plan.length + cp.orders.length ? <ul className="grid gap-1.5">{[...cp.plan, ...cp.orders].map((r) => <Row key={r.entry_id} r={r} />)}</ul> : <Empty>No plan item or order is on the record.</Empty>}
          </Card>
        </div>
      </div>
      {cp.discrepancies.length > 0 && (
        <Card title="Conflicting information" note="Both sides and who recorded each.">
          <div className="grid gap-2 lg:grid-cols-2">{cp.discrepancies.map((x) => <DiscrepancyCard key={x.discrepancy_id} d={x} />)}</div>
        </Card>
      )}
      <Card title="What each profession contributed" testid="plan-contributions">
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {cp.contributions.map((c) => {
            const t = roleTone(c.role.staff_role);
            return (
              <div key={c.stage_id} className="rounded-xl border border-line bg-white/60 p-2.5">
                <div className="flex items-center gap-2">
                  <RoleAvatar staffRole={c.role.staff_role} name={c.played_by === "human" ? c.role.label : c.player} size={28} />
                  <div className="min-w-0">
                    <div className="truncate text-[12.5px] font-semibold" style={{ color: t.fg }}>{c.role.label}</div>
                    <div className="truncate text-[10.5px] text-ink-3">{c.stage_title} · {c.played_by === "human" ? "you" : c.played_by === "sim" ? "simulation" : c.played_by ? `sampled, ${c.player}` : "not played yet"}</div>
                  </div>
                </div>
                <ul className="mt-2 grid gap-1 text-[11.5px] leading-snug text-ink-2">
                  {c.highlights.slice(0, 5).map((h) => <li key={h.entry_id}>• {h.text}</li>)}
                  {!c.highlights.length && <li className="text-ink-3">Nothing recorded.</li>}
                </ul>
              </div>
            );
          })}
        </div>
      </Card>
      <Card title="How earlier information was used later" note="A line appears when a later role asked about, raised, looked up or handed over something an earlier role recorded." testid="plan-flow">
        {cp.information_flow.length ? (
          <ul className="grid gap-1.5">
            {cp.information_flow.slice(0, 14).map((f, i) => (
              <li key={i} className="flex flex-wrap items-center gap-1.5 text-[12px] leading-snug text-ink">
                <Tone bg={roleTone(f.entry.by.staff_role).bg} fg={roleTone(f.entry.by.staff_role).fg}>{f.entry.stage_title}</Tone>
                <span className="min-w-0 flex-1 basis-56 truncate">{f.entry.text}</span>
                <span className="text-ink-3">→</span>
                <Tone bg="#E3F4EA" fg="#1F7A4D">{title(f.used_in_stage)}: {f.how}</Tone>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>No later stage has built on an earlier entry yet.</Empty>
        )}
      </Card>
    </div>
  );
}

function Counts({ counts }: { counts: Record<ObjectiveLabel, number> }) {
  return (
    <span className="flex flex-wrap gap-1">
      {(Object.keys(OBJECTIVE_LABEL) as ObjectiveLabel[]).filter((k) => counts[k]).map((k) => (
        <Tone key={k} bg={OBJECTIVE_TONE[k].bg} fg={OBJECTIVE_TONE[k].fg}>{counts[k]} {OBJECTIVE_LABEL[k].toLowerCase()}</Tone>
      ))}
    </span>
  );
}

function DebriefView({ db }: { db: Debrief }) {
  const t = db.team;
  const stat = (n: number, label: string, warn = false) => (
    <div className="rounded-xl border border-line bg-white/60 px-3 py-2">
      <div className="tnum text-[20px] font-semibold tracking-[-0.02em]" style={{ color: warn && n ? "#9A5B00" : "#141A33" }}>{n}</div>
      <div className="text-[11px] leading-snug text-ink-3">{label}</div>
    </div>
  );
  return (
    <div className="grid gap-3" data-testid="debrief">
      <Card title="Team debrief" note={db.formative_note} testid="team-debrief">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {stat(t.summary.carried_forward, "entries used by a later stage")}
          {stat(t.summary.lost_at_handoff, "critical items lost at handoff", true)}
          {stat(t.summary.unresolved_discrepancies, "conflicts left unsettled", true)}
          {stat(t.summary.unsupported_statements, "statements with no support", true)}
          {stat(t.summary.critical_never_found, "critical facts nobody found", true)}
          {stat(t.summary.facts_recorded, "case facts on the record")}
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <div data-testid="team-lost">
            <div className="eyebrow mb-1">Information lost between stages</div>
            {t.information_lost.length ? (
              <ul className="grid gap-1.5">
                {t.information_lost.slice(0, 8).map((x, i) => (
                  <li key={i} className="rounded-lg border border-line bg-white/70 p-2 text-[12px] leading-snug text-ink">
                    {x.text}
                    <div className="mt-1 flex flex-wrap items-center gap-1"><ProvenanceChips p={x.provenance} /><span className="text-[10.5px] text-ink-3">{x.how}</span></div>
                  </li>
                ))}
              </ul>
            ) : <Empty>Every critical item on the record reached the receiver.</Empty>}
          </div>
          <div className="grid content-start gap-3">
            <div>
              <div className="eyebrow mb-1">Stated without support in the record</div>
              {t.unsupported_statements.length ? (
                <ul className="grid gap-1">{t.unsupported_statements.map((u, i) => <li key={i} className="text-[12px] leading-snug" style={{ color: "#8E1B23" }}>“{u.quote}”: {u.reason}.</li>)}</ul>
              ) : <Empty>None.</Empty>}
            </div>
            <div>
              <div className="eyebrow mb-1">In the case, never reached the record</div>
              {t.never_found.length ? <ul className="grid gap-1">{t.never_found.map((n) => <li key={n.fact_id} className="text-[12px] leading-snug text-ink-2">• {n.text}</li>)}</ul> : <Empty>The team found every critical fact.</Empty>}
            </div>
            {db.case_debrief.diagnosis && (
              <div className="rounded-lg bg-accent-soft/60 p-2 text-[12px] leading-snug text-ink">
                <b>Case diagnosis:</b> {db.case_debrief.diagnosis}. Expected disposition {db.case_debrief.expected_disposition ?? "not defined"}; the team recorded {db.case_debrief.recorded_disposition ?? "none"}.
              </div>
            )}
          </div>
        </div>
      </Card>
      <Card title="By role" testid="role-debrief">
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {db.roles.map((r) => (
            <div key={r.role.label} className="rounded-xl border border-line bg-white/60 p-2.5">
              <div className="flex items-center gap-2">
                <RoleAvatar staffRole={r.role.staff_role} name={r.role.label} size={26} />
                <div className="text-[12.5px] font-semibold text-ink">{r.role.label}</div>
              </div>
              <div className="mt-1 text-[10.5px] text-ink-3">{r.played_by.map((p) => (p === "human" ? "played by you" : p === "sim" ? "simulation" : "sampled")).join(", ")}</div>
              <div className="mt-1.5"><Counts counts={r.counts} /></div>
            </div>
          ))}
        </div>
      </Card>
      {db.stages.map((s) => (
        <Card key={s.stage_id} title={`${s.title} · ${s.role.label}`} note={`${s.played_by === "human" ? "Played by you" : s.played_by === "sim" ? "Resolved by the simulation" : `Sampled (${s.player})`} · use ${s.behaviors.use.not_assessable ? "n/a" : s.behaviors.use.count} · contribute ${s.behaviors.contribute.count} · identify ${s.behaviors.identify.count} · communicate ${s.behaviors.communicate.count}`} testid="stage-debrief">
          <ObjectiveList objectives={s.objectives} />
          {s.handoff && <div className="mt-3"><SbarReport grading={s.handoff.grading} /></div>}
          {s.encounter_feedback?.next_time?.length ? <div className="mt-2 text-[12px] leading-snug text-ink-2"><b className="text-ink">Next time:</b> {s.encounter_feedback.next_time.slice(0, 3).join(" ")}</div> : null}
        </Card>
      ))}
    </div>
  );
}

export function Outcome({ journeyId, complete, stages, version }: { journeyId: string; complete: boolean; stages: Stage[]; version: number }) {
  const [cp, setCp] = useState<CarePlan | null>(null);
  const [db, setDb] = useState<Debrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"plan" | "debrief">("plan");
  useEffect(() => {
    let dead = false;
    journeyApi.carePlan(journeyId).then((x) => !dead && setCp(x)).catch((e) => !dead && setError(e.message));
    if (complete) journeyApi.debrief(journeyId).then((x) => !dead && setDb(x)).catch((e) => !dead && setError(e.message));
    return () => {
      dead = true;
    };
  }, [journeyId, complete, version]);
  if (error) return <InlineError>{error}</InlineError>;
  if (!cp) return <div className="glass flex items-center gap-2 p-4 text-[13px] text-ink-2"><Spinner /> Assembling the care plan from the shared record…</div>;
  return (
    <div className="scroll-thin h-full overflow-y-auto pr-1" data-testid="outcome">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <div className="seg">
          <button data-on={tab === "plan"} onClick={() => setTab("plan")} data-testid="tab-plan">Care plan</button>
          <button data-on={tab === "debrief"} onClick={() => setTab("debrief")} data-testid="tab-debrief">Debrief</button>
        </div>
        {!complete && <span className="text-[12px] text-ink-3">The journey is not finished: this is the plan so far. The debrief opens when every stage is complete.</span>}
      </div>
      {tab === "plan" ? <Plan cp={cp} stages={stages} /> : db ? <DebriefView db={db} /> : <div className="glass p-4 text-[13px] text-ink-2" data-testid="debrief-locked">The debrief opens when every stage is complete, so that nothing from the case is shown to a role that has not played yet.</div>}
    </div>
  );
}
