"use client";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { describe, enumsOf, roomState } from "@/lib/describe";
import type { FeedState } from "@/lib/feed";
import { duration, formatValue, L, patientId, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { ACUITY, ACUITY_LABEL } from "@/lib/palette";
import { useUI } from "@/lib/ui";
import type { CatalogAttribute, Selection } from "@/lib/types";
import { Icon, ICONS, SimTag, SourceChip } from "./atoms";

function Row({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-[3px] text-[12px]">
      <span className="shrink-0 text-ink-3">{k}</span>
      <span className="tnum min-w-0 text-right font-medium text-ink">{children}</span>
    </div>
  );
}
const isUrl = (s?: string) => !!s && /^https?:\/\//.test(s);

function EntityLink({ sel, children }: { sel: Selection; children: ReactNode }) {
  const select = useUI((s) => s.select);
  return (
    <button className="font-semibold text-accent-dark underline decoration-accent/30 underline-offset-2 hover:decoration-accent" onClick={() => select(sel)}>
      {children}
    </button>
  );
}

function LiveState({ sel, f }: { sel: Selection; f: FeedState }) {
  const e = enumsOf(f);
  const snap = f.snap;
  const layout = f.layout;
  const d = describe(sel, f);
  if (!d) return <div className="text-[12px] text-ink-3">Not part of the current layout.</div>;
  const i = d.index;
  if (sel.kind === "patient") {
    if (!snap || i < 0) return <div className="text-[12px] text-ink-3">This patient is not in the hospital at this moment in the recording.</div>;
    const p = snap.patients;
    const room = layout?.rooms[p.room[i]];
    const staffIdx = p.staff?.[i] ?? -1;
    const flags = [p.flags[i] & 1 && "deteriorated", p.flags[i] & 2 && "admit decision", p.flags[i] & 4 && "fast track", p.flags[i] & 8 && "played encounter"].filter(Boolean) as string[];
    return (
      <>
        <Row k="Acuity">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: ACUITY[p.acuity[i]] }} />
            {ACUITY_LABEL[p.acuity[i]]}
          </span>
        </Row>
        <Row k="Presenting group">{L.condition(e, p.condition[i])}</Row>
        <Row k="State">{L.patientState(e, p.state[i])}</Row>
        <Row k="In this state">{duration(p.state_min[i])}</Row>
        <Row k="Since arrival">{duration(p.age_min[i])}</Row>
        <Row k="Where">{room ? <EntityLink sel={{ kind: "room", id: room.id, feed: f.key }}>{room.label}</EntityLink> : "–"}</Row>
        {staffIdx >= 0 && snap.staff.id[staffIdx] ? (
          <Row k="With">
            <EntityLink sel={{ kind: "staff", id: snap.staff.id[staffIdx], feed: f.key }}>{snap.staff.id[staffIdx]}</EntityLink>
          </Row>
        ) : null}
        <Row k="Arrived by">{L.arrival(e, p.arrival_mode[i])}</Row>
        <Row k="Age band">{L.ageBand(e, p.age_band[i])}</Row>
        {p.payer ? <Row k="Payer">{titleCase(L.payer(e, p.payer[i]))}</Row> : null}
        {p.exit[i] > 0 ? <Row k="Outcome">{L.exit(e, p.exit[i])}</Row> : null}
        {flags.length ? <Row k="Flags">{flags.join(" · ")}</Row> : null}
      </>
    );
  }
  if (sel.kind === "staff") {
    if (!snap || i < 0) return <div className="text-[12px] text-ink-3">Not on shift at this moment.</div>;
    const s = snap.staff;
    const room = layout?.rooms[s.room[i]];
    const pid = s.patient?.[i] ?? -1;
    return (
      <>
        <Row k="Role">{L.role(e, s.role[i])}</Row>
        <Row k="State">{L.staffState(e, s.state[i])}</Row>
        <Row k="Where">{room ? <EntityLink sel={{ kind: "room", id: room.id, feed: f.key }}>{room.label}</EntityLink> : "–"}</Row>
        {pid >= 0 ? (
          <Row k="Serving">
            <EntityLink sel={{ kind: "patient", id: pid, feed: f.key }}>{patientId(pid)}</EntityLink>
          </Row>
        ) : null}
        {s.fatigue?.[i] != null ? <Row k="Fatigue index">{`${Math.round(s.fatigue[i] * 100)}%`}</Row> : null}
        <div className="pt-1 text-[10.5px] text-ink-3">Staff are fictional.</div>
      </>
    );
  }
  if (sel.kind === "room") {
    const r = layout?.rooms[i];
    if (!r) return null;
    const occupants: number[] = [];
    if (snap) snap.patients.room.forEach((ri, k) => ri === i && e.patient_state[snap.patients.state[k]] !== "exited" && occupants.push(k));
    const rs = roomState(f, i);
    const staffHere: string[] = [];
    if (snap) snap.staff.room.forEach((ri, k) => ri === i && staffHere.push(snap.staff.id[k]));
    return (
      <>
        {snap ? (
          <Row k="Status">
            {rs.held && rs.holder ? (
              <>
                Held ·{" "}
                <EntityLink sel={{ kind: "patient", id: snap.patients.id[rs.holder.patientIdx], feed: f.key }}>{patientId(snap.patients.id[rs.holder.patientIdx])}</EntityLink> at {rs.holder.where}
              </>
            ) : (
              rs.text
            )}
          </Row>
        ) : null}
        <Row k={rs.held ? "In the room now" : "Occupancy"}>{`${snap?.rooms.occupancy[i] ?? 0} of ${r.capacity}`}</Row>
        {rs.held && <div className="pb-1 text-right text-[10.5px] text-ink-3">The bay stays assigned while its patient is away for a test.</div>}
        {snap?.rooms.queue?.[i] ? <Row k="Queue">{snap.rooms.queue[i]}</Row> : null}
        <Row k="Size">{`${+r.w.toFixed(1)} × ${+r.d.toFixed(1)} m`}</Row>
        {occupants.length > 0 && snap ? (
          <Row k={occupants.length > 1 ? "Patients" : "Patient"}>
            <span className="flex flex-wrap justify-end gap-x-2 gap-y-0.5">
              {occupants.slice(0, 8).map((k) => (
                <EntityLink key={k} sel={{ kind: "patient", id: snap.patients.id[k], feed: f.key }}>
                  {patientId(snap.patients.id[k])}
                </EntityLink>
              ))}
              {occupants.length > 8 ? <span className="text-ink-3">+{occupants.length - 8}</span> : null}
            </span>
          </Row>
        ) : null}
        {staffHere.length > 0 ? (
          <Row k="Staff here">
            <span className="flex flex-wrap justify-end gap-x-2 gap-y-0.5">
              {staffHere.slice(0, 6).map((id) => (
                <EntityLink key={id} sel={{ kind: "staff", id, feed: f.key }}>
                  {id}
                </EntityLink>
              ))}
            </span>
          </Row>
        ) : null}
        <div className="mt-2 rounded-xl bg-[#141a33]/[0.035] p-2.5">
          <div className="mb-1 flex items-center gap-2">
            <span className="eyebrow">Layout provenance</span>
            <SourceChip tag={r.provenance} title="surveyed = from a real plan · published = a count or zone the hospital has stated · inferred = placed to be consistent with those" />
          </div>
          <div className="break-words text-[11px] leading-snug text-ink-2">
            {isUrl(r.source) ? (
              <a href={r.source} target="_blank" rel="noreferrer" className="text-accent-dark underline decoration-accent/30 underline-offset-2">
                {r.source}
              </a>
            ) : (
              (r.source ?? "No source recorded for this room.")
            )}
          </div>
          {r.note ? <div className="mt-1 text-[11px] leading-snug text-ink-3">{r.note}</div> : null}
        </div>
      </>
    );
  }
  if (sel.kind === "equipment") {
    const q = layout?.equipment[i];
    if (!q) return null;
    const room = layout?.rooms.find((r) => r.id === q.room);
    return (
      <>
        {snap ? <Row k="Status">{L.equipStatus(e, snap.equipment.status[i])}</Row> : null}
        <Row k="Type">{titleCase(q.type)}</Row>
        <Row k="Room">{room ? <EntityLink sel={{ kind: "room", id: room.id, feed: f.key }}>{room.label}</EntityLink> : q.room}</Row>
        <div className="mt-2 rounded-xl bg-[#141a33]/[0.035] p-2.5">
          <div className="mb-1 flex items-center gap-2">
            <span className="eyebrow">Layout provenance</span>
            <SourceChip tag={q.provenance} />
          </div>
          <div className="break-words text-[11px] leading-snug text-ink-2">{q.source ?? "No source recorded."}</div>
        </div>
      </>
    );
  }
  const a = snap?.ambulances?.[i];
  return a ? (
    <>
      <Row k="State">{titleCase(a.state)}</Row>
      <Row k="Position">{`${a.x.toFixed(0)} m east, ${a.z.toFixed(0)} m south`}</Row>
    </>
  ) : (
    <div className="text-[12px] text-ink-3">This ambulance has left the site.</div>
  );
}

function Attribute({ name, a }: { name: string; a: CatalogAttribute }) {
  const [open, setOpen] = useState(false);
  const dist = a.dist ? `${a.dist.kind}${a.dist.mean != null ? ` · mean ${a.dist.mean}` : ""}${a.dist.cv != null ? ` · cv ${a.dist.cv}` : ""}${a.dist.low != null ? ` · ${a.dist.low}–${a.dist.high}` : ""}` : null;
  return (
    <div className="border-t border-line py-2 first:border-t-0">
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 break-words text-[12px] font-semibold text-ink">{titleCase(name)}</span>
        <span className="flex shrink-0 items-center gap-1">
          {a.mixed_provenance && (
            <span className="chip bg-[#FDE7E8] text-[#B4232A]" title={a.mixed_provenance}>
              mixed
            </span>
          )}
          <SourceChip tag={a.source} />
        </span>
      </div>
      <div className="mt-0.5 flex items-baseline gap-1.5">
        <span className="tnum min-w-0 break-words text-[12px] text-ink">{formatValue(a.value)}</span>
        <span className="shrink-0 text-[11px] text-ink-3">{a.unit}</span>
      </div>
      {dist && <div className="tnum mt-0.5 text-[11px] text-ink-2">Distribution: {dist}</div>}
      {a.index && <div className="mt-0.5 text-[11px] text-ink-3">Indexed by {a.index.replace(/_/g, " ")}</div>}
      {a.range && <div className="tnum mt-0.5 text-[11px] text-ink-3">Plausible range {formatValue(a.range)}</div>}
      {a.mixed_provenance && <div className="mt-1 rounded-lg bg-[#FDF6E7] px-2 py-1.5 text-[11px] leading-snug text-[#8A5A00]">Mixed provenance: {a.mixed_provenance.replace(/^PER-ELEMENT PROVENANCE[^:]*:\s*/i, "")}</div>}
      {a.validation_only && <div className="mt-0.5 text-[11px] text-ink-3">Validation target only, never a simulator input.</div>}
      {(a.citation || a.url || a.note || a.file) && (
        <div className={`mt-1 text-[11px] leading-snug text-ink-3 ${open ? "" : "line-clamp-2"}`} onClick={() => setOpen((o) => !o)} role="button" title="Click to expand">
          {a.citation}
          {a.note ? ` ${a.note}` : ""}
          {a.file ? ` (${a.file})` : ""}
        </div>
      )}
      {isUrl(a.url) && (
        <a href={a.url} target="_blank" rel="noreferrer" className="mt-1 inline-flex max-w-full items-center gap-1 text-[11px] font-medium text-accent-dark hover:underline">
          <Icon d={ICONS.link} size={11} />
          <span className="truncate">{a.url!.replace(/^https?:\/\//, "")}</span>
        </a>
      )}
    </div>
  );
}

const SHARED_LABEL: Record<string, string> = { space: "all spaces", staff: "all staff", patient: "all patients", equipment: "all equipment", event: "all events" };

function Catalog({ refPath }: { refPath: string }) {
  const { data, source, loading } = useApi(() => api.catalogRef(refPath), [refPath]);
  const entityType = data?.entity_type ?? refPath.split("/")[0];
  const shared = useApi(async () => ({ data: await api.catalogSharedKeys(entityType), source: "live" as const }), [entityType]);
  const [open, setOpen] = useState(false);
  const sharedSet = new Set(shared.data ?? []);
  const attrs = data ? Object.entries(data.attributes ?? {}) : [];
  // the variant's own attributes first; parameters shared by every variant of the entity type go in a collapsed group
  const own = attrs.filter(([k]) => !sharedSet.has(k));
  const common = attrs.filter(([k]) => sharedSet.has(k));
  const counts = attrs.reduce<Record<string, number>>((m, [, a]) => ((m[a.source] = (m[a.source] ?? 0) + 1), m), {});
  return (
    <div data-testid="catalog">
      <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="eyebrow">Catalog definition</span>
        <code className="rounded bg-[#141a33]/[0.05] px-1.5 py-[1px] text-[10.5px] text-ink-2">{refPath}</code>
        {source === "fixture" && <SourceChip tag="fixture" title="Read from the bundled copy of catalog/*.yaml because the server is unreachable" />}
      </div>
      {loading && <div className="py-3 text-[12px] text-ink-3">Loading…</div>}
      {!loading && !data && <div className="py-2 text-[12px] text-ink-3">No catalog entry for this reference.</div>}
      {data && (
        <>
          <div className="mb-1 text-[11px] text-ink-3">
            {data.label} · {attrs.length} attributes
            {(["measured", "literature", "assumed"] as const).map((k) => (counts[k] ? ` · ${counts[k]} ${k}` : "")).join("")}
          </div>
          <div data-testid="catalog-own">
            {own.map(([k, a]) => (
              <Attribute key={k} name={k} a={a} />
            ))}
            {own.length === 0 && <div className="py-1 text-[11px] text-ink-3">This variant has no attributes of its own.</div>}
          </div>
          {common.length > 0 && (
            <div className="mt-1 border-t border-line">
              <button className="flex w-full items-center gap-2 py-2 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open} data-testid="catalog-shared-toggle">
                <span className={`text-ink-3 transition-transform ${open ? "rotate-90" : ""}`}>
                  <Icon d={ICONS.chevron} size={12} stroke={2.4} />
                </span>
                <span className="text-[12px] font-semibold text-ink">Shared parameters ({SHARED_LABEL[entityType] ?? `all ${entityType} variants`})</span>
                <span className="tnum ml-auto text-[10.5px] text-ink-3">{common.length}</span>
              </button>
              {open && (
                <div data-testid="catalog-shared">
                  {common.map(([k, a]) => (
                    <Attribute key={k} name={k} a={a} />
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SimDetail({ sel, f }: { sel: Selection; f: FeedState }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const runId = f.header?.live ? f.header.id : null;
  useEffect(() => {
    setData(null);
    if (!runId || (sel.kind !== "patient" && sel.kind !== "staff")) return;
    let dead = false;
    const p = sel.kind === "patient" ? api.runPatient(runId, Number(sel.id)) : api.runStaff(runId, String(sel.id));
    p.then((d) => !dead && setData(d)).catch(() => undefined);
    return () => {
      dead = true;
    };
  }, [runId, sel.kind, sel.id]);
  if (!data) return null;
  const known = (data.known_state ?? data.profile ?? null) as Record<string, unknown> | null;
  const inter = Array.isArray(data.interactions) ? (data.interactions as Record<string, unknown>[]) : [];
  if (!known && !inter.length) return null;
  return (
    <div className="mt-3 border-t border-line pt-3">
      <div className="eyebrow mb-1">From the simulator</div>
      {known && Object.entries(known).slice(0, 14).map(([k, v]) => <Row key={k} k={titleCase(k)}>{formatValue(v)}</Row>)}
      {inter.length > 0 && <div className="mt-1 text-[11px] text-ink-3">{inter.length} interactions recorded for this run.</div>}
    </div>
  );
}

export function Inspector({ f, className = "" }: { f: FeedState; className?: string }) {
  const sel = useUI((s) => s.selection);
  const select = useUI((s) => s.select);
  if (!sel || sel.feed !== f.key) return null;
  const d = describe(sel, f);
  const runId = f.header?.id ?? "";
  return (
    <div className={`glass slidein pointer-events-auto flex min-h-0 flex-col ${className}`} data-testid="inspector">
      <div className="flex items-start gap-2 px-4 pb-2 pt-3.5">
        <div className="min-w-0 flex-1">
          <div className="eyebrow">{sel.kind === "room" ? "Space" : titleCase(sel.kind)}</div>
          <div className="truncate text-[17px] font-semibold tracking-[-0.01em] text-ink">{d?.title ?? String(sel.id)}</div>
          <div className="truncate text-[12px] text-ink-3">{d?.sub}</div>
        </div>
        <button aria-label="Close inspector" className="-mr-1.5 flex h-7 w-7 items-center justify-center rounded-full text-ink-3 hover:bg-accent-soft hover:text-accent-dark" onClick={() => select(null)}>
          <Icon d={ICONS.close} size={14} stroke={2.2} />
        </button>
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 pb-4">
        {sel.kind === "patient" && (
          <Link
            href={`/encounter?run_id=${encodeURIComponent(runId)}&patient_id=${encodeURIComponent(String(sel.id))}`}
            className="btn-primary mb-3 w-full"
            data-testid="play-encounter"
            title="Step into the clinician's role for this patient"
          >
            <Icon d={ICONS.play} size={12} stroke={2.4} />
            Play this encounter
          </Link>
        )}
        <div className="mb-1 flex items-center gap-2">
          <span className="eyebrow">Live state</span>
          <SimTag>{f.origin === "fixture" ? "fixture" : "simulated"}</SimTag>
        </div>
        <LiveState sel={sel} f={f} />
        <SimDetail sel={sel} f={f} />
        {d?.catalogRef ? (
          <div className="mt-3 border-t border-line pt-3">
            <Catalog refPath={d.catalogRef} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
