"use client";
import { useEffect, useMemo, useRef } from "react";
import { enumsOf, roomState } from "@/lib/describe";
import type { FeedState } from "@/lib/feed";
import { duration, L, patientId } from "@/lib/format";
import { ACUITY, roleColor } from "@/lib/palette";
import { isPlayable } from "@/lib/session";
import { useUI, type ListTab } from "@/lib/ui";
import type { Selection } from "@/lib/types";
import { BED_TYPES } from "../scene/build";
import { Bar, SimTag } from "./atoms";

const STATUS_STYLE: Record<string, [string, string]> = {
  occupied: ["#E3E9FF", "#1F3FD1"],
  open_empty: ["#DFF5EA", "#11734B"],
  cleaning: ["#FDEFD8", "#8A5A00"],
  closed: ["#ECEEF6", "#4A5275"],
  out_of_service: ["#FDE7E8", "#B4232A"],
  busy: ["#E3E9FF", "#1F3FD1"],
  idle: ["#DFF5EA", "#11734B"],
  walking: ["#ECEEF6", "#4A5275"],
  on_break: ["#FDEFD8", "#8A5A00"],
  off_shift: ["#ECEEF6", "#8089A8"],
};
const WAIT_STATES = new Set(["waiting_triage", "waiting_bay", "waiting_provider", "waiting_test", "waiting_results", "boarding"]);

interface Row {
  sel: Selection;
  title: string;
  dot?: string;
  sub: string;
  chip: string;
  chipKey: string;
  bar: number;
  barColor?: string;
  right: string;
  /** sort key (lower first) and a marker for patients whose encounter can be played now */
  rank?: number;
  playable?: boolean;
}
const MAX_ROWS = 160;
const natural = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true });

function rows(f: FeedState, tab: ListTab): { rows: Row[]; total: number } {
  const e = enumsOf(f);
  const snap = f.snap;
  const layout = f.layout;
  const out: Row[] = [];
  if (!layout) return { rows: out, total: 0 };
  if (tab === "beds") {
    const occupant = new Map<number, number>();
    if (snap) snap.patients.room.forEach((r, i) => !occupant.has(r) && e.patient_state[snap.patients.state[i]] !== "exited" && occupant.set(r, i));
    layout.rooms.forEach((r, i) => {
      if (!BED_TYPES.has(r.type) || r.physical === false) return;
      const st = e.room_status[snap?.rooms.status[i] ?? -1] ?? "open_empty";
      if (r.capacity > 1) {
        const occ = snap?.rooms.occupancy[i] ?? 0;
        out.push({ sel: { kind: "room", id: r.id, feed: f.key }, title: r.label, sub: `${r.zone ?? L.roomType(r.type)}`, chip: occ > r.capacity ? `${occ} (layout shows ${r.capacity})` : `${occ} / ${r.capacity}`, chipKey: occ > r.capacity ? "out_of_service" : occ ? "occupied" : "open_empty", bar: occ / Math.max(1, r.capacity), right: "beds in use" });
        return;
      }
      const pi = occupant.get(i);
      const rs = roomState(f, i);
      const p = snap?.patients;
      out.push({
        sel: { kind: "room", id: r.id, feed: f.key },
        title: r.label,
        dot: pi != null && p ? ACUITY[p.acuity[pi]] : undefined,
        sub: pi != null && p ? L.patientState(e, p.state[pi]) : rs.held ? rs.text.replace(/^Held · /, "") : (r.zone ?? L.roomType(r.type)),
        chip: rs.held ? "Held" : rs.text || L.roomStatus(e, 1),
        chipKey: rs.held ? "cleaning" : st,
        bar: pi != null && p ? p.age_min[pi] / 360 : 0,
        barColor: pi != null && p && p.age_min[pi] > 360 ? "#E5484D" : undefined,
        right: pi != null && p ? duration(p.age_min[pi]) : "",
      });
    });
    out.sort((a, b) => natural(a.title, b.title));
  } else if (tab === "staff" && snap) {
    snap.staff.id.forEach((id, i) => {
      const st = e.staff_state[snap.staff.state[i]] ?? "idle";
      const room = layout.rooms[snap.staff.room[i]];
      const fat = snap.staff.fatigue?.[i];
      out.push({
        sel: { kind: "staff", id, feed: f.key },
        title: id,
        dot: roleColor(e.staff_role[snap.staff.role[i]]),
        sub: `${L.role(e, snap.staff.role[i])}${room ? ` · ${room.label}` : ""}`,
        chip: L.staffState(e, snap.staff.state[i]),
        chipKey: st,
        bar: fat ?? 0,
        barColor: fat != null && fat > 0.7 ? "#E5484D" : fat != null && fat > 0.45 ? "#EDBE3A" : "#22A3A0",
        right: fat != null ? `fatigue ${Math.round(fat * 100)}%` : "",
      });
    });
    out.sort((a, b) => natural(a.title, b.title));
  } else if (tab === "patients" && snap) {
    const p = snap.patients;
    p.id.forEach((id, i) => {
      const st = e.patient_state[p.state[i]] ?? "";
      if (st === "exited") return;
      const room = layout.rooms[p.room[i]];
      out.push({
        sel: { kind: "patient", id, feed: f.key },
        title: patientId(id),
        dot: ACUITY[p.acuity[i]],
        sub: `ESI ${p.acuity[i]} · ${room ? room.label : L.condition(e, p.condition[i])}`,
        chip: L.patientState(e, p.state[i]),
        chipKey: WAIT_STATES.has(st) ? "cleaning" : st === "in_ward" ? "closed" : "occupied",
        bar: p.state_min[i] / 120,
        barColor: WAIT_STATES.has(st) && p.state_min[i] > 60 ? "#E5484D" : undefined,
        right: duration(p.state_min[i]),
        playable: isPlayable(f, i),
        // playable first, then everyone else in the department, ward patients last; most urgent first within each
        rank: (isPlayable(f, i) ? 0 : st === "in_ward" ? 200 : 100) + p.acuity[i],
      });
    });
    out.sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0) || b.bar - a.bar);
  }
  return { rows: out.slice(0, MAX_ROWS), total: out.length };
}

export function EntityList({ f, className = "" }: { f: FeedState; className?: string }) {
  const tab = useUI((s) => s.listTab);
  const selection = useUI((s) => s.selection);
  const set = useUI((s) => s.set);
  const select = useUI((s) => s.select);
  const { rows: list, total } = useMemo(() => rows(f, tab), [f, tab]);
  const scroller = useRef<HTMLDivElement>(null);
  const counts = useMemo(() => {
    const e = enumsOf(f);
    const ex = e.patient_state.indexOf("exited");
    return {
      beds: f.layout?.rooms.filter((r) => BED_TYPES.has(r.type) && r.physical !== false).length ?? 0,
      staff: f.snap?.staff.id.length ?? 0,
      patients: f.snap?.patients.state.filter((s) => s !== ex).length ?? 0,
    };
  }, [f]);
  const selKey = selection && selection.feed === f.key ? `${selection.kind}:${selection.id}` : "";
  // 3D -> list: bring the selected row into view
  useEffect(() => {
    if (!selKey) return;
    const el = scroller.current?.querySelector<HTMLElement>(`[data-row="${CSS.escape(selKey)}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selKey, tab]);
  // switch tab to match what was picked in the scene
  useEffect(() => {
    if (!selection || selection.feed !== f.key) return;
    const want: ListTab | null = selection.kind === "patient" ? "patients" : selection.kind === "staff" ? "staff" : selection.kind === "room" ? "beds" : null;
    if (want && want !== useUI.getState().listTab) {
      if (want !== "beds" || BED_TYPES.has(f.layout?.rooms.find((r) => r.id === selection.id)?.type ?? "")) set({ listTab: want });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selKey]);

  return (
    <div className={`glass pointer-events-auto flex min-h-0 flex-col ${className}`} data-testid="entity-list">
      <div className="flex items-center gap-2 px-3 pb-2 pt-3">
        <div className="seg">
          {(["beds", "staff", "patients"] as ListTab[]).map((t) => (
            <button key={t} data-on={tab === t} data-tab={t} onClick={() => set({ listTab: t })}>
              {t === "beds" ? "Beds" : t === "staff" ? "Staff" : "Patients"}
              <span className="tnum ml-1.5 text-[10.5px] font-medium text-ink-3">{counts[t]}</span>
            </button>
          ))}
        </div>
        <span className="ml-auto">
          <SimTag />
        </span>
      </div>
      <div ref={scroller} className="scroll-thin min-h-0 flex-1 overflow-y-auto px-1.5 pb-1.5">
        {list.length === 0 && <div className="px-2 py-6 text-center text-[12px] text-ink-3">{f.snap ? "Nothing to list." : "Waiting for the first snapshot."}</div>}
        {list.map((r) => {
          const key = `${r.sel.kind}:${r.sel.id}`;
          const on = key === selKey;
          const [bg, fg] = STATUS_STYLE[r.chipKey] ?? STATUS_STYLE.closed;
          return (
            <button
              key={key}
              data-row={key}
              onClick={() => select(on ? null : r.sel)}
              onPointerEnter={() => set({ hover: r.sel })}
              onPointerLeave={() => set({ hover: null })}
              className={`group flex w-full items-center gap-2.5 rounded-xl px-2 py-[7px] text-left transition-colors ${on ? "bg-accent-soft ring-1 ring-inset ring-accent/40" : "hover:bg-white/70"}`}
            >
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: r.dot ?? "rgba(20,26,51,0.12)" }} />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="truncate text-[12px] font-semibold text-ink">{r.title}</span>
                  {r.playable && (
                    <span className="chip bg-accent text-white" title="This patient's encounter with the provider can be played by you">
                      playable
                    </span>
                  )}
                  <span className="chip ml-auto" style={{ background: bg, color: fg }}>
                    {r.chip}
                  </span>
                </span>
                <span className="mt-0.5 flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate text-[11px] text-ink-3">{r.sub}</span>
                  <span className="tnum shrink-0 text-[10.5px] text-ink-3">{r.right}</span>
                </span>
                {r.bar > 0 && (
                  <span className="mt-1 block">
                    <Bar value={r.bar} color={r.barColor} />
                  </span>
                )}
              </span>
            </button>
          );
        })}
        {total > list.length && <div className="px-2 py-2 text-center text-[11px] text-ink-3">Showing {list.length} of {total}. Use search to find the rest.</div>}
      </div>
    </div>
  );
}
