// One place that turns a selection into a title, a pill label and (for the scene) a box to bracket.
import { enumsFallback } from "./session";
import type { FeedState } from "./feed";
import { roomIndex } from "./feed";
import { L, patientId, titleCase } from "./format";
import { ACUITY_SHORT } from "./palette";
import type { Enums, Selection } from "./types";

const EMPTY: Enums = {
  patient_state: [], patient_exit: [], staff_role: [], staff_state: [], room_type: [], room_status: [],
  condition_group: [], arrival_mode: [], age_band: [], payer: [], equipment_type: [], equipment_status: [],
} as unknown as Enums;
export const enumsOf = (f: FeedState): Enums => f.header?.enums ?? enumsFallback ?? EMPTY;

const AWAY = new Set(["waiting_test", "in_test", "walking"]);
const HOLDING_TYPES = new Set(["treatment_bay", "resus_bay", "fast_track", "peds_ed"]);

/**
 * A bay the simulator reports as occupied while nobody is physically in it is being held for a patient who is away
 * (at imaging, or walking). The snapshot does not say which patient, so this looks for one who is away now and whose
 * last recorded bed space was this room. Returns null when that cannot be told from what has been observed.
 */
export function bayHolder(f: FeedState, roomIdx: number): { patientIdx: number; where: string } | null {
  const snap = f.snap;
  const layout = f.layout;
  if (!snap || !layout) return null;
  const e = enumsOf(f);
  const p = snap.patients;
  for (let i = 0; i < p.id.length; i++) {
    if (!AWAY.has(e.patient_state[p.state[i]] ?? "")) continue;
    const hist = f.journeys.get(p.id[i]);
    if (!hist) continue;
    for (let k = hist.length - 1; k >= 0; k--) {
      if (hist[k].t > snap.t) continue;
      const r = layout.rooms[hist[k].room];
      if (r && HOLDING_TYPES.has(r.type)) {
        if (hist[k].room === roomIdx) {
          const now = layout.rooms[p.room[i]];
          return { patientIdx: i, where: now && p.room[i] !== roomIdx ? now.label : "in transit" };
        }
        break;
      }
    }
  }
  return null;
}

/** Room status in words, from the same snapshot fields everywhere: `rooms.status` and `rooms.occupancy`. */
export function roomState(f: FeedState, roomIdx: number): { text: string; key: string; held: boolean; holder: ReturnType<typeof bayHolder> } {
  const snap = f.snap;
  const e = enumsOf(f);
  const r = f.layout?.rooms[roomIdx];
  if (!snap || !r) return { text: "", key: "open_empty", held: false, holder: null };
  const key = e.room_status[snap.rooms.status[roomIdx]] ?? "open_empty";
  const occ = snap.rooms.occupancy[roomIdx] ?? 0;
  if (key === "occupied" && occ === 0 && r.capacity <= 1) {
    const holder = bayHolder(f, roomIdx);
    return { text: holder ? `Held · patient at ${holder.where}` : "Held · patient away", key: "held", held: true, holder };
  }
  return { text: L.roomStatus(e, snap.rooms.status[roomIdx]), key, held: false, holder: null };
}

export interface Described {
  title: string;
  sub: string;
  pill: string;
  catalogRef: string | null;
  /** index into the snapshot arrays, -1 when the entity is not in the current snapshot */
  index: number;
}

export function describe(sel: Selection, f: FeedState): Described | null {
  const e = enumsOf(f);
  const snap = f.snap;
  const layout = f.layout;
  switch (sel.kind) {
    case "patient": {
      const i = snap ? snap.patients.id.indexOf(Number(sel.id)) : -1;
      const title = patientId(sel.id);
      if (i < 0 || !snap) return { title, sub: "Not in the hospital at this moment", pill: title, catalogRef: null, index: -1 };
      const p = snap.patients;
      const st = L.patientState(e, p.state[i]);
      return { title, sub: `${ACUITY_SHORT[p.acuity[i]] ?? ""} · ${L.condition(e, p.condition[i])}`, pill: `${title} · ${st}`, catalogRef: `patient/esi${p.acuity[i]}`, index: i };
    }
    case "staff": {
      const i = snap ? snap.staff.id.indexOf(String(sel.id)) : -1;
      const title = String(sel.id);
      if (i < 0 || !snap) return { title, sub: "Off shift", pill: title, catalogRef: null, index: -1 };
      const role = e.staff_role[snap.staff.role[i]];
      const room = layout?.rooms[snap.staff.room[i]];
      const where = room ? room.label : titleCase(e.staff_state[snap.staff.state[i]] ?? "");
      const name = snap.staff.name?.[i];
      return { title: name ? `${name} (${title})` : title, sub: L.role(e, snap.staff.role[i]), pill: `${title} · ${where}`, catalogRef: role ? `staff/${role}` : null, index: i };
    }
    case "room": {
      if (!layout) return null;
      const i = roomIndex(layout).get(String(sel.id)) ?? -1;
      const r = layout.rooms[i];
      if (!r) return null;
      const rs = roomState(f, i);
      let status = rs.text;
      if (snap && r.capacity === 1 && !rs.held) {
        const pi = snap.patients.room.indexOf(i);
        if (pi >= 0 && e.patient_state[snap.patients.state[pi]] !== "walking" && e.patient_state[snap.patients.state[pi]] !== "exited") status = L.patientState(e, snap.patients.state[pi]);
      } else if (snap && r.capacity > 1) status = `${snap.rooms.occupancy[i] ?? 0} of ${r.capacity}`;
      return { title: r.label, sub: `${L.roomType(r.type)}${r.zone ? ` · ${r.zone}` : ""}`, pill: status ? `${r.label} · ${status}` : r.label, catalogRef: r.catalog_ref ?? `space/${r.type}`, index: i };
    }
    case "equipment": {
      if (!layout) return null;
      const i = layout.equipment.findIndex((q) => q.id === sel.id);
      const q = layout.equipment[i];
      if (!q) return null;
      const status = snap ? titleCase(e.equipment_status[snap.equipment.status[i]] ?? "") : "";
      const title = q.label ?? q.id;
      return { title, sub: `${titleCase(q.type)} · equipment`, pill: status ? `${title} · ${status}` : title, catalogRef: q.catalog_ref ?? `equipment/${q.type}`, index: i };
    }
    case "ambulance": {
      const i = snap?.ambulances?.findIndex((a) => a.id === sel.id) ?? -1;
      const a = snap?.ambulances?.[i];
      const title = String(sel.id);
      return { title, sub: "Ambulance", pill: a ? `${title} · ${titleCase(a.state)}` : title, catalogRef: null, index: i };
    }
  }
}
