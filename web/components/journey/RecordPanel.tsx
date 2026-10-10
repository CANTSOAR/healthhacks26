"use client";
// The shared record: one list for the whole journey. Every entry carries its provenance chips (role, who played it,
// stage and turn, source). Conflicts are shown first, with both sides and both provenances.
import { useMemo, useState } from "react";
import { ACTOR_LABEL, KIND_LABEL, roleTone } from "@/lib/journey/api";
import type { By, Discrepancy, Provenance, RecordEntry, SharedRecord, Stage } from "@/lib/journey/types";
import { Tone } from "@/components/encounter/ui";

export function RoleChip({ by, compact = false }: { by: By; compact?: boolean }) {
  const t = roleTone(by.staff_role);
  const actor = by.actor === "human" ? "you" : by.actor === "sampled" ? "sampled" : by.actor === "sim" ? "simulation" : "AI";
  return (
    <Tone bg={t.bg} fg={t.fg} title={`${by.role_label}${by.name ? `, ${by.name}` : ""} (${ACTOR_LABEL[by.actor] ?? by.actor})`}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: t.fg }} />
      {by.role_label}
      {!compact && <span className="font-medium opacity-70">· {actor}</span>}
    </Tone>
  );
}

export function ProvenanceChips({ p, sourceLabel }: { p: Provenance; sourceLabel?: string }) {
  const src = sourceLabel ?? p.source.replace(/_/g, " ");
  return (
    <span className="flex flex-wrap items-center gap-1" data-testid="provenance">
      <RoleChip by={p.by} />
      <Tone bg="rgba(20,26,51,0.05)" fg="#4A5275" title="Stage and turn in which this was added">
        {p.stage_title}
        {p.turn ? ` · turn ${p.turn}` : ""}
      </Tone>
      <Tone bg="rgba(20,26,51,0.05)" fg="#4A5275" title="Where the information came from">
        {src}
      </Tone>
    </span>
  );
}

function Side({ p }: { p: Provenance }) {
  return (
    <div className="rounded-lg bg-white/80 p-2">
      <div className="text-[12px] leading-snug text-ink">{p.kind === "patient_report" ? `“${p.text}”` : p.text}</div>
      <div className="mt-1.5">
        <ProvenanceChips p={p} />
      </div>
    </div>
  );
}

export function DiscrepancyCard({ d }: { d: Discrepancy }) {
  const open = !d.resolved;
  return (
    <div className="rounded-xl border p-2.5" style={{ background: open ? "#FFF6E0" : "#EEF7F1", borderColor: open ? "#F1D58A" : "#BFE3CC" }} data-testid="discrepancy" data-resolved={d.resolved}>
      <div className="flex items-start gap-2">
        <span className="chip mt-px" style={{ background: open ? "#F6C445" : "#2FA36B", color: open ? "#4A3500" : "#fff" }}>
          {open ? "Conflict" : "Settled"}
        </span>
        <div className="text-[12px] font-semibold leading-snug" style={{ color: open ? "#6B4A00" : "#1F6B45" }}>
          {d.note}
        </div>
      </div>
      <div className="mt-2 grid gap-1.5">
        {d.entries.map((p) => (
          <Side key={p.entry_id} p={p} />
        ))}
      </div>
      <div className="mt-1.5 text-[10.5px] leading-snug text-ink-3">Flagged because {d.basis.replace(/^authored: /, "")}.</div>
    </div>
  );
}

function Entry({ e, fresh, stages }: { e: RecordEntry; fresh: boolean; stages: Stage[] }) {
  const conflict = !!e.discrepancy_ids?.length && e.status === "disputed";
  const unsupported = e.status === "unsupported";
  const title = (id: string) => stages.find((s) => s.stage_id === id)?.title ?? id;
  return (
    <li
      className={`rounded-xl border p-2.5 ${fresh ? "rise" : ""}`}
      style={{ background: unsupported ? "#FDECEC" : conflict ? "#FFF6E0" : "rgba(255,255,255,0.72)", borderColor: unsupported ? "#F5C2C5" : conflict ? "#F1D58A" : "rgba(20,26,51,0.08)" }}
      data-testid="record-entry"
      data-kind={e.kind}
      data-status={e.status}
    >
      <div className="flex items-start gap-2">
        <span className="mt-[1px] shrink-0 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-3">{e.kind === "handoff" ? (e.element_label ?? "Handoff") : (KIND_LABEL[e.kind] ?? e.kind)}</span>
        {e.status === "superseded" && <span className="chip" style={{ background: "rgba(20,26,51,0.06)", color: "#4A5275" }}>later corrected</span>}
        {conflict && <span className="chip" style={{ background: "#F6C445", color: "#4A3500" }}>in conflict</span>}
        {unsupported && <span className="chip" style={{ background: "#E5484D", color: "#fff" }}>not supported by the record</span>}
        {e.order_status && e.kind === "order" && <span className="chip" style={{ background: e.order_status === "resulted" ? "#E3F4EA" : "#FFF1D6", color: e.order_status === "resulted" ? "#1F7A4D" : "#8A5200" }}>{e.order_status}</span>}
      </div>
      <div className={`mt-1 text-[12.5px] leading-snug text-ink ${e.status === "superseded" ? "line-through decoration-ink-4" : ""}`}>{e.kind === "patient_report" ? `“${e.text}”` : e.text}</div>
      {e.unsupported?.map((u, i) => (
        <div key={i} className="mt-1 text-[11px] leading-snug" style={{ color: "#8E1B23" }}>
          “{u.quote}”: {u.reason}.
        </div>
      ))}
      <div className="mt-1.5">
        <ProvenanceChips p={e} sourceLabel={e.source_label} />
      </div>
      {e.quote && e.by.actor === "human" && <div className="mt-1 truncate text-[10.5px] italic text-ink-3">asked: “{e.quote}”</div>}
      {e.used_in.length > 0 && (
        <div className="mt-1 text-[10.5px] font-medium leading-snug" style={{ color: "#1F6B45" }} data-testid="used-in">
          ↳ {e.used_in.map((u) => `${title(u.stage_id)}: ${u.how}`).join(" · ")}
        </div>
      )}
    </li>
  );
}

export function RecordPanel({ record, stages, fresh }: { record: SharedRecord; stages: Stage[]; fresh: Set<string> }) {
  const [filter, setFilter] = useState<string>("all");
  const groups = useMemo(() => {
    const list = record.entries.filter((e) => filter === "all" || e.stage_id === filter);
    const by = new Map<string, RecordEntry[]>();
    for (const e of list) by.set(e.stage_id, [...(by.get(e.stage_id) ?? []), e]);
    return [...by.entries()];
  }, [record.entries, filter]);
  const used = stages.filter((s) => record.entries.some((e) => e.stage_id === s.stage_id));
  const open = record.discrepancies.filter((d) => !d.resolved);
  const settled = record.discrepancies.filter((d) => d.resolved);
  return (
    <aside className="glass flex h-full min-h-0 flex-col overflow-hidden" data-testid="record-panel" aria-label="Shared record">
      <div className="shrink-0 border-b border-line px-3.5 pb-2.5 pt-3">
        <div className="flex items-baseline justify-between gap-2">
          <div>
            <div className="eyebrow">One patient, one record</div>
            <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">Shared record</h2>
          </div>
          <div className="tnum text-[11px] font-semibold text-ink-3" data-testid="record-count">
            {record.entries.length} {record.entries.length === 1 ? "entry" : "entries"}
            {record.n_unresolved ? <span style={{ color: "#9A5B00" }}> · {record.n_unresolved} open conflict{record.n_unresolved > 1 ? "s" : ""}</span> : null}
          </div>
        </div>
        {used.length > 1 && (
          <div className="scroll-thin mt-2 flex gap-1 overflow-x-auto">
            {[{ stage_id: "all", title: "All stages" }, ...used].map((s) => (
              <button key={s.stage_id} onClick={() => setFilter(s.stage_id)} className="chip shrink-0 transition-colors" style={filter === s.stage_id ? { background: "#2F55F5", color: "#fff" } : { background: "rgba(20,26,51,0.05)", color: "#4A5275" }}>
                {s.title}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {record.entries.length === 0 ? (
          <p className="px-1 text-[12.5px] leading-relaxed text-ink-3">Nothing has been recorded yet. Whatever each role learns, orders or decides is written here with who added it, in which stage, and where it came from. Later stages start from this record, not from the case.</p>
        ) : (
          <>
            {(open.length > 0 || settled.length > 0) && (
              <div className="mb-3 grid gap-2">
                {[...open, ...settled].map((d) => (
                  <DiscrepancyCard key={d.discrepancy_id} d={d} />
                ))}
              </div>
            )}
            {groups.map(([sid, list]) => (
              <section key={sid} className="mb-3">
                <div className="mb-1.5 flex items-center gap-2 px-0.5">
                  <span className="text-[11px] font-semibold text-ink-2">{list[0].stage_title}</span>
                  <span className="h-px flex-1 bg-line" />
                  <RoleChip by={list[0].by} />
                </div>
                <ol className="grid gap-1.5">
                  {list.map((e) => (
                    <Entry key={e.entry_id} e={e} fresh={fresh.has(e.entry_id)} stages={stages} />
                  ))}
                </ol>
              </section>
            ))}
          </>
        )}
      </div>
    </aside>
  );
}
