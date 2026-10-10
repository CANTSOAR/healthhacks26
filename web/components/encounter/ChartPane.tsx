"use client";
// The right pane: a chart laid out like a clinical record, plus the disclosure ledger.
// Only learner-visible content reaches this component (the API never sends faculty truth to the student view).
import { useEffect, useMemo, useRef, useState } from "react";
import { assetUrl } from "@/lib/encounter/api";
import { genderWord, requestLabel, RULE_LABEL, RULE_TONE } from "@/lib/encounter/labels";
import type { Chart, ChartArtifact, ChartFact, ChartSection, LabRow, LearnerCase, LedgerEvent, PatientView } from "@/lib/encounter/types";
import { Avatar, SyntheticLabel, Tone } from "./ui";

const FRESH_MS = 5000;

/** Tracks which chart items appeared since the last update so they can be highlighted for a few seconds. */
function useFresh(chart: Chart): Set<string> {
  const seen = useRef<Set<string> | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  useEffect(() => {
    const ids: string[] = [];
    for (const s of chart.sections) {
      if (!s.visible) continue;
      ids.push(`s:${s.section_id}`);
      s.facts.forEach((f) => ids.push(`f:${f.fact_id}`));
      s.notes.forEach((n) => ids.push(`n:${n.note_id}`));
    }
    chart.artifacts.forEach((a) => ids.push(`a:${a.artifact_id}`));
    if (seen.current === null) {
      seen.current = new Set(ids); // first paint: nothing is "new"
      return;
    }
    const added = ids.filter((i) => !seen.current!.has(i));
    if (!added.length) return;
    added.forEach((i) => seen.current!.add(i));
    setFresh((prev) => new Set([...prev, ...added]));
    const timer = setTimeout(() => {
      setFresh((prev) => {
        const next = new Set(prev);
        added.forEach((i) => next.delete(i));
        return next;
      });
    }, FRESH_MS);
    return () => clearTimeout(timer);
  }, [chart]);
  return fresh;
}

const freshCls = (on: boolean) => `transition-[background-color,box-shadow] duration-[1400ms] ${on ? "bg-[#FFF6D6] shadow-[0_0_0_2px_#F4D675]" : "bg-transparent shadow-[0_0_0_0px_transparent]"}`;

function NewTag() {
  return (
    <span className="chip rise" style={{ background: "#F4D675", color: "#6B4A00" }} data-testid="new-tag">
      New
    </span>
  );
}

function sourceWord(f: ChartFact): string {
  if (f.source === "patient") return "Patient";
  if (f.source === "result") return "Result";
  return "Triage";
}

function FactRow({ f, fresh }: { f: ChartFact; fresh: boolean }) {
  return (
    <li className={`flex items-start gap-2 rounded-lg px-2 py-1.5 ${freshCls(fresh)}`} data-testid="chart-fact" data-fact-id={f.fact_id}>
      <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-ink-3" />
      <span className="min-w-0 flex-1 text-[13px] leading-snug text-ink">{f.text}</span>
      {fresh && <NewTag />}
      <span className="tnum shrink-0 whitespace-nowrap pt-px text-[10.5px] font-medium text-ink-3" title={f.rule ? `Disclosure rule: ${RULE_LABEL[f.rule] ?? f.rule}` : undefined}>
        {sourceWord(f)}
        {f.turn ? ` · turn ${f.turn}` : ""}
      </span>
    </li>
  );
}

function VitalsGrid({ facts, fresh }: { facts: ChartFact[]; fresh: Set<string> }) {
  const tiles = facts.filter((f) => f.label && f.value !== undefined && f.value !== null);
  const rest = facts.filter((f) => !(f.label && f.value !== undefined && f.value !== null));
  return (
    <div>
      {tiles.length > 0 && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {tiles.map((f) => (
            <div key={f.fact_id} className={`rounded-xl border border-line px-3 py-2 ${fresh.has(`f:${f.fact_id}`) ? "bg-[#FFF6D6]" : "bg-white/70"}`} data-testid="vital-tile">
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-3">{f.label}</div>
              <div className="tnum mt-0.5 text-[18px] font-semibold leading-tight tracking-[-0.01em] text-ink">
                {String(f.value)} <span className="text-[11px] font-medium text-ink-3">{f.unit}</span>
              </div>
            </div>
          ))}
        </div>
      )}
      {rest.length > 0 && (
        <ul className={tiles.length ? "mt-2" : ""}>
          {rest.map((f) => (
            <FactRow key={f.fact_id} f={f} fresh={fresh.has(`f:${f.fact_id}`)} />
          ))}
        </ul>
      )}
    </div>
  );
}

const KIND_LABEL: Record<string, string> = {
  lab_report: "Laboratory report",
  ecg: "ECG report",
  xray: "X-ray report",
  ct: "CT report",
  prior_note: "Previous note",
  medication_list: "Medication list",
  image: "Image",
  document: "Document",
};

function flagTone(flag?: string) {
  const f = (flag || "").toUpperCase();
  if (!f || f === "N" || f === "NORMAL") return null;
  if (f.startsWith("C") || f === "HH" || f === "LL") return { bg: "#FDE7E7", fg: "#B4232C", word: f };
  if (f.startsWith("H")) return { bg: "#FDE7E7", fg: "#B4232C", word: "H" };
  if (f.startsWith("L")) return { bg: "#E3E9FF", fg: "#1F3FD1", word: "L" };
  return { bg: "#FFF1D6", fg: "#9A5B00", word: f };
}

function isLabRows(c: unknown): c is LabRow[] {
  return Array.isArray(c) && c.length > 0 && c.every((r) => r && typeof r === "object" && ("test" in r || "name" in r));
}

function LabTable({ rows }: { rows: LabRow[] }) {
  return (
    <div className="scroll-thin overflow-x-auto">
      <table className="w-full min-w-[360px] border-collapse text-left text-[12.5px]" data-testid="lab-table">
        <thead>
          <tr className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-3">
            <th className="border-b border-line py-1.5 pr-3 font-semibold">Test</th>
            <th className="border-b border-line py-1.5 pr-3 text-right font-semibold">Value</th>
            <th className="border-b border-line py-1.5 pr-3 font-semibold">Unit</th>
            <th className="border-b border-line py-1.5 pr-3 font-semibold">Reference range</th>
            <th className="border-b border-line py-1.5 font-semibold">Flag</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const t = flagTone(r.flag);
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const name = r.test ?? (r as any).name;
            return (
              <tr key={`${name}-${i}`} className={t ? "font-semibold" : ""} data-testid="lab-row">
                <td className="border-b border-line/70 py-1.5 pr-3 text-ink">{name}</td>
                <td className="tnum border-b border-line/70 py-1.5 pr-3 text-right" style={{ color: t ? t.fg : undefined }}>
                  {String(r.value ?? "")}
                </td>
                <td className="border-b border-line/70 py-1.5 pr-3 font-normal text-ink-2">{r.unit}</td>
                <td className="tnum border-b border-line/70 py-1.5 pr-3 font-normal text-ink-2">{r.ref_range}</td>
                <td className="border-b border-line/70 py-1.5">
                  {t ? (
                    <Tone bg={t.bg} fg={t.fg} title={t.word === "H" ? "Above the reference range" : t.word === "L" ? "Below the reference range" : "Flagged"}>
                      {t.word}
                    </Tone>
                  ) : (
                    <span className="text-[11px] font-normal text-ink-4">–</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ArtifactBody({ a }: { a: ChartArtifact }) {
  const c = a.content;
  if (isLabRows(c)) return <LabTable rows={c} />;
  if (Array.isArray(c)) {
    return (
      <ul className="list-disc space-y-1 pl-4 text-[13px] leading-snug text-ink">
        {c.map((x, i) => (
          <li key={i}>{typeof x === "string" ? x : Object.entries(x as Record<string, unknown>).map(([k, v]) => `${k}: ${String(v)}`).join(" · ")}</li>
        ))}
      </ul>
    );
  }
  if (c && typeof c === "object") {
    return (
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px]">
        {Object.entries(c as Record<string, unknown>).map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="font-semibold capitalize text-ink-2">{k.replace(/_/g, " ")}</dt>
            <dd className="text-ink">{typeof v === "string" || typeof v === "number" ? String(v) : JSON.stringify(v)}</dd>
          </div>
        ))}
      </dl>
    );
  }
  if (typeof c === "string" && c.trim()) {
    const mono = a.kind === "ecg";
    return <p className={`whitespace-pre-wrap text-[13px] leading-relaxed text-ink ${mono ? "tnum" : ""}`}>{c}</p>;
  }
  return <p className="text-[12px] text-ink-3">No content was authored for this item.</p>;
}

function ArtifactCard({ a, fresh }: { a: ChartArtifact; fresh: boolean }) {
  const img = a.asset && /\.(png|jpe?g|webp|gif|svg)$/i.test(a.asset) ? assetUrl(a.asset) : null;
  const report = ["ecg", "xray", "ct", "image"].includes(a.kind);
  return (
    <div className={`rounded-xl border border-line p-3 ${fresh ? "bg-[#FFF6D6] shadow-[0_0_0_2px_#F4D675]" : "bg-white/75"} transition-[background-color,box-shadow] duration-[1400ms]`} data-testid="artifact" data-kind={a.kind} data-artifact-id={a.artifact_id}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-[12.5px] font-semibold text-ink">{a.title}</span>
        <span className="sim-tag">{KIND_LABEL[a.kind] ?? a.kind}</span>
        {a.synthetic !== false && <span className="sim-tag">synthetic</span>}
        {fresh && <NewTag />}
        {a.turn ? <span className="tnum ml-auto text-[10.5px] font-medium text-ink-3">turn {a.turn}</span> : null}
      </div>
      {img && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={img} alt={a.title} className="mb-2 max-h-64 rounded-lg border border-line" />
      )}
      {report && <div className="eyebrow mb-1">Findings</div>}
      <ArtifactBody a={a} />
      {/* The author's interpretation is deliberately not shown during the encounter: reading the result is the learner's job. */}
    </div>
  );
}

function Section({ s, artifacts, fresh }: { s: ChartSection; artifacts: ChartArtifact[]; fresh: Set<string> }) {
  const isNew = fresh.has(`s:${s.section_id}`);
  const arts = artifacts.filter((a) => s.artifact_ids.includes(a.artifact_id));
  // a document that only repeats the section's static text is not rendered twice
  const text = s.static_text?.trim();
  const shownArts = arts.filter((a) => !(a.kind === "document" && typeof a.content === "string" && text && a.content.trim() === text));
  const plainDocs = s.section_id === "triage" ? shownArts.filter((a) => a.kind === "document" && typeof a.content === "string") : [];
  const cards = shownArts.filter((a) => !plainDocs.includes(a));
  const empty = !text && !s.facts.length && !s.notes.length && !shownArts.length;
  return (
    <section className={`rounded-2xl border border-line/80 bg-white/55 p-3 ${isNew ? "rise" : ""}`} data-testid="chart-section" data-section-id={s.section_id}>
      <div className="mb-1.5 flex items-center gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-2">{s.title}</h3>
        {isNew && <NewTag />}
      </div>
      {text && <p className="whitespace-pre-wrap px-2 text-[13px] leading-relaxed text-ink">{text}</p>}
      {plainDocs.map((a) => (
        <p key={a.artifact_id} className="whitespace-pre-wrap px-2 text-[13px] leading-relaxed text-ink">
          {a.content as string}
        </p>
      ))}
      {s.section_id === "vitals" ? (
        <VitalsGrid facts={s.facts} fresh={fresh} />
      ) : (
        s.facts.length > 0 && (
          <ul>
            {s.facts.map((f) => (
              <FactRow key={f.fact_id} f={f} fresh={fresh.has(`f:${f.fact_id}`)} />
            ))}
          </ul>
        )
      )}
      {s.notes.length > 0 && (
        <ul className="mt-1">
          {s.notes.map((n) => (
            <li key={n.note_id} className={`flex items-start gap-2 rounded-lg px-2 py-1.5 ${freshCls(fresh.has(`n:${n.note_id}`))}`} data-testid="chart-note">
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-ink-4" />
              <span className={`min-w-0 flex-1 text-[13px] italic leading-snug ${n.superseded ? "text-ink-3 line-through" : "text-ink-2"}`}>“{n.text}”</span>
              <span className="shrink-0 whitespace-nowrap pt-px text-[10.5px] font-medium text-ink-3" title="Recorded as the patient said it. It has not been verified.">
                {n.superseded ? "Superseded" : "Patient reports"}
                {n.turn ? ` · turn ${n.turn}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
      {cards.length > 0 && (
        <div className="mt-2 space-y-2">
          {cards.map((a) => (
            <ArtifactCard key={a.artifact_id} a={a} fresh={fresh.has(`a:${a.artifact_id}`)} />
          ))}
        </div>
      )}
      {empty && <p className="px-2 text-[12px] text-ink-3">Nothing recorded yet.</p>}
    </section>
  );
}

function resultWord(e: LedgerEvent): { word: string; bg: string; fg: string } {
  const r = e.result || "";
  if (e.kind === "start") return { word: "Chart opened", bg: "rgba(20,26,51,0.06)", fg: "#4A5275" };
  if (r.startsWith("finished")) return { word: "Finished", bg: "rgba(20,26,51,0.06)", fg: "#4A5275" };
  if (e.disclosed_fact_ids.length || e.released_artifact_ids.length) return { word: "Unlocked", bg: "#E3F4EA", fg: "#1F7A4D" };
  const map: Record<string, string> = {
    answered: "Answered, nothing new",
    repeat: "Already known",
    patient_does_not_know: "Patient does not know",
    not_specified: "Not in this case",
    no_fact_requested: "No finding asked for",
    not_available: "Not available",
    pending: "Result pending",
    already_available: "Already in the chart",
  };
  return { word: map[r] ?? (r || "–"), bg: "rgba(20,26,51,0.06)", fg: "#4A5275" };
}

function Ledger({ ledger, chart }: { ledger: LedgerEvent[]; chart: Chart }) {
  const factText = useMemo(() => {
    const m = new Map<string, string>();
    chart.sections.forEach((s) => s.facts.forEach((f) => m.set(f.fact_id, f.text)));
    return m;
  }, [chart]);
  const artTitle = useMemo(() => new Map(chart.artifacts.map((a) => [a.artifact_id, a.title])), [chart]);
  const rows = [...ledger].sort((a, b) => a.seq - b.seq);
  const unlocked = rows.reduce((n, e) => n + e.disclosed_fact_ids.length + e.released_artifact_ids.length, 0);
  return (
    <div data-testid="ledger">
      <p className="mb-3 text-[12px] leading-relaxed text-ink-2">
        Every chart entry is released by a rule the case author set, and each release is recorded here with the question or request that triggered it.{" "}
        <span className="tnum font-semibold text-ink">{unlocked}</span> item{unlocked === 1 ? "" : "s"} unlocked so far.
      </p>
      <ol className="space-y-2">
        {rows.map((e) => {
          const w = resultWord(e);
          const what = e.kind === "start" ? "Encounter started" : e.kind === "request" ? `Requested: ${requestLabel(e.request || "")}` : e.kind === "finish" ? "Encounter finished" : e.text;
          return (
            <li key={e.seq} className="rounded-xl border border-line/80 bg-white/60 p-2.5" data-testid="ledger-row" data-kind={e.kind}>
              <div className="flex items-start gap-2">
                <span className="tnum mt-px inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-[#141a33]/[0.06] px-1 text-[10.5px] font-semibold text-ink-2" title={`Turn ${e.turn}`}>
                  {e.turn}
                </span>
                <span className={`min-w-0 flex-1 text-[12.5px] leading-snug ${e.kind === "turn" ? "text-ink" : "font-medium text-ink-2"}`}>{e.kind === "turn" ? `“${what}”` : what}</span>
                <Tone bg={w.bg} fg={w.fg}>
                  {w.word}
                </Tone>
              </div>
              {(e.disclosed_fact_ids.length > 0 || e.released_artifact_ids.length > 0) && (
                <ul className="mt-2 space-y-1 border-l-2 border-[#BFE5CF] pl-2.5">
                  {e.disclosed_fact_ids.map((id) => {
                    const rule = e.rule_fired[id];
                    const t = RULE_TONE[rule] ?? RULE_TONE.chart_initial;
                    return (
                      <li key={id} className="flex flex-wrap items-start gap-x-2 gap-y-1 text-[12.5px] leading-snug text-ink" data-testid="ledger-unlock" data-rule={rule}>
                        <span className="min-w-0 flex-1 basis-48">{factText.get(id) ?? id}</span>
                        <Tone bg={t.bg} fg={t.fg} title={`Rule: ${rule}`}>
                          {RULE_LABEL[rule] ?? rule ?? "rule"}
                        </Tone>
                      </li>
                    );
                  })}
                  {e.released_artifact_ids.map((id) => (
                    <li key={id} className="flex flex-wrap items-start gap-x-2 gap-y-1 text-[12.5px] leading-snug text-ink" data-testid="ledger-unlock" data-rule="artifact">
                      <span className="min-w-0 flex-1 basis-48">{artTitle.get(id) ?? id}</span>
                      <Tone bg={RULE_TONE.on_request.bg} fg={RULE_TONE.on_request.fg}>
                        {e.kind === "start" ? "Document · in the chart from the start" : "Document released"}
                      </Tone>
                    </li>
                  ))}
                </ul>
              )}
              {(e.rapport_delta ?? 0) !== 0 && (
                <div className="mt-1.5 text-[11px] text-ink-3">
                  Rapport {e.rapport_delta! > 0 ? "+" : ""}
                  {e.rapport_delta}
                  {e.rapport_reasons?.length ? ` (${e.rapport_reasons.map((r) => r.replace(/_/g, " ")).join(", ")})` : ""}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function ChartPane({ kase, patient, chart, ledger, simLine }: { kase: LearnerCase; patient: PatientView; chart: Chart; ledger: LedgerEvent[]; simLine?: string | null }) {
  const [tab, setTab] = useState<"chart" | "ledger">("chart");
  const fresh = useFresh(chart);
  const visible = chart.sections.filter((s) => s.visible);
  const hidden = chart.hidden_section_count ?? chart.sections.filter((s) => !s.visible).length;
  const pending = (chart.pending_results ?? []) as unknown[];
  const unlocked = ledger.reduce((n, e) => n + (e.kind === "start" ? 0 : e.disclosed_fact_ids.length + e.released_artifact_ids.length), 0);
  return (
    <div className="glass flex h-full min-h-0 flex-col overflow-hidden" data-testid="chart-pane">
      {/* identity banner */}
      <div className="border-b border-line bg-white/50 px-4 py-3">
        <div className="flex items-center gap-3">
          <Avatar name={patient.name} image={patient.image} size={44} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="truncate text-[16px] font-semibold tracking-[-0.01em] text-ink" data-testid="chart-patient-name">
                {patient.name ?? "Patient"}
              </span>
              <span className="tnum text-[12.5px] font-medium text-ink-2">
                {patient.age != null ? `${patient.age} y` : ""}
                {patient.gender ? ` · ${genderWord(patient.gender)}` : ""}
              </span>
            </div>
            <div className="mt-0.5 truncate text-[11.5px] text-ink-3">
              {simLine || kase.setting || "Encounter"}
              {kase.learner_role ? ` · You are the ${kase.learner_role.toLowerCase()}` : ""}
            </div>
          </div>
        </div>
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          <div className="seg" role="tablist">
            <button role="tab" aria-selected={tab === "chart"} data-on={tab === "chart"} onClick={() => setTab("chart")} data-testid="tab-chart">
              Chart
            </button>
            <button role="tab" aria-selected={tab === "ledger"} data-on={tab === "ledger"} onClick={() => setTab("ledger")} data-testid="tab-ledger">
              Disclosure ledger{unlocked ? ` · ${unlocked}` : ""}
            </button>
          </div>
          <span className="ml-auto">
            <SyntheticLabel compact />
          </span>
        </div>
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto p-3">
        {tab === "chart" ? (
          <div className="space-y-2.5">
            {visible.map((s) => (
              <Section key={s.section_id} s={s} artifacts={chart.artifacts} fresh={fresh} />
            ))}
            {pending.length > 0 && (
              <div className="rounded-2xl border border-dashed border-[#E9C46A] bg-[#FFF8E6] px-3 py-2 text-[12px] font-medium text-[#8A5200]">
                {pending.length} result{pending.length === 1 ? "" : "s"} pending. They appear here when ready.
              </div>
            )}
            {hidden > 0 && (
              <div className="flex items-center gap-2 rounded-2xl border border-dashed border-ink-4/60 px-3 py-2.5 text-[12px] text-ink-3" data-testid="hidden-sections">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M6 11V8a6 6 0 0 1 12 0v3M5 11h14v9H5z" />
                </svg>
                <span>
                  <span className="tnum font-semibold text-ink-2">{hidden}</span> more section{hidden === 1 ? "" : "s"} will open as you take the history, examine the patient and request tests.
                </span>
              </div>
            )}
          </div>
        ) : (
          <Ledger ledger={ledger} chart={chart} />
        )}
      </div>
    </div>
  );
}
