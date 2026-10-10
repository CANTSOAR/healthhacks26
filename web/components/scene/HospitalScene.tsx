"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { useCallback, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useStore } from "zustand";
import type { Feed } from "@/lib/feed";
import { GROUND } from "@/lib/palette";
import { useUI } from "@/lib/ui";
import { Ambulances } from "./Ambulances";
import type { Built } from "./build";
import { Building } from "./Building";
import { CameraRig, type Insets } from "./CameraRig";
import { People, type PosMap } from "./People";
import { SceneDebug } from "./SceneDebug";
import { SelectionBox } from "./SelectionBox";

// `?dbgupload=three` leaves three's behaviour alone, so scripts/repro-black-people.mjs can show the bug described in Lights
const UNFIXED = typeof window !== "undefined" && process.env.NODE_ENV !== "production" && new URLSearchParams(window.location.search).get("dbgupload") === "three";

function Lights({ built }: { built: Built | null }) {
  const light = useRef<THREE.DirectionalLight>(null);
  const b = built?.bounds;
  const cx = b?.cx ?? 50;
  const cz = b?.cz ?? 35;
  const r = (b?.r ?? 60) + 24;
  const target = useMemo(() => {
    const o = new THREE.Object3D();
    o.position.set(cx, 0, cz);
    o.updateMatrixWorld();
    return o;
  }, [cx, cz]);
  // The shadow pass redraws every instance; refreshing it on alternate frames halves that cost and is not visible
  // at the speed people walk.
  const frame = useRef(0);
  useFrame((state) => {
    const l = light.current;
    if (!l) return;
    l.shadow.autoUpdate = false;
    if (frame.current++ % 2 === 0) l.shadow.needsUpdate = true;
    // Skipping the shadow pass exposes a flaw in three (0.186, WebGLRenderer.render): instanced attributes are uploaded
    // "once per frame" keyed on info.render.frame, but that counter is incremented between the main scene traversal and
    // the shadow pass. A shadow caster is therefore stamped by the shadow pass with the number the next main traversal
    // sees, and that traversal skips its upload. With a shadow pass every frame nobody notices (the shadow pass uploads
    // before anything is drawn); on a frame without one nothing is uploaded at all. Instance matrices then reach the GPU
    // on alternate frames only, and an instanceColor first created on such a frame is bound into the mesh's vertex
    // array object before its buffer exists, which three caches: every instance black from then on.
    // Advancing the counter on frames without a shadow pass makes the main traversal upload.
    else if (!UNFIXED) state.gl.info.render.frame++;
  });
  return (
    <>
      <hemisphereLight args={["#FFFFFF", "#D5DBF7", 2.25]} />
      <directionalLight
        ref={light}
        position={[cx + r * 0.55, r * 1.25, cz + r * 0.7]}
        target={target}
        intensity={1.25}
        color="#FFF8EE"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0012}
        shadow-normalBias={0.18}
        shadow-radius={5}
        shadow-camera-left={-r}
        shadow-camera-right={r}
        shadow-camera-top={r}
        shadow-camera-bottom={-r}
        shadow-camera-near={1}
        shadow-camera-far={r * 4}
      />
    </>
  );
}

/** The one scene component: Play, Watch and both halves of Compare all render this against a feed. */
export default function HospitalScene({ feed, sync = false, insets }: { feed: Feed; sync?: boolean; insets?: Insets }) {
  const feedKey = useStore(feed, (s) => s.key);
  const layout = useStore(feed, (s) => s.layout);
  const layoutRev = useStore(feed, (s) => s.layoutRev);
  const selection = useUI((s) => s.selection);
  const hover = useUI((s) => s.hover);
  const [built, setBuilt] = useState<Built | null>(null);
  const positions = useMemo<PosMap>(() => new Map(), []);
  const onBuilt = useCallback((b: Built) => setBuilt(b), []);
  const mine = (s: typeof selection) => (s && s.feed === feedKey ? s : null);
  const sel = mine(selection);
  const hov = mine(hover);

  // `?gfx=low` turns shadows and antialiasing off for weak GPUs / software rendering
  const low = useMemo(() => typeof window !== "undefined" && new URLSearchParams(window.location.search).get("gfx") === "low", []);

  return (
    <Canvas
      shadows={!low}
      flat
      dpr={low ? 1 : [1, 1.75]}
      camera={{ fov: 30, near: 2, far: 4000, position: [50, 80, 120] }}
      gl={{ antialias: !low, powerPreference: "high-performance" }}
      onPointerMissed={(e) => {
        if (e.type === "click") useUI.getState().select(null);
      }}
      style={{ background: GROUND }}
    >
      <color attach="background" args={[GROUND]} />
      <fog attach="fog" args={[GROUND, 220, 620]} />
      <Lights built={built} />
      {/* ground: flat colour that matches the page, plus a shadow-only plane */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]} raycast={() => null}>
        <planeGeometry args={[6000, 6000]} />
        <meshBasicMaterial color={GROUND} toneMapped={false} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow raycast={() => null}>
        <planeGeometry args={[3000, 3000]} />
        <shadowMaterial color="#5B6BB5" opacity={0.16} />
      </mesh>
      {layout ? <Building layout={layout} feed={feed} feedKey={feedKey} onBuilt={onBuilt} /> : null}
      <People feed={feed} feedKey={feedKey} positions={positions} />
      <Ambulances key={`a${layoutRev}`} feed={feed} feedKey={feedKey} positions={positions} />
      {sel ? <SelectionBox key={`${sel.kind}:${sel.id}`} sel={sel} feed={feed} positions={positions} /> : null}
      {hov && !(sel && sel.kind === hov.kind && sel.id === hov.id) ? <SelectionBox key={`h${hov.kind}:${hov.id}`} sel={hov} feed={feed} positions={positions} variant="hover" /> : null}
      {process.env.NODE_ENV !== "production" ? <SceneDebug feedKey={feedKey} positions={positions} /> : null}
      <CameraRig built={built} feed={feed} feedKey={feedKey} positions={positions} sync={sync} insets={insets} />
    </Canvas>
  );
}
