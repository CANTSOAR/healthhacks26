"use client";
// A patient-facing stage, played in its role: the encounter's own conversation and chart panes, driven through the journey
// routes so that everything released is also written to the shared record.
import { useEffect, useMemo, useState } from "react";
import { ChartPane } from "@/components/encounter/ChartPane";
import { ConversationPane, type Msg } from "@/components/encounter/ConversationPane";
import { Field, InlineError, inputCls, Modal, Spinner } from "@/components/encounter/ui";
import { ApiError, newRequestId } from "@/lib/encounter/api";
import { requestLabel } from "@/lib/encounter/labels";
import type { LedgerEvent } from "@/lib/encounter/types";
import { journeyApi, lc } from "@/lib/journey/api";
import type { SharedRecord, Stage, StageEncounter, StageView } from "@/lib/journey/types";

function fromLedger(ledger: LedgerEvent[]): Msg[] {
  const out: Msg[] = [];
  for (const e of [...ledger].sort((a, b) => a.seq - b.seq)) {
    if (e.kind === "turn") {
      out.push({ id: `s${e.seq}`, who: "student", text: e.text ?? "", turn: e.turn });
      if (e.reply) out.push({ id: `p${e.seq}`, who: "patient", text: e.reply, turn: e.turn, unlocked: e.disclosed_fact_ids.length + e.released_artifact_ids.length || undefined });
    } else if (e.kind === "request") {
      const n = e.disclosed_fact_ids.length + e.released_artifact_ids.length;
      out.push({ id: `r${e.seq}`, who: "system", text: `Requested ${requestLabel(e.request ?? "")}${n ? " · result added to the chart" : ""}`, turn: e.turn });
    }
  }
  return out;
}

const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

function FinishDialog({ stage, busy, error, onCancel, onSubmit }: { stage: Stage; busy: boolean; error: string | null; onCancel: () => void; onSubmit: (body: Record<string, unknown>) => void }) {
  const keys = [...stage.writes.required, ...(stage.writes.optional ?? [])];
  const req = (k: string) => stage.writes.required.includes(k);
  const [acuity, setAcuity] = useState<number | null>(null);
  const [disposition, setDisposition] = useState("");
  const [note, setNote] = useState("");
  const [meds, setMeds] = useState("");
  const [plan, setPlan] = useState("");
  const [open, setOpen] = useState("");
  const [orders, setOrders] = useState("");
  const ready = (!req("acuity") || acuity) && (!req("disposition") || disposition) && (!req("note") || note.trim()) && (!req("med_list") || meds.trim());
  const tag = (k: string) => (req(k) ? "" : " (optional)");
  return (
    <Modal title={`Finish ${stage.title.toLowerCase()}: write to the shared record`} onClose={onCancel} wide>
      <div className="grid gap-3" data-testid="stage-finish-dialog">
        <p className="text-[12.5px] leading-relaxed text-ink-2">What you write here is what the next role starts from. It is recorded under your role with this stage as its source.</p>
        {keys.includes("acuity") && (
          <Field label="Acuity (ESI)" hint="1 is the most urgent, 5 the least.">
            <div className="seg" data-testid="finish-acuity">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} type="button" data-on={acuity === n} onClick={() => setAcuity(n)} data-testid={`acuity-${n}`}>
                  ESI {n}
                </button>
              ))}
            </div>
          </Field>
        )}
        {keys.includes("disposition") && (
          <Field label="Disposition">
            <div className="seg" data-testid="finish-disposition">
              {["discharge", "admit", "transfer"].map((d) => (
                <button key={d} type="button" data-on={disposition === d} onClick={() => setDisposition(d)} data-testid={`disposition-${d}`}>
                  {d.charAt(0).toUpperCase() + d.slice(1)}
                </button>
              ))}
            </div>
          </Field>
        )}
        {keys.includes("note") && (
          <Field label={`${stage.interaction_type === "triage" ? "Triage note" : "Assessment note"}${tag("note")}`} hint="A figure, medicine, allergy, test or imaging result, or piece of past history that nobody recorded is flagged as unsupported. Free-text reasoning is not checked.">
            <textarea className={`${inputCls} min-h-[72px]`} value={note} onChange={(e) => setNote(e.target.value)} data-testid="finish-note" />
          </Field>
        )}
        {keys.includes("med_list") && (
          <Field label={`Reconciled medication list${tag("med_list")}`} hint="One medicine per line, with what the patient actually takes.">
            <textarea className={`${inputCls} min-h-[84px]`} value={meds} onChange={(e) => setMeds(e.target.value)} data-testid="finish-med-list" />
          </Field>
        )}
        {keys.includes("orders") && (
          <Field label="Further orders (optional)" hint="One per line, for example: bmp. Orders placed now have no result yet and show as pending.">
            <textarea className={`${inputCls} min-h-[44px]`} value={orders} onChange={(e) => setOrders(e.target.value)} data-testid="finish-orders" />
          </Field>
        )}
        {keys.includes("plan") && (
          <Field label="Plan items (optional)" hint="One per line.">
            <textarea className={`${inputCls} min-h-[44px]`} value={plan} onChange={(e) => setPlan(e.target.value)} data-testid="finish-plan" />
          </Field>
        )}
        {keys.includes("open_questions") && (
          <Field label="Open questions (optional)" hint="What is still uncertain or needs someone else. One per line.">
            <textarea className={`${inputCls} min-h-[44px]`} value={open} onChange={(e) => setOpen(e.target.value)} data-testid="finish-open-questions" />
          </Field>
        )}
        {error && <InlineError>{error}</InlineError>}
        <div className="flex justify-end gap-2">
          <button className="btn-quiet" onClick={onCancel} disabled={busy}>
            Keep going
          </button>
          <button className="btn-primary" disabled={busy || !ready} data-testid="finish-submit" onClick={() => onSubmit({ acuity: acuity ?? undefined, disposition: disposition || undefined, note, med_list: lines(meds), plan: lines(plan), open_questions: lines(open), orders: lines(orders) })}>
            {busy && <Spinner size={12} />} Write to the record and finish
          </button>
        </div>
      </div>
    </Modal>
  );
}

export function PatientStage({ journeyId, stage, view, pane, onRecord, onFinished }: { journeyId: string; stage: Stage; view: StageView; pane: "stage" | "chart" | "record"; onRecord: (r: SharedRecord, added: string[]) => void; onFinished: (v: StageView) => void }) {
  const [enc, setEnc] = useState<StageEncounter>(view.encounter!);
  const [messages, setMessages] = useState<Msg[]>(() => fromLedger(view.encounter!.ledger));
  const [ledger, setLedger] = useState<LedgerEvent[]>(view.encounter!.ledger);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finishOpen, setFinishOpen] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [finishError, setFinishError] = useState<string | null>(null);
  const [voiceOn, setVoiceOn] = useState(false);
  const requested = useMemo(() => new Set(ledger.filter((e) => e.kind === "request" && e.request).map((e) => e.request!)), [ledger]);
  useEffect(() => setError(null), [stage.stage_id]);

  async function act(kind: "turn" | "request", text: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    const rid = newRequestId();
    const tmp = `t-${rid}`;
    setMessages((m) => [...m, kind === "turn" ? { id: tmp, who: "student", text } : { id: tmp, who: "system", text: `Requested ${requestLabel(text)}…` }, ...(kind === "turn" ? [{ id: `${tmp}-p`, who: "patient" as const, text: "", pending: true }] : [])]);
    try {
      const r = kind === "turn" ? await journeyApi.turn(journeyId, stage.stage_id, text, rid) : await journeyApi.request(journeyId, stage.stage_id, text, rid);
      const n = r.disclosed.length + r.released_artifacts.length;
      setMessages((m) => {
        const base = m.filter((x) => x.id !== `${tmp}-p` && (kind === "turn" || x.id !== tmp));
        return kind === "turn" ? [...base, { id: `p-${rid}`, who: "patient", text: r.reply ?? "", turn: r.turn, unlocked: n || undefined }] : [...base, { id: `r-${rid}`, who: "system", text: r.notes.join(" "), turn: r.turn }];
      });
      setLedger((prev) => {
        const m = new Map(prev.map((e) => [e.seq, e]));
        r.ledger_tail.forEach((e) => m.set(e.seq, e));
        return [...m.values()].sort((a, b) => a.seq - b.seq);
      });
      setEnc((e) => ({ ...e, chart: r.chart, rapport: r.rapport ?? e.rapport }));
      onRecord(r.record, r.record_added);
    } catch (e) {
      setMessages((m) => m.filter((x) => x.id !== `${tmp}-p` && x.id !== tmp));
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function finish(body: Record<string, unknown>) {
    setFinishing(true);
    setFinishError(null);
    try {
      const v = await journeyApi.finish(journeyId, stage.stage_id, body);
      setFinishOpen(false);
      onFinished(v);
    } catch (e) {
      setFinishError((e as ApiError).message);
    } finally {
      setFinishing(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-2" data-testid="patient-stage">
      <div className="flex shrink-0 flex-wrap items-center gap-2 px-1">
        <span className="text-[12px] text-ink-2">
          You are the <b className="text-ink">{lc(stage.learner_role.label)}</b>. Requests outside this role&apos;s scope are not offered.
        </span>
        <button className="btn-primary ml-auto" onClick={() => setFinishOpen(true)} disabled={busy} data-testid="stage-finish-open">
          Finish stage and write to the record
        </button>
      </div>
      {error && <InlineError>{error}</InlineError>}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 min-[1400px]:grid-cols-2">
        <div className={`min-h-0 ${pane === "stage" ? "" : "hidden min-[1400px]:block"}`}>
          <ConversationPane kase={enc.case} patient={view.patient} messages={messages} requests={enc.available_requests} requested={requested} rapport={enc.rapport} busy={busy} finished={false} voiceOn={voiceOn} onVoice={setVoiceOn} onSend={(t) => act("turn", t)} onRequest={(r) => act("request", r)} />
        </div>
        <div className={`min-h-0 ${pane === "chart" ? "" : "hidden min-[1400px]:block"}`}>
          <ChartPane kase={enc.case} patient={view.patient} chart={enc.chart} ledger={ledger} />
        </div>
      </div>
      {finishOpen && <FinishDialog stage={stage} busy={finishing} error={finishError} onCancel={() => setFinishOpen(false)} onSubmit={finish} />}
    </div>
  );
}
