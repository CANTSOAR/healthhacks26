"use client";
import { RoundedBox } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef, useState } from "react";
import * as THREE from "three";
import type { Feed } from "@/lib/feed";
import { useUI } from "@/lib/ui";
import type { PosMap } from "./People";

interface Amb {
  fx: number;
  fz: number;
  tx: number;
  tz: number;
  heading: number;
  state: string;
}

export function Ambulances({ feed, feedKey, positions }: { feed: Feed; feedKey: string; positions: PosMap }) {
  const [ids, setIds] = useState<string[]>([]);
  const data = useRef(new Map<string, Amb>());
  const groups = useRef(new Map<string, THREE.Group>());
  const last = useRef<unknown>(null);

  useFrame(() => {
    const st = feed.getState();
    if (st.snap !== last.current) {
      last.current = st.snap;
      const list = st.snap?.ambulances ?? [];
      const seen = new Set<string>();
      for (const a of list) {
        seen.add(a.id);
        const g = groups.current.get(a.id);
        const d = data.current.get(a.id);
        if (!d) data.current.set(a.id, { fx: a.x, fz: a.z, tx: a.x, tz: a.z, heading: 0, state: a.state });
        else {
          d.fx = g ? g.position.x : d.tx;
          d.fz = g ? g.position.z : d.tz;
          d.tx = a.x;
          d.tz = a.z;
          d.state = a.state;
          if (Math.hypot(d.tx - d.fx, d.tz - d.fz) > 0.05) d.heading = -Math.atan2(d.tz - d.fz, d.tx - d.fx);
        }
      }
      for (const k of [...data.current.keys()]) if (!seen.has(k)) data.current.delete(k);
      const next = list.map((a) => a.id);
      if (next.join("|") !== ids.join("|")) setIds(next);
    }
    const alpha = st.tickMs > 0 ? Math.min(1, Math.max(0, (performance.now() - st.snapAt) / st.tickMs)) : 1;
    for (const [id, d] of data.current) {
      const g = groups.current.get(id);
      if (!g) continue;
      g.position.set(d.fx + (d.tx - d.fx) * alpha, 0, d.fz + (d.tz - d.fz) * alpha);
      let dh = d.heading - g.rotation.y;
      dh = Math.atan2(Math.sin(dh), Math.cos(dh));
      g.rotation.y += dh * 0.15;
      positions.set("ambulance:" + id, [g.position.x, g.position.z, 0]);
    }
  });

  return (
    <>
      {ids.map((id) => (
        <group
          key={id}
          ref={(g) => {
            if (g) groups.current.set(id, g);
            else groups.current.delete(id);
          }}
          onClick={(e) => {
            if (e.delta > 5) return;
            e.stopPropagation();
            useUI.getState().select({ kind: "ambulance", id, feed: feedKey });
          }}
          onPointerOver={() => (document.body.style.cursor = "pointer")}
          onPointerOut={() => (document.body.style.cursor = "")}
        >
          <RoundedBox args={[3.4, 2.0, 2.1]} radius={0.22} smoothness={3} position={[-0.7, 1.45, 0]} castShadow receiveShadow>
            <meshStandardMaterial color="#FFFFFF" roughness={0.9} />
          </RoundedBox>
          <RoundedBox args={[1.5, 1.45, 2.0]} radius={0.22} smoothness={3} position={[1.7, 1.15, 0]} castShadow receiveShadow>
            <meshStandardMaterial color="#F4F6FF" roughness={0.9} />
          </RoundedBox>
          <mesh position={[1.95, 1.5, 0]}>
            <boxGeometry args={[0.9, 0.5, 2.02]} />
            <meshStandardMaterial color="#27304F" roughness={0.6} />
          </mesh>
          <mesh position={[-0.7, 1.25, 0]}>
            <boxGeometry args={[3.42, 0.34, 2.12]} />
            <meshStandardMaterial color="#2F55F5" roughness={0.9} />
          </mesh>
          <mesh position={[0.6, 2.52, 0]}>
            <boxGeometry args={[0.3, 0.16, 1.2]} />
            <meshStandardMaterial color="#E5484D" roughness={0.8} />
          </mesh>
          {[
            [-1.6, 1.0],
            [-1.6, -1.0],
            [1.6, 1.0],
            [1.6, -1.0],
          ].map(([x, z], i) => (
            <mesh key={i} position={[x, 0.42, z]} rotation={[Math.PI / 2, 0, 0]} castShadow>
              <cylinderGeometry args={[0.42, 0.42, 0.3, 16]} />
              <meshStandardMaterial color="#39415F" roughness={1} />
            </mesh>
          ))}
        </group>
      ))}
    </>
  );
}
