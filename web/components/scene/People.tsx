"use client";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import type { Feed } from "@/lib/feed";
import { ACUITY, roleColor, SKIN, STAFF_HEAD } from "@/lib/palette";
import { useUI } from "@/lib/ui";
import type { Selection } from "@/lib/types";
import { BED_TYPES } from "./build";

const MAX = 4096;
const FADE_MS = 380;
const LYING = new Set(["waiting_provider", "with_provider", "waiting_test", "waiting_results", "boarding", "in_ward"]);

interface Ent {
  kind: "patient" | "staff";
  id: number | string;
  fx: number;
  fz: number;
  tx: number;
  tz: number;
  cx: number;
  cz: number;
  born: number;
  dying: number;
  color: THREE.Color;
  lying: boolean;
  seen: number;
}
/** Rendered position of every person/ambulance, for the selection bracket to follow. Value: [x, z, lying ? 1 : 0]. */
export type PosMap = Map<string, [number, number, number]>;
export const posKey = (kind: string, id: string | number) => `${kind}:${id}`;

const m4 = new THREE.Matrix4();
const q = new THREE.Quaternion();
const qLie = new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI / 2, 0, 0));
const qStand = new THREE.Quaternion();
const v = new THREE.Vector3();
const s = new THREE.Vector3();
const skin = new THREE.Color(SKIN);
const staffHead = new THREE.Color(STAFF_HEAD);
const easeOut = (t: number) => 1 - (1 - t) * (1 - t);

export function People({ feed, feedKey, positions }: { feed: Feed; feedKey: string; positions: PosMap }) {
  const body = useRef<THREE.InstancedMesh>(null);
  const head = useRef<THREE.InstancedMesh>(null);
  // People are a few pixels wide from the default camera, so each one also gets an invisible, much larger click target.
  const hit = useRef<THREE.InstancedMesh>(null);
  const hitGeo = useMemo(() => new THREE.CylinderGeometry(1, 1, 2.4, 10), []);
  const hovered = useRef<string>("");
  const centres = useRef<Float32Array>(new Float32Array(MAX * 2));
  const ents = useRef(new Map<string, Ent>());
  const order = useRef<Selection[]>([]);
  const last = useRef<{ snap: unknown; jump: number; gen: number }>({ snap: null, jump: -1, gen: 0 });
  const bodyGeo = useMemo(() => new THREE.CapsuleGeometry(0.21, 0.46, 4, 12), []);
  const headGeo = useMemo(() => new THREE.SphereGeometry(0.2, 16, 12), []);

  useFrame((state) => {
    const b = body.current;
    const h = head.current;
    const ht = hit.current;
    if (!b || !h) return;
    // click radius in metres: about a dozen pixels whatever the zoom, without swallowing a whole bay when close
    const hitR = Math.max(0.55, Math.min(1.9, state.camera.position.y * 0.0125));
    const st = feed.getState();
    const now = performance.now();
    const map = ents.current;

    if (st.snap !== last.current.snap) {
      const snap = st.snap;
      const jumped = st.jump !== last.current.jump || !last.current.snap;
      last.current = { snap, jump: st.jump, gen: last.current.gen + 1 };
      const gen = last.current.gen;
      if (jumped) map.clear();
      if (snap) {
        const en = st.header?.enums;
        const rooms = st.layout?.rooms;
        const exited = en ? en.patient_state.indexOf("exited") : 11;
        const upsert = (key: string, kind: Ent["kind"], id: number | string, x: number, z: number, color: string, lying: boolean) => {
          let e = map.get(key);
          if (!e) {
            e = { kind, id, fx: x, fz: z, tx: x, tz: z, cx: x, cz: z, born: jumped ? 0 : now, dying: 0, color: new THREE.Color(color), lying, seen: gen };
            map.set(key, e);
          } else {
            e.fx = e.cx;
            e.fz = e.cz;
            e.tx = x;
            e.tz = z;
            e.dying = 0;
            e.color.set(color);
            e.lying = lying;
            e.seen = gen;
          }
        };
        const p = snap.patients;
        for (let i = 0; i < p.id.length; i++) {
          if (p.state[i] === exited) continue;
          const room = rooms?.[p.room[i]];
          const lying = !!room && BED_TYPES.has(room.type) && LYING.has(en?.patient_state[p.state[i]] ?? "");
          upsert("patient:" + p.id[i], "patient", p.id[i], p.x[i], p.z[i], ACUITY[p.acuity[i]] ?? ACUITY[0], lying);
        }
        const sf = snap.staff;
        const off = en ? en.staff_state.indexOf("off_shift") : 0;
        for (let i = 0; i < sf.id.length; i++) {
          if (sf.state[i] === off) continue;
          upsert("staff:" + sf.id[i], "staff", sf.id[i], sf.x[i], sf.z[i], roleColor(en?.staff_role[sf.role[i]]), false);
        }
      }
      for (const e of map.values()) if (e.seen !== last.current.gen && !e.dying) e.dying = now;
    }

    const alpha = st.tickMs > 0 ? Math.min(1, Math.max(0, (now - st.snapAt) / st.tickMs)) : 1;
    let n = 0;
    const ord = order.current;
    positions.clear();
    for (const [key, e] of map) {
      let scale = 1;
      if (e.dying) {
        const t = (now - e.dying) / FADE_MS;
        if (t >= 1) {
          map.delete(key);
          continue;
        }
        scale = 1 - t * t;
      } else if (e.born) {
        const t = (now - e.born) / FADE_MS;
        if (t < 1) scale = easeOut(Math.max(0, t));
        else e.born = 0;
      }
      if (n >= MAX) break;
      e.cx = e.fx + (e.tx - e.fx) * alpha;
      e.cz = e.fz + (e.tz - e.fz) * alpha;
      const k = (e.kind === "staff" ? 1.24 : 1.16) * scale;
      if (e.lying) {
        m4.compose(v.set(e.cx, 0.9, e.cz + 0.12), qLie, s.set(k, k, k));
        b.setMatrixAt(n, m4);
        m4.compose(v.set(e.cx, 0.93, e.cz - 0.5), q, s.set(k, k, k));
        h.setMatrixAt(n, m4);
      } else {
        m4.compose(v.set(e.cx, 0.16 + 0.44 * k, e.cz), qStand, s.set(k, k, k));
        b.setMatrixAt(n, m4);
        m4.compose(v.set(e.cx, 0.16 + 1.06 * k, e.cz), q, s.set(k, k, k));
        h.setMatrixAt(n, m4);
      }
      if (ht) {
        m4.compose(v.set(e.cx, 1.2, e.cz), qStand, s.set(hitR, 1, hitR));
        ht.setMatrixAt(n, m4);
      }
      b.setColorAt(n, e.color);
      h.setColorAt(n, e.kind === "staff" ? staffHead : skin);
      ord[n] = { kind: e.kind, id: e.id, feed: feedKey };
      centres.current[n * 2] = e.cx;
      centres.current[n * 2 + 1] = e.cz;
      positions.set(key, [e.cx, e.cz, e.lying ? 1 : 0]);
      n++;
    }
    b.count = n;
    h.count = n;
    b.instanceMatrix.needsUpdate = true;
    h.instanceMatrix.needsUpdate = true;
    if (b.instanceColor) b.instanceColor.needsUpdate = true;
    if (h.instanceColor) h.instanceColor.needsUpdate = true;
    b.boundingSphere = null;
    h.boundingSphere = null;
    if (ht) {
      ht.count = n;
      ht.instanceMatrix.needsUpdate = true;
      ht.boundingSphere = null;
    }
  });

  /** Click targets overlap where people stand close together: take the person whose centre is nearest the pointer's ray. */
  type Ev = { delta: number; instanceId?: number; stopPropagation: () => void; ray: THREE.Ray; intersections: { object: THREE.Object3D; instanceId?: number }[] };
  const pick = (e: Ev): Selection | null => {
    let best = -1;
    let bd = Infinity;
    for (const x of e.intersections) {
      if (x.object !== hit.current || x.instanceId == null) continue;
      const d = e.ray.distanceSqToPoint(v.set(centres.current[x.instanceId * 2], 0.9, centres.current[x.instanceId * 2 + 1]));
      if (d < bd) {
        bd = d;
        best = x.instanceId;
      }
    }
    if (best < 0 && e.instanceId != null) best = e.instanceId;
    return best >= 0 ? (order.current[best] ?? null) : null;
  };
  const handlers = {
    onClick: (e: Ev) => {
      if (e.delta > 5) return;
      const sel = pick(e);
      if (!sel) return;
      e.stopPropagation();
      useUI.getState().select(sel);
    },
    onPointerMove: (e: Ev) => {
      const sel = pick(e);
      if (!sel) return;
      e.stopPropagation();
      const key = `${sel.kind}:${sel.id}`;
      if (hovered.current !== key) {
        hovered.current = key;
        document.body.style.cursor = "pointer";
        useUI.setState({ hover: sel });
      }
    },
    onPointerOut: () => {
      if (!hovered.current) return;
      hovered.current = "";
      document.body.style.cursor = "";
      useUI.setState({ hover: null });
    },
  };

  return (
    <>
      <instancedMesh ref={hit} args={[hitGeo, undefined, MAX]} frustumCulled={false} userData={{ personHit: true }} {...handlers}>
        <meshBasicMaterial transparent opacity={0} depthWrite={false} colorWrite={false} />
      </instancedMesh>
      <instancedMesh ref={body} args={[bodyGeo, undefined, MAX]} frustumCulled={false} castShadow receiveShadow raycast={() => null}>
        <meshStandardMaterial roughness={0.85} metalness={0} />
      </instancedMesh>
      <instancedMesh ref={head} args={[headGeo, undefined, MAX]} frustumCulled={false} castShadow raycast={() => null}>
        <meshStandardMaterial roughness={0.85} metalness={0} />
      </instancedMesh>
    </>
  );
}
