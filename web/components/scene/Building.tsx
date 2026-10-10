"use client";
import { useFrame } from "@react-three/fiber";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { Feed } from "@/lib/feed";
import { useUI } from "@/lib/ui";
import type { Layout } from "@/lib/types";
import { buildLayout, type Built, type Geo, type Prim } from "./build";

const GEOS: Record<Geo, () => THREE.BufferGeometry> = {
  box: () => new THREE.BoxGeometry(1, 1, 1),
  rbox: () => new RoundedBoxGeometry(1, 1, 1, 2, 0.12),
  cyl: () => new THREE.CylinderGeometry(0.5, 0.5, 1, 20),
  ico: () => new THREE.IcosahedronGeometry(0.5, 1),
};

const ROOM_TINT: Record<string, string> = { closed: "#DADDE8", out_of_service: "#F1D5D8", cleaning: "#FFF1CF" };
const EQUIP_TINT: Record<string, string> = { down: "#EBA5A8", off: "#D2D6E3" };

const tmpM = new THREE.Matrix4();
const tmpQ = new THREE.Quaternion();
const tmpE = new THREE.Euler();
const tmpP = new THREE.Vector3();
const tmpS = new THREE.Vector3();
const tmpC = new THREE.Color();

function Instances({ geo, items, feed, feedKey }: { geo: Geo; items: Prim[]; feed: Feed; feedKey: string }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const geometry = useMemo(() => GEOS[geo](), [geo]);
  const dynamic = useMemo(() => items.map((p, i) => (p.floorOf != null || p.equip != null ? i : -1)).filter((i) => i >= 0), [items]);
  const lastSnap = useRef<unknown>(null);
  const shadow = geo !== "box" || items.some((p) => !p.noShadow);

  useLayoutEffect(() => {
    const m = ref.current;
    if (!m) return;
    items.forEach((p, i) => {
      tmpE.set(p.rx ?? 0, p.ry ?? 0, 0);
      tmpQ.setFromEuler(tmpE);
      tmpM.compose(tmpP.set(p.x, p.y, p.z), tmpQ, tmpS.set(p.sx, p.sy, p.sz));
      m.setMatrixAt(i, tmpM);
      m.setColorAt(i, tmpC.set(p.c));
    });
    m.count = items.length;
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
    m.computeBoundingSphere();
    m.computeBoundingBox();
    lastSnap.current = null;
  }, [items]);

  useFrame(() => {
    const m = ref.current;
    if (!m || !dynamic.length) return;
    const st = feed.getState();
    if (st.snap === lastSnap.current) return;
    lastSnap.current = st.snap;
    const snap = st.snap;
    const en = st.header?.enums;
    for (const i of dynamic) {
      const p = items[i];
      let c = p.c;
      if (snap && en) {
        if (p.floorOf != null) c = ROOM_TINT[en.room_status[snap.rooms.status[p.floorOf]]] ?? c;
        else if (p.equip != null) c = EQUIP_TINT[en.equipment_status[snap.equipment.status[p.equip]]] ?? c;
      }
      m.setColorAt(i, tmpC.set(c));
    }
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  });

  return (
    <instancedMesh
      ref={ref}
      args={[geometry, undefined, Math.max(1, items.length)]}
      castShadow={shadow}
      receiveShadow
      onClick={(e) => {
        if (e.delta > 5 || e.instanceId == null) return;
        const p = items[e.instanceId];
        if (!p?.pick) return;
        e.stopPropagation();
        useUI.getState().select({ kind: p.pick.kind, id: p.pick.id, feed: feedKey });
      }}
    >
      <meshStandardMaterial roughness={0.92} metalness={0} flatShading={geo === "ico"} />
    </instancedMesh>
  );
}

function FloorLabels({ built }: { built: Built }) {
  const [tex, setTex] = useState<{ t: THREE.CanvasTexture; w: number; h: number; x: number; z: number }[]>([]);
  useEffect(() => {
    let dead = false;
    const made: THREE.CanvasTexture[] = [];
    const draw = () => {
      if (dead) return;
      const out = built.labels.map((l) => {
        const px = 64;
        const c = document.createElement("canvas");
        const ctx = c.getContext("2d")!;
        const font = `600 ${px}px "Inter Variable", Inter, system-ui, sans-serif`;
        ctx.font = font;
        const tw = Math.ceil(ctx.measureText(l.text.toUpperCase()).width + px * 0.3) + 16;
        c.width = tw;
        c.height = Math.ceil(px * 1.4);
        ctx.font = font;
        ctx.textBaseline = "middle";
        ctx.textAlign = "center";
        ctx.fillStyle = "rgba(60,72,125,0.55)";
        // letter-spacing by hand keeps old browsers happy
        (ctx as unknown as { letterSpacing?: string }).letterSpacing = "3px";
        ctx.fillText(l.text.toUpperCase(), c.width / 2, c.height / 2);
        const t = new THREE.CanvasTexture(c);
        t.anisotropy = 8;
        t.colorSpace = THREE.SRGBColorSpace;
        made.push(t);
        const h = l.size;
        return { t, w: (h * c.width) / c.height, h, x: l.x, z: l.z };
      });
      setTex(out);
    };
    const fonts = typeof document !== "undefined" ? document.fonts : null;
    if (fonts?.load) fonts.load('600 64px "Inter Variable"').then(draw, draw);
    else draw();
    return () => {
      dead = true;
      made.forEach((t) => t.dispose());
    };
  }, [built]);
  return (
    <>
      {tex.map((l, i) => (
        <mesh key={i} position={[l.x, 0.175, l.z]} rotation={[-Math.PI / 2, 0, 0]} raycast={() => null}>
          <planeGeometry args={[l.w, l.h]} />
          <meshBasicMaterial map={l.t} transparent depthWrite={false} toneMapped={false} />
        </mesh>
      ))}
    </>
  );
}

function ContextBuildings({ layout }: { layout: Layout }) {
  const items = useMemo(
    () =>
      (layout.site.buildings ?? []).map((b) => {
        const shape = new THREE.Shape(b.polygon.map(([x, z]) => new THREE.Vector2(x, -z)));
        // A footprint with next to no height is a ground slab the rooms stand on (the main hospital outline):
        // draw it flat, never extruded over the interior.
        const slab = (b.height ?? 12) < 1;
        // Other campus buildings are context only: drawn as low massing blocks (a fraction of their real height, capped)
        // so they never hide the department the camera is looking at.
        const g = new THREE.ExtrudeGeometry(shape, { depth: slab ? 0.03 : Math.min(7, Math.max(2.5, (b.height ?? 12) * 0.22)), bevelEnabled: false });
        g.rotateX(-Math.PI / 2);
        return { g, slab };
      }),
    [layout],
  );
  useEffect(() => () => items.forEach((i) => i.g.dispose()), [items]);
  return (
    <>
      {items.map((it, i) => (
        <mesh key={i} geometry={it.g} castShadow={!it.slab} receiveShadow raycast={() => null}>
          <meshStandardMaterial color={it.slab ? "#F1F3FD" : "#F0F2FC"} roughness={1} />
        </mesh>
      ))}
    </>
  );
}

export function Building({ layout, feed, feedKey, onBuilt }: { layout: Layout; feed: Feed; feedKey: string; onBuilt?: (b: Built) => void }) {
  const built = useMemo(() => buildLayout(layout), [layout]);
  useEffect(() => onBuilt?.(built), [built, onBuilt]);
  const groups = useMemo(() => {
    const g: Record<Geo, Prim[]> = { box: [], rbox: [], cyl: [], ico: [] };
    for (const p of built.prims) g[p.g].push(p);
    return g;
  }, [built]);
  return (
    <group>
      {(Object.keys(groups) as Geo[]).map((k) => (groups[k].length ? <Instances key={k + groups[k].length} geo={k} items={groups[k]} feed={feed} feedKey={feedKey} /> : null))}
      {built.tori.map((t, i) => (
        <mesh
          key={i}
          position={[t.x, t.y, t.z]}
          castShadow
          receiveShadow
          onClick={(e) => {
            if (e.delta > 5 || !t.pick) return;
            e.stopPropagation();
            useUI.getState().select({ kind: t.pick.kind, id: t.pick.id, feed: feedKey });
          }}
        >
          <torusGeometry args={[t.r, t.tube, 14, 36]} />
          <meshStandardMaterial color={t.c} roughness={0.9} />
        </mesh>
      ))}
      <FloorLabels built={built} />
      <ContextBuildings layout={layout} />
    </group>
  );
}
