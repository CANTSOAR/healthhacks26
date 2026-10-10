"use client";
// The handoff stage: write an SBAR from the shared record, then answer the receiving colleague's questions.
import { useEffect, useRef, useState } from "react";
import type { HandoffView, Stage } from "@/lib/journey/types";
import { inputCls, Spinner } from "@/components/encounter/ui";
import { RoleAvatar } from "./StageRail";

const PARTS: { key: "situation" | "background" | "assessment" | "recommendation"; letter: string; label: string; hint: string }[] = [
  { key: "situation", letter: "S", label: "Situation", hint: "What is happening with the patient right now?" },
  { key: "background", letter: "B", label: "Background", hint: "History the receiver needs: conditions, medicines, allergies, what the patient was slow to say." },
  { key: "assessment", letter: "A", label: "Assessment", hint: "What was found. Keep findings apart from your interpretation; say what is uncertain." },
  { key: "recommendation", letter: "R", label: "Recommendation", hint: "The plan, what is pending, and what you need the receiver to do first." },
];

export function HandoffStage({ stage, handoff, busy, onSbar, onAnswer, onFinish }: { stage: Stage; handoff: HandoffView; busy: boolean; onSbar: (b: Record<string, string>) => void; onAnswer: (t: string) => void; onFinish: () => void }) {
  const [sbar, setSbar] = useState<Record<string, string>>({ situation: "", background: "", assessment: "", recommendation: "" });
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement | null>(null);
  const col = handoff.colleague;
  const composing = handoff.phase === "compose";
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [handoff.messages.length]);
  const send = () => {
    const t = text.trim();
    if (!t || busy) return;
    setText("");
    onAnswer(t);
  };
  return (
    <div className="glass flex h-full min-h-0 flex-col overflow-hidden" data-testid="handoff-stage" data-phase={handoff.phase}>
      <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-line px-4 py-3">
        <RoleAvatar staffRole="attending" name={col.name} size={42} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[15px] font-semibold tracking-[-0.01em] text-ink" data-testid="colleague-name">{col.name}</div>
          <div className="truncate text-[11.5px] text-ink-3">
            {col.label ?? col.role} · AI colleague receiving the handoff · fictional
          </div>
        </div>
        {!composing && (
          <span className="chip" style={{ background: "rgba(20,26,51,0.06)", color: "#4A5275" }} data-testid="question-count">
            {handoff.questions.length} of up to {handoff.max_questions} questions asked
          </span>
        )}
        {!composing && (
          <button className="btn-primary" onClick={onFinish} disabled={busy} data-testid="handoff-finish">
            Finish handoff
          </button>
        )}
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 py-3">
        <div className="mb-3 rounded-xl bg-accent-soft/60 px-3 py-2 text-[12.5px] leading-relaxed text-ink">{stage.brief}</div>
        <ol className="grid gap-2.5">
          {handoff.messages.map((m, i) =>
            m.who === "colleague" ? (
              <li key={i} className="flex items-start gap-2" data-testid="msg-colleague" data-kind={m.kind ?? "opening"}>
                <RoleAvatar staffRole="attending" name={col.name} size={26} />
                <div className="max-w-[85%] rounded-2xl rounded-tl-md border border-line bg-white px-3 py-2 text-[13px] leading-relaxed text-ink">{m.text}</div>
              </li>
            ) : (
              <li key={i} className="flex justify-end" data-testid="msg-learner">
                <div className="max-w-[85%] whitespace-pre-line rounded-2xl rounded-tr-md bg-accent px-3 py-2 text-[13px] leading-relaxed text-white">{m.text}</div>
              </li>
            ),
          )}
        </ol>
        {composing && (
          <div className="mt-4 grid gap-2.5" data-testid="sbar-composer">
            {PARTS.map((p) => (
              <label key={p.key} className="block">
                <span className="mb-1 flex items-center gap-2 text-[12px] font-semibold text-ink">
                  <span className="inline-flex h-5 w-5 items-center justify-center rounded-md bg-accent text-[11px] text-white">{p.letter}</span>
                  {p.label}
                  <span className="font-normal text-ink-3">{p.hint}</span>
                </span>
                <textarea className={`${inputCls} min-h-[64px] resize-y leading-relaxed`} value={sbar[p.key]} onChange={(e) => setSbar({ ...sbar, [p.key]: e.target.value })} data-testid={`sbar-${p.key}`} />
              </label>
            ))}
            <div className="flex flex-wrap items-center gap-2">
              <button className="btn-primary !h-9 !px-4" disabled={busy || !Object.values(sbar).some((v) => v.trim())} onClick={() => onSbar(sbar)} data-testid="sbar-submit">
                {busy && <Spinner size={12} />} Give the handoff
              </button>
              <span className="text-[11.5px] text-ink-3">It is checked against the shared record on the right: what the team learned, not the hidden case.</span>
            </div>
          </div>
        )}
        <div ref={end} />
      </div>
      {!composing && (
        <div className="flex shrink-0 items-center gap-2 border-t border-line px-3 py-2.5">
          <input className={inputCls} placeholder={handoff.phase === "questions" ? `Answer ${col.name.split(" ").slice(-1)[0]}…` : "Add anything else, or finish the handoff"} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} disabled={busy} data-testid="handoff-input" />
          <button className="btn-primary" onClick={send} disabled={busy || !text.trim()} data-testid="handoff-send">
            {busy ? <Spinner size={12} /> : "Send"}
          </button>
        </div>
      )}
    </div>
  );
}
