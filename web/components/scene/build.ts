// Turns a layout (contracts/layout.schema.json) into drawable primitives. Nothing here is hard-coded to one
// hospital: every wall, bed and scanner comes from the room list, so a changed layout redraws the building.
import { FLOOR } from "@/lib/palette";
import type { Layout, Room } from "@/lib/types";

export type Geo = "box" | "rbox" | "cyl" | "ico";
export interface PickRef {
  kind: "room" | "equipment";
  id: string;
}
export interface Prim {
  g: Geo;
  x: number;
  y: number;
  z: number;
  sx: number;
  sy: number;
  sz: number;
  rx?: number;
  ry?: number;
  c: string;
  pick?: PickRef;
  /** room index: floor recolours with room status */
  floorOf?: number;
  /** equipment index: recolours when the machine is down / off */
  equip?: number;
  noShadow?: boolean;
}
export interface Torus {
  x: number;
  y: number;
  z: number;
  r: number;
  tube: number;
  c: string;
  pick?: PickRef;
  equip?: number;
}
export interface FloorLabel {
  x: number;
  z: number;
  text: string;
  size: number;
}
export interface Built {
  prims: Prim[];
  tori: Torus[];
  labels: FloorLabel[];
  bounds: { minX: number; maxX: number; minZ: number; maxZ: number; cx: number; cz: number; r: number };
}

export const BED_TYPES = new Set(["treatment_bay", "resus_bay", "fast_track", "icu_bed", "stepdown_bed", "ward_unit", "recovery", "peds_ed"]);
const SEAT_TYPES = new Set(["waiting_room", "results_waiting"]);
const OPEN_TYPES = new Set(["ambulance_bay", "entrance", "corridor"]);
const IMAGING = new Set(["ct", "mri", "xray", "ultrasound"]);

const WALL = "#FFFFFF";
const PAD = "#F9FAFF";
const FRAME = "#E4E8F4";
const MATTRESS = "#F7F8FD";
const BLANKET = "#CBD6FF";
const CHAIR = "#C5CEEC";
const DESK = "#DDE3F6";
const SCREEN = "#27304F";
const MACHINE = "#F1F3FB";
const ACCENT = "#2F55F5";

const WALL_H = 1.05;
const WALL_T = 0.16;
const FLOOR_Y = 0.16;

/**
 * Patient positions for a room, so beds and chairs are drawn where the simulator puts people.
 * Explicit `slots` win. Otherwise the simulator's rule (sim/layoutmodel.py): an even grid of
 * cols = ceil(sqrt(capacity * w / d)) by rows = ceil(capacity / cols), one slot at the centre of each cell.
 * The hand-built contract fixture (hospital_id "fixture") used a different rule, a 1.5 m grid from the north-west
 * corner, and its recorded positions follow that, so `fixtureGrid` keeps it drawable.
 */
export function slotsOf(r: Room, fixtureGrid = false): [number, number][] {
  if (r.slots?.length) return r.slots;
  const out: [number, number][] = [];
  if (fixtureGrid) {
    const cols = Math.max(1, Math.floor(r.w / 1.5));
    for (let k = 0; k < r.capacity; k++) out.push([r.x - r.w / 2 + 0.75 + (k % cols) * 1.5, r.z - r.d / 2 + 0.75 + Math.floor(k / cols) * 1.5]);
    return out;
  }
  const cap = Math.max(0, r.capacity);
  if (!cap) return out;
  const cols = Math.max(1, Math.ceil(Math.sqrt((cap * Math.max(r.w, 0.1)) / Math.max(r.d, 0.1))));
  const rows = Math.ceil(cap / cols);
  for (let k = 0; k < cap; k++) out.push([r.x - r.w / 2 + ((k % cols) + 0.5) * (r.w / cols), r.z - r.d / 2 + (Math.floor(k / cols) + 0.5) * (r.d / rows)]);
  return out;
}

// small deterministic random, so trees stay put between renders
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

export function buildLayout(layout: Layout): Built {
  const prims: Prim[] = [];
  const tori: Torus[] = [];
  const labels: FloorLabel[] = [];
  const rooms = layout.rooms.filter((r) => r.physical !== false);
  const add = (p: Prim) => prims.push(p);

  let minX = Infinity,
    maxX = -Infinity,
    minZ = Infinity,
    maxZ = -Infinity;
  for (const r of rooms) {
    minX = Math.min(minX, r.x - r.w / 2);
    maxX = Math.max(maxX, r.x + r.w / 2);
    minZ = Math.min(minZ, r.z - r.d / 2);
    maxZ = Math.max(maxZ, r.z + r.d / 2);
  }
  if (!isFinite(minX)) {
    minX = 0;
    minZ = 0;
    maxX = layout.site.w;
    maxZ = layout.site.d;
  }
  const cx = (minX + maxX) / 2;
  const cz = (minZ + maxZ) / 2;
  const bounds = { minX, maxX, minZ, maxZ, cx, cz, r: Math.hypot(maxX - minX, maxZ - minZ) / 2 };

  const equipByRoom = new Map<string, number>();
  layout.equipment.forEach((e, i) => {
    if (!equipByRoom.has(e.room)) equipByRoom.set(e.room, i);
  });

  layout.rooms.forEach((r, ri) => {
    if (r.physical === false) return;
    const pick: PickRef = { kind: "room", id: r.id };
    const x0 = r.x - r.w / 2;
    const z0 = r.z - r.d / 2;
    const open = OPEN_TYPES.has(r.type);
    // plinth + floor
    if (!open) add({ g: "box", x: r.x, y: 0.05, z: r.z, sx: r.w + 0.7, sy: 0.1, sz: r.d + 0.7, c: PAD, pick });
    add({ g: "box", x: r.x, y: open ? 0.06 : 0.135, z: r.z, sx: r.w, sy: open ? 0.08 : 0.07, sz: r.d, c: FLOOR[r.type] ?? "#F3F5FC", pick, floorOf: ri, noShadow: true });

    // low walls, roof cut away, with a door gap on the side facing the middle of the building
    if (!open) {
      const doorSouth = r.z < cz;
      const gap = Math.min(r.w * 0.5, r.w > 10 ? 2.6 : 1.5);
      const wall = (wx: number, wz: number, sx: number, sz: number) => add({ g: "box", x: wx, y: FLOOR_Y + WALL_H / 2, z: wz, sx, sy: WALL_H, sz, c: WALL, pick });
      const hSeg = (wz: number, withDoor: boolean) => {
        if (!withDoor) return wall(r.x, wz, r.w + WALL_T, WALL_T);
        const side = (r.w - gap) / 2;
        wall(x0 + side / 2, wz, side + WALL_T, WALL_T);
        wall(r.x + r.w / 2 - side / 2, wz, side + WALL_T, WALL_T);
      };
      hSeg(z0, !doorSouth);
      hSeg(z0 + r.d, doorSouth);
      wall(x0, r.z, WALL_T, r.d);
      wall(x0 + r.w, r.z, WALL_T, r.d);
    }

    const slots = slotsOf(r, layout.hospital_id === "fixture");
    if (BED_TYPES.has(r.type)) {
      for (const [sx, sz] of slots) {
        add({ g: "rbox", x: sx, y: FLOOR_Y + 0.22, z: sz, sx: 0.92, sy: 0.44, sz: 1.42, c: FRAME, pick });
        add({ g: "rbox", x: sx, y: FLOOR_Y + 0.5, z: sz, sx: 0.84, sy: 0.16, sz: 1.34, c: MATTRESS, pick });
        add({ g: "rbox", x: sx, y: FLOOR_Y + 0.53, z: sz + 0.26, sx: 0.86, sy: 0.14, sz: 0.8, c: r.type === "resus_bay" || r.type === "icu_bed" ? "#F6C9CD" : r.type === "fast_track" ? "#BFE6D3" : BLANKET, pick });
      }
      if (r.type !== "ward_unit" && slots.length <= 2) {
        // bedside monitor on a pole
        const [sx, sz] = slots[0] ?? [r.x, r.z];
        const mx = Math.min(sx + 0.85, r.x + r.w / 2 - 0.35);
        add({ g: "cyl", x: mx, y: FLOOR_Y + 0.6, z: sz - 0.35, sx: 0.07, sy: 1.2, sz: 0.07, c: "#C9CFE2", pick });
        add({ g: "rbox", x: mx, y: FLOOR_Y + 1.25, z: sz - 0.35, sx: 0.42, sy: 0.3, sz: 0.1, c: SCREEN, pick });
      }
    } else if (SEAT_TYPES.has(r.type)) {
      for (const [sx, sz] of slots) {
        add({ g: "rbox", x: sx, y: FLOOR_Y + 0.2, z: sz + 0.05, sx: 0.62, sy: 0.4, sz: 0.6, c: CHAIR, pick });
        add({ g: "rbox", x: sx, y: FLOOR_Y + 0.5, z: sz - 0.27, sx: 0.62, sy: 0.6, sz: 0.14, c: CHAIR, pick });
      }
    } else if (r.type === "triage") {
      add({ g: "rbox", x: r.x + r.w * 0.18, y: FLOOR_Y + 0.38, z: r.z + r.d * 0.2, sx: Math.min(1.5, r.w * 0.45), sy: 0.76, sz: 0.7, c: DESK, pick });
      add({ g: "rbox", x: r.x + r.w * 0.18, y: FLOOR_Y + 0.98, z: r.z + r.d * 0.2, sx: 0.5, sy: 0.34, sz: 0.08, c: SCREEN, pick });
      const [sx, sz] = slots[0] ?? [r.x, r.z];
      add({ g: "rbox", x: sx, y: FLOOR_Y + 0.2, z: sz, sx: 0.6, sy: 0.4, sz: 0.6, c: CHAIR, pick });
    } else if (IMAGING.has(r.type)) {
      const ei = equipByRoom.get(r.id);
      const mpick: PickRef = ei != null ? { kind: "equipment", id: layout.equipment[ei].id } : pick;
      const m = (p: Omit<Prim, "pick" | "equip">) => add({ ...p, pick: mpick, equip: ei });
      const tz = Math.min(r.z + 0.5, r.z + r.d / 2 - 1.4);
      if (r.type === "ct" || r.type === "mri") {
        // table running through a ring (CT) or a tunnel (MRI)
        m({ g: "rbox", x: r.x, y: FLOOR_Y + 0.3, z: tz + 0.3, sx: 0.7, sy: 0.6, sz: 1.6, c: FRAME });
        m({ g: "rbox", x: r.x, y: FLOOR_Y + 0.68, z: tz, sx: 0.62, sy: 0.12, sz: 2.6, c: MATTRESS });
        if (r.type === "ct") {
          m({ g: "rbox", x: r.x, y: FLOOR_Y + 0.22, z: tz - 0.9, sx: 2.5, sy: 0.44, sz: 0.9, c: MACHINE });
          tori.push({ x: r.x, y: FLOOR_Y + 1.15, z: tz - 0.9, r: 0.95, tube: 0.36, c: MACHINE, pick: mpick, equip: ei });
          tori.push({ x: r.x, y: FLOOR_Y + 1.15, z: tz - 0.52, r: 0.74, tube: 0.05, c: ACCENT, pick: mpick });
        } else {
          m({ g: "cyl", x: r.x, y: FLOOR_Y + 1.15, z: tz - 1.0, sx: 2.5, sy: 1.9, sz: 2.5, rx: Math.PI / 2, c: MACHINE });
          m({ g: "cyl", x: r.x, y: FLOOR_Y + 1.15, z: tz - 0.04, sx: 1.3, sy: 0.04, sz: 1.3, rx: Math.PI / 2, c: SCREEN });
        }
      } else if (r.type === "xray") {
        m({ g: "rbox", x: r.x, y: FLOOR_Y + 0.36, z: r.z, sx: 0.8, sy: 0.72, sz: 2.1, c: FRAME });
        m({ g: "rbox", x: r.x, y: FLOOR_Y + 0.76, z: r.z, sx: 0.74, sy: 0.08, sz: 2.0, c: MATTRESS });
        m({ g: "box", x: r.x + 0.95, y: FLOOR_Y + 1.05, z: r.z - 0.3, sx: 0.2, sy: 2.1, sz: 0.2, c: MACHINE });
        m({ g: "box", x: r.x + 0.5, y: FLOOR_Y + 2.0, z: r.z - 0.3, sx: 1.1, sy: 0.14, sz: 0.16, c: MACHINE });
        m({ g: "rbox", x: r.x, y: FLOOR_Y + 1.72, z: r.z - 0.3, sx: 0.46, sy: 0.42, sz: 0.46, c: MACHINE });
        m({ g: "box", x: r.x, y: FLOOR_Y + 1.48, z: r.z - 0.3, sx: 0.3, sy: 0.06, sz: 0.3, c: ACCENT });
      } else {
        m({ g: "rbox", x: r.x + 0.8, y: FLOOR_Y + 0.5, z: r.z, sx: 0.55, sy: 1.0, sz: 0.55, c: MACHINE });
        m({ g: "rbox", x: r.x + 0.8, y: FLOOR_Y + 1.2, z: r.z, sx: 0.5, sy: 0.36, sz: 0.1, c: SCREEN });
        add({ g: "rbox", x: r.x - 0.3, y: FLOOR_Y + 0.3, z: r.z, sx: 0.85, sy: 0.6, sz: 1.5, c: FRAME, pick });
      }
    } else if (r.type === "lab") {
      const len = r.w * 0.72;
      for (const dz of [-r.d * 0.28, r.d * 0.28]) {
        add({ g: "rbox", x: r.x, y: FLOOR_Y + 0.45, z: r.z + dz, sx: len, sy: 0.9, sz: 0.75, c: DESK, pick });
        const n = Math.max(2, Math.floor(len / 1.4));
        for (let i = 0; i < n; i++) {
          const ax = r.x - len / 2 + (len / n) * (i + 0.5);
          if (i % 2 === 0) add({ g: "rbox", x: ax, y: FLOOR_Y + 1.12, z: r.z + dz, sx: 0.6, sy: 0.44, sz: 0.5, c: MACHINE, pick });
          else add({ g: "cyl", x: ax, y: FLOOR_Y + 1.08, z: r.z + dz, sx: 0.3, sy: 0.36, sz: 0.3, c: "#9ED3DA", pick });
        }
      }
    } else if (r.type === "pharmacy") {
      const n = Math.max(2, Math.floor((r.w - 1.2) / 1.5));
      for (let i = 0; i < n; i++) {
        const ax = x0 + 0.9 + ((r.w - 1.8) / Math.max(1, n - 1)) * i;
        add({ g: "box", x: ax, y: FLOOR_Y + 0.75, z: r.z - r.d * 0.12, sx: 0.45, sy: 1.5, sz: r.d * 0.5, c: "#F3E7CF", pick });
        add({ g: "box", x: ax, y: FLOOR_Y + 1.0, z: r.z - r.d * 0.12, sx: 0.48, sy: 0.06, sz: r.d * 0.5, c: "#E2D2B0", pick });
        add({ g: "box", x: ax, y: FLOOR_Y + 0.5, z: r.z - r.d * 0.12, sx: 0.48, sy: 0.06, sz: r.d * 0.5, c: "#E2D2B0", pick });
      }
      add({ g: "rbox", x: r.x, y: FLOOR_Y + 0.5, z: r.z + r.d * 0.32, sx: r.w * 0.6, sy: 1.0, sz: 0.6, c: DESK, pick });
    } else if (r.type === "nurse_station") {
      const w = Math.min(r.w * 0.8, 7);
      const d = Math.min(r.d * 0.7, 3);
      add({ g: "rbox", x: r.x, y: FLOOR_Y + 0.5, z: r.z - d / 2, sx: w, sy: 1.0, sz: 0.55, c: DESK, pick });
      add({ g: "rbox", x: r.x - w / 2 + 0.28, y: FLOOR_Y + 0.5, z: r.z, sx: 0.55, sy: 1.0, sz: d, c: DESK, pick });
      add({ g: "rbox", x: r.x + w / 2 - 0.28, y: FLOOR_Y + 0.5, z: r.z, sx: 0.55, sy: 1.0, sz: d, c: DESK, pick });
      add({ g: "box", x: r.x, y: FLOOR_Y + 1.02, z: r.z - d / 2, sx: w, sy: 0.05, sz: 0.6, c: ACCENT, pick });
      for (const dx of [-w * 0.25, w * 0.25]) add({ g: "rbox", x: r.x + dx, y: FLOOR_Y + 1.26, z: r.z - d / 2, sx: 0.5, sy: 0.34, sz: 0.08, c: SCREEN, pick });
    } else if (r.type === "ambulance_bay") {
      const n = Math.max(1, r.capacity);
      const along = r.w >= r.d;
      for (let i = 0; i <= n; i++) {
        const f = i / n - 0.5;
        if (along) add({ g: "box", x: r.x + f * (r.w - 0.3), y: 0.11, z: r.z, sx: 0.14, sy: 0.02, sz: r.d * 0.8, c: "#FFFFFF", pick, noShadow: true });
        else add({ g: "box", x: r.x, y: 0.11, z: r.z + f * (r.d - 0.3), sx: r.w * 0.8, sy: 0.02, sz: 0.14, c: "#FFFFFF", pick, noShadow: true });
      }
      // canopy posts and a thin accent beam: reads as a covered bay without hiding it
      for (const dx of [-r.w / 2 + 0.3, r.w / 2 - 0.3]) add({ g: "cyl", x: r.x + dx, y: 1.6, z: r.z - r.d / 2 + 0.3, sx: 0.22, sy: 3.2, sz: 0.22, c: WALL, pick });
      add({ g: "box", x: r.x, y: 3.25, z: r.z - r.d / 2 + 0.3, sx: r.w, sy: 0.22, sz: 0.5, c: ACCENT, pick });
    } else if (r.type === "entrance") {
      add({ g: "box", x: r.x, y: 0.115, z: r.z, sx: r.w * 0.6, sy: 0.02, sz: r.d * 0.8, c: "#B9C6FF", pick, noShadow: true });
      for (const dx of [-r.w / 2 + 0.2, r.w / 2 - 0.2]) add({ g: "box", x: r.x + dx, y: 1.4, z: r.z - r.d / 2 + 0.2, sx: 0.3, sy: 2.8, sz: 0.3, c: WALL, pick });
      add({ g: "box", x: r.x, y: 2.9, z: r.z - r.d / 2 + 0.2, sx: r.w, sy: 0.3, sz: 0.5, c: WALL, pick });
    } else if (r.type === "operating_room") {
      add({ g: "rbox", x: r.x, y: FLOOR_Y + 0.42, z: r.z, sx: 0.8, sy: 0.84, sz: 2.0, c: FRAME, pick });
      add({ g: "cyl", x: r.x, y: FLOOR_Y + 2.0, z: r.z, sx: 1.0, sy: 0.14, sz: 1.0, c: MACHINE, pick });
    } else if (r.type === "decon") {
      add({ g: "cyl", x: r.x, y: FLOOR_Y + 1.0, z: r.z, sx: 0.12, sy: 2.0, sz: 0.12, c: "#C9CFE2", pick });
      add({ g: "cyl", x: r.x, y: FLOOR_Y + 2.0, z: r.z, sx: 0.6, sy: 0.08, sz: 0.6, c: "#9ED3DA", pick });
    }

    if (Math.min(r.w, r.d) >= 3.2 && r.type !== "treatment_bay" && r.type !== "fast_track") {
      const size = Math.max(0.55, Math.min(1.5, Math.min(r.w * 0.11, r.d * 0.22)));
      const south = r.z + r.d / 2 - size * 0.8 - (open ? 0 : 0.2);
      labels.push({ x: r.x, z: south, text: r.label, size });
    }
  });

  // roads
  for (const road of layout.site.roads ?? []) {
    const w = road.width ?? 6;
    for (let i = 0; i + 1 < road.points.length; i++) {
      const [ax, az] = road.points[i];
      const [bx, bz] = road.points[i + 1];
      const len = Math.hypot(bx - ax, bz - az);
      const ry = -Math.atan2(bz - az, bx - ax);
      add({ g: "box", x: (ax + bx) / 2, y: 0.02, z: (az + bz) / 2, sx: len + w * 0.4, sy: 0.04, sz: w, ry, c: "#D4D9EF", noShadow: true });
      const n = Math.floor(len / 5);
      for (let k = 0; k < n; k++) {
        const f = (k + 0.5) / n;
        add({ g: "box", x: ax + (bx - ax) * f, y: 0.045, z: az + (bz - az) * f, sx: 1.8, sy: 0.02, sz: 0.16, ry, c: "#F4F6FF", noShadow: true });
      }
    }
  }

  // a few trees on empty ground for scale
  const rand = rng(layout.rooms.length * 7919 + Math.round(layout.site.w));
  const blocked = (x: number, z: number) => {
    // keep the whole department footprint clear, not just each room
    if (x > minX - 4 && x < maxX + 4 && z > minZ - 4 && z < maxZ + 4) return true;
    for (const road of layout.site.roads ?? []) {
      const w = (road.width ?? 6) / 2 + 2;
      for (let i = 0; i + 1 < road.points.length; i++) {
        const [ax, az] = road.points[i];
        const [bx, bz] = road.points[i + 1];
        const l2 = (bx - ax) ** 2 + (bz - az) ** 2 || 1;
        const t = Math.max(0, Math.min(1, ((x - ax) * (bx - ax) + (z - az) * (bz - az)) / l2));
        if (Math.hypot(x - (ax + (bx - ax) * t), z - (az + (bz - az) * t)) < w) return true;
      }
    }
    for (const b of layout.site.buildings ?? []) {
      const xs = b.polygon.map((p) => p[0]);
      const zs = b.polygon.map((p) => p[1]);
      if (x > Math.min(...xs) - 2 && x < Math.max(...xs) + 2 && z > Math.min(...zs) - 2 && z < Math.max(...zs) + 2) return true;
    }
    return false;
  };
  const want = Math.min(60, Math.round((layout.site.w * layout.site.d) / 260));
  for (let i = 0, placed = 0; i < want * 6 && placed < want; i++) {
    const x = -12 + rand() * (layout.site.w + 24);
    const z = -12 + rand() * (layout.site.d + 24);
    if (blocked(x, z)) continue;
    placed++;
    const s = 0.8 + rand() * 0.7;
    add({ g: "cyl", x, y: 0.5 * s, z, sx: 0.24 * s, sy: 1.0 * s, sz: 0.24 * s, c: "#C9BFB4" });
    add({ g: "ico", x, y: 1.75 * s, z, sx: 2.1 * s, sy: 2.2 * s, sz: 2.1 * s, ry: rand() * 3, c: rand() > 0.5 ? "#BFDCC8" : "#AFD2BE" });
  }

  return { prims, tori, labels, bounds };
}
