"use client";
import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { describe } from "@/lib/describe";
import { roomIndex, type Feed } from "@/lib/feed";
import type { Selection } from "@/lib/types";
import { posKey, type PosMap } from "./People";

/** Box to bracket: centre and size in metres. */
export function boxFor(sel: Selection, feed: Feed, positions: PosMap): { c: [number, number, number]; s: [number, number, number] } | null {
  const st = feed.getState();
  const layout = st.layout;
  if (sel.kind === "room" && layout) {
    const r = layout.rooms[roomIndex(layout).get(String(sel.id)) ?? -1];
    if (!r) return null;
    return { c: [r.x, 0.95, r.z], s: [r.w + 0.9, 1.9, r.d + 0.9] };
  }
  if (sel.kind === "equipment" && layout) {
    const q = layout.equipment.find((e) => e.id === sel.id);
    const r = q ? layout.rooms[roomIndex(layout).get(q.room) ?? -1] : null;
    if (!r) return null;
    return { c: [r.x, 1.25, r.z - 0.2], s: [Math.min(r.w, 3.6), 2.5, Math.min(r.d, 4.4)] };
  }
  const p = positions.get(posKey(sel.kind, sel.id));
  if (!p) return null;
  if (sel.kind === "ambulance") return { c: [p[0], 1.4, p[1]], s: [6, 2.9, 6] };
  return p[2] ? { c: [p[0], 0.85, p[1] - 0.1], s: [1.3, 1.0, 1.9] } : { c: [p[0], 0.9, p[1]], s: [1.0, 1.75, 1.0] };
}

const ARM = 0.28; // corner arm length as a fraction of the shortest side (capped)

export function SelectionBox({ sel, feed, positions, variant = "selected" }: { sel: Selection; feed: Feed; positions: PosMap; variant?: "selected" | "hover" }) {
  const group = useRef<THREE.Group>(null);
  const mesh = useRef<THREE.InstancedMesh>(null);
  const size = useRef<[number, number, number]>([0, 0, 0]);
  const [label, setLabel] = useState("");
  const lastLabelAt = useRef(0);
  const geo = useMemo(() => new THREE.BoxGeometry(1, 1, 1), []);
  const mat = useMemo(
    () => new THREE.MeshBasicMaterial({ color: "#2F55F5", toneMapped: false, depthTest: false, transparent: true, opacity: variant === "hover" ? 0.45 : 1, fog: false }),
    [variant],
  );

  useFrame((state) => {
    const g = group.current;
    const m = mesh.current;
    if (!g || !m) return;
    const box = boxFor(sel, feed, positions);
    if (!box) {
      g.visible = false;
      return;
    }
    g.visible = true;
    g.position.set(...box.c);
    // keep the bracket strokes a constant apparent weight
    const dist = state.camera.position.distanceTo(g.position);
    const th = Math.max(0.035, dist * 0.0022) * (variant === "hover" ? 0.8 : 1);
    const [sx, sy, sz] = box.s;
    if (size.current[0] !== sx || size.current[1] !== sy || size.current[2] !== sz || m.userData.th !== th) {
      size.current = [sx, sy, sz];
      m.userData.th = th;
      const arm = Math.min(Math.min(sx, sy, sz) * ARM + 0.15, 1.6);
      const M = new THREE.Matrix4();
      let i = 0;
      for (const ax of [-1, 1])
        for (const ay of [-1, 1])
          for (const az of [-1, 1]) {
            const cx = (ax * sx) / 2;
            const cy = (ay * sy) / 2;
            const cz = (az * sz) / 2;
            M.makeScale(arm, th, th).setPosition(cx - (ax * arm) / 2, cy, cz);
            m.setMatrixAt(i++, M);
            M.makeScale(th, arm, th).setPosition(cx, cy - (ay * arm) / 2, cz);
            m.setMatrixAt(i++, M);
            M.makeScale(th, th, arm).setPosition(cx, cy, cz - (az * arm) / 2);
            m.setMatrixAt(i++, M);
          }
      m.instanceMatrix.needsUpdate = true;
    }
    if (variant === "selected") {
      const now = performance.now();
      if (now - lastLabelAt.current > 200) {
        lastLabelAt.current = now;
        const d = describe(sel, feed.getState());
        const text = d?.pill ?? "";
        if (text !== label) setLabel(text);
      }
    }
  });

  return (
    <group ref={group} visible={false}>
      <instancedMesh ref={mesh} args={[geo, mat, 24]} frustumCulled={false} renderOrder={20} raycast={() => null} />
      {variant === "selected" && label ? (
        <Html position={[0, size.current[1] / 2 + 0.5, 0]} center zIndexRange={[20, 0]} style={{ pointerEvents: "none" }}>
          <div className="pill-label">
            <span className="pill-dot" />
            {label}
          </div>
        </Html>
      ) : null}
    </group>
  );
}
