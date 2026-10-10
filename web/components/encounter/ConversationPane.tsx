"use client";
// The left pane: the conversation with the patient, quick requests, optional voice.
import { useEffect, useMemo, useRef, useState } from "react";
import { genderWord, requestGroup, requestLabel } from "@/lib/encounter/labels";
import type { AvailableRequest, LearnerCase, PatientView } from "@/lib/encounter/types";
import { canListen, canSpeak, listen, stopSpeaking, type Dictation } from "@/lib/encounter/voice";
import { Avatar, inputCls, Spinner } from "./ui";

export interface Msg {
  id: string;
  who: "student" | "patient" | "system";
  text: string;
  turn?: number;
  pending?: boolean;
  fallback?: boolean;
  unlocked?: number; // how many chart items this turn released
}

const GROUPS: { key: "exam" | "order" | "record"; label: string; verb: string }[] = [
  { key: "exam", label: "Examine", verb: "Examine" },
  { key: "order", label: "Order a test", verb: "Order" },
  { key: "record", label: "Records", verb: "Request" },
];

function Rapport({ value }: { value: number }) {
  const max = 6;
  const v = Math.max(0, Math.min(max, value));
  const word = value <= 0 ? "Guarded" : value < 3 ? "Warming" : value < 5 ? "Comfortable" : "Trusting";
  return (
    <div className="flex items-center gap-2" title="Rapport rises when you introduce yourself, ask open questions, acknowledge feelings and explain why you are asking. Some patients only share certain things once they trust you." data-testid="rapport" data-value={value}>
      <span className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-3">Rapport</span>
      <span className="flex gap-[3px]" aria-hidden>
        {Array.from({ length: max }, (_, i) => (
          <span key={i} className="h-1.5 w-4 rounded-full transition-colors duration-500" style={{ background: i < v ? "#2F55F5" : "rgba(20,26,51,0.1)" }} />
        ))}
      </span>
      <span className="text-[11px] font-semibold text-ink-2">{word}</span>
    </div>
  );
}

export function ConversationPane({
  kase,
  patient,
  messages,
  requests,
  requested,
  rapport,
  busy,
  finished,
  voiceOn,
  onVoice,
  onSend,
  onRequest,
}: {
  kase: LearnerCase;
  patient: PatientView;
  messages: Msg[];
  requests: AvailableRequest[];
  requested: Set<string>;
  rapport: number | null;
  busy: boolean;
  finished: boolean;
  voiceOn: boolean;
  onVoice: (on: boolean) => void;
  onSend: (text: string) => void;
  onRequest: (request: string) => void;
}) {
  const [text, setText] = useState("");
  const [panel, setPanel] = useState<"exam" | "order" | "record" | null>(null);
  const [filter, setFilter] = useState("");
  const [listening, setListening] = useState(false);
  const [speech, setSpeech] = useState({ out: false, in: false });
  const dict = useRef<Dictation | null>(null);
  const end = useRef<HTMLDivElement | null>(null);
  const input = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => setSpeech({ out: canSpeak(), in: canListen() }), []);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, busy]);

  const grouped = useMemo(() => {
    const g: Record<string, AvailableRequest[]> = { exam: [], order: [], record: [] };
    requests.forEach((r) => g[requestGroup(r.request, r.kind)].push(r));
    return g;
  }, [requests]);

  const send = () => {
    const t = text.trim();
    if (!t || busy || finished) return;
    setText("");
    onSend(t);
    input.current?.focus();
  };
  const toggleMic = () => {
    if (listening) {
      dict.current?.stop();
      return;
    }
    stopSpeaking();
    const d = listen(
      (t) => setText(t),
      () => setListening(false),
    );
    if (d) {
      dict.current = d;
      setListening(true);
    }
  };
  const shown = panel ? grouped[panel].filter((r) => requestLabel(r.request).toLowerCase().includes(filter.toLowerCase())) : [];

  return (
    <div className="glass flex h-full min-h-0 flex-col overflow-hidden" data-testid="conversation-pane">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line bg-white/50 px-4 py-3">
        <Avatar name={patient.name} image={patient.image} size={44} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[15px] font-semibold tracking-[-0.01em] text-ink">{patient.name ?? "Patient"}</div>
          <div className="truncate text-[11.5px] text-ink-3">
            {patient.age != null ? `${patient.age} y` : ""}
            {patient.gender ? ` · ${genderWord(patient.gender)}` : ""} · simulated patient
          </div>
        </div>
        {rapport != null && <Rapport value={rapport} />}
        {speech.out && (
          <button
            className="btn-quiet !h-7 !px-2.5"
            onClick={() => {
              if (voiceOn) stopSpeaking();
              onVoice(!voiceOn);
            }}
            aria-pressed={voiceOn}
            title={voiceOn ? "The patient's replies are read aloud. Click to mute." : "Read the patient's replies aloud"}
            data-testid="voice-toggle"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M4 9v6h4l5 4V5L8 9z" />
              {voiceOn ? <path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" /> : <path d="M17 9l5 6M22 9l-5 6" />}
            </svg>
            {voiceOn ? "Voice on" : "Muted"}
          </button>
        )}
      </div>

      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 py-3" data-testid="messages" aria-live="polite">
        {kase.prebrief && (
          <div className="mb-3 rounded-xl border border-accent/15 bg-accent-soft/60 px-3 py-2.5">
            <div className="eyebrow" style={{ color: "#1F3FD1" }}>
              Your brief
            </div>
            <p className="mt-0.5 text-[12.5px] leading-relaxed text-ink">{kase.prebrief}</p>
          </div>
        )}
        {messages.length === 0 && !busy && (
          <p className="py-6 text-center text-[12.5px] text-ink-3">Introduce yourself and ask what brought the patient in. Type below{speech.in ? " or use the microphone" : ""}.</p>
        )}
        <ul className="space-y-2.5">
          {messages.map((m) =>
            m.who === "system" ? (
              <li key={m.id} className="rise flex justify-center" data-testid="msg-system">
                <span className="max-w-[92%] rounded-full bg-[#141a33]/[0.05] px-3 py-1 text-center text-[11.5px] font-medium text-ink-2">{m.text}</span>
              </li>
            ) : m.who === "student" ? (
              <li key={m.id} className="rise flex justify-end" data-testid="msg-student">
                <div className="max-w-[82%] rounded-2xl rounded-br-md bg-accent px-3.5 py-2 text-[13.5px] leading-snug text-white shadow-pill">{m.text}</div>
              </li>
            ) : (
              <li key={m.id} className="rise flex items-end gap-2" data-testid="msg-patient">
                <Avatar name={patient.name} image={patient.image} size={26} />
                <div className="max-w-[82%]">
                  <div className="rounded-2xl rounded-bl-md border border-line bg-white px-3.5 py-2 text-[13.5px] leading-snug text-ink">{m.text}</div>
                  {(m.unlocked || m.fallback) && (
                    <div className="mt-1 flex gap-1.5 pl-1">
                      {m.unlocked ? (
                        <span className="chip" style={{ background: "#E3F4EA", color: "#1F7A4D" }} data-testid="msg-unlocked">
                          +{m.unlocked} in the chart
                        </span>
                      ) : null}
                      {m.fallback ? (
                        <span className="chip" style={{ background: "#FFF1D6", color: "#9A5B00" }} title="The language model did not answer in time; the authored wording was used.">
                          fallback
                        </span>
                      ) : null}
                    </div>
                  )}
                </div>
              </li>
            ),
          )}
          {busy && (
            <li className="flex items-end gap-2" data-testid="msg-typing">
              <Avatar name={patient.name} image={patient.image} size={26} />
              <div className="flex items-center gap-1 rounded-2xl rounded-bl-md border border-line bg-white px-3.5 py-3">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-3" style={{ animationDelay: `${i * 120}ms` }} />
                ))}
              </div>
            </li>
          )}
        </ul>
        <div ref={end} />
      </div>

      {!finished && (
        <div className="border-t border-line bg-white/55 px-3 pb-3 pt-2">
          {panel && (
            <div className="rise mb-2 rounded-xl border border-line bg-white/85 p-2.5" data-testid="request-panel">
              <div className="mb-2 flex items-center gap-2">
                <span className="eyebrow">{GROUPS.find((g) => g.key === panel)?.label}</span>
                <input className={`${inputCls} !h-7 max-w-[200px] !py-0 text-[12px]`} placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter requests" />
                <button className="btn ml-auto !h-6 !px-2 text-[11px]" onClick={() => setPanel(null)}>
                  Close
                </button>
              </div>
              <div className="scroll-thin flex max-h-[132px] flex-wrap gap-1.5 overflow-y-auto">
                {shown.map((r) => {
                  const done = requested.has(r.request);
                  return (
                    <button
                      key={r.request}
                      disabled={busy}
                      onClick={() => {
                        onRequest(r.request);
                        setPanel(null);
                        setFilter("");
                      }}
                      className={`inline-flex h-7 items-center gap-1 rounded-full border px-2.5 text-[12px] font-medium transition-colors disabled:opacity-40 ${done ? "border-[#BFE5CF] bg-[#E3F4EA] text-[#1F7A4D]" : "border-line bg-white text-ink-2 hover:border-accent/40 hover:text-accent-dark"}`}
                      data-testid="request-option"
                      data-request={r.request}
                      title={done ? "Already requested" : r.request}
                    >
                      {done && "✓ "}
                      {requestLabel(r.request)}
                    </button>
                  );
                })}
                {shown.length === 0 && <span className="px-1 py-1 text-[12px] text-ink-3">Nothing matches.</span>}
              </div>
            </div>
          )}
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            {GROUPS.filter((g) => grouped[g.key].length > 0).map((g) => (
              <button
                key={g.key}
                className={`btn-quiet !h-7 !px-2.5 ${panel === g.key ? "!border-accent/50 !text-accent-dark" : ""}`}
                onClick={() => {
                  setPanel(panel === g.key ? null : g.key);
                  setFilter("");
                }}
                data-testid={`quick-${g.key}`}
              >
                {g.label}
                <span className="tnum text-[10.5px] font-medium text-ink-3">{grouped[g.key].length}</span>
              </button>
            ))}
            <span className="ml-auto hidden text-[11px] text-ink-3 sm:inline">Enter to send · Shift+Enter for a new line</span>
          </div>
          <div className="flex items-end gap-2">
            <textarea
              ref={input}
              rows={1}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder={listening ? "Listening…" : `Say something to ${patient.name?.split(" ")[0] ?? "the patient"}…`}
              className={`${inputCls} max-h-28 min-h-[38px] resize-none !rounded-2xl !px-3.5 !py-2 text-[13.5px]`}
              maxLength={2000}
              aria-label="Your message to the patient"
              data-testid="chat-input"
            />
            {speech.in && (
              <button className={`flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-full border transition-colors ${listening ? "border-[#D8434C] bg-[#FDE7E7] text-[#B4232C]" : "border-line bg-white/80 text-ink-2 hover:text-accent-dark"}`} onClick={toggleMic} aria-pressed={listening} aria-label={listening ? "Stop dictation" : "Dictate"} title={listening ? "Stop dictation" : "Dictate with the microphone"} data-testid="mic">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3" />
                </svg>
              </button>
            )}
            <button className="btn-primary !h-[38px] shrink-0 !px-4" onClick={send} disabled={busy || !text.trim()} data-testid="chat-send">
              {busy ? <Spinner size={12} /> : "Send"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
