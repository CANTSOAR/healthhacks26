"use client";
import { OrbitControls } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef, type ComponentRef } from "react";
import * as THREE from "three";
import type { Feed } from "@/lib/feed";
import { useUI } from "@/lib/ui";
import type { Built } from "./build";
import type { PosMap } from "./People";
import { boxFor } from "./SelectionBox";

const D2R = Math.PI / 180;
// pitch above the horizon is kept between 34 and 62 degrees (polar angle = 90 - pitch); the rest view is ~47
const MIN_POLAR = 28 * D2R;
const MAX_POLAR = 56 * D2R;
const HOME_POLAR = 43 * D2R;
const HOME_AZ = -0.32;

/** Shared pose so two canvases (Compare) move as one. */
const share = { owner: "", stamp: 0, pos: new THREE.Vector3(), target: new THREE.Vector3() };

export interface Insets {
  l: number;
  r: number;
  t: number;
  b: number;
}

export function CameraRig({ built, feed, feedKey, positions, sync, insets }: { built: Built | null; feed: Feed; feedKey: string; positions: PosMap; sync: boolean; insets?: Insets }) {
  const ctl = useRef<ComponentRef<typeof OrbitControls>>(null);
  const { camera, size, scene, gl } = useThree();
  const swayFrom = useRef<number | null>(null);
  const want = useRef<{ target: THREE.Vector3; dist: number } | null>(null);
  const spin = useRef(0);
  const tilt = useRef(0);
  const dragging = useRef(false);
  const lastTouch = useRef(0);
  const applied = useRef(0);
  const home = useRef<{ target: THREE.Vector3; dist: number } | null>(null);

  // frame the building whenever the layout (or the viewport shape) changes
  useEffect(() => {
    if (!built) return;
    const cam = camera as THREE.PerspectiveCamera;
    const b = built.bounds;
    const aspect = size.width / Math.max(1, size.height);
    const v = (cam.fov * D2R) / 2;
    const h = Math.atan(Math.tan(v) * aspect);
    // fit the footprint: its width against the horizontal field of view, its foreshortened depth against the vertical
    // Panels cover the edges of the canvas: fit into what is left and shift the picture into that free area.
    const ins = insets ?? { l: 0, r: 0, t: 0, b: 0 };
    const freeW = Math.max(0.3, (size.width - ins.l - ins.r) / size.width);
    const freeH = Math.max(0.3, (size.height - ins.t - ins.b) / size.height);
    // the view is turned by HOME_AZ, so the footprint's on-screen extents mix its width and depth
    const ca = Math.abs(Math.cos(HOME_AZ));
    const sa = Math.abs(Math.sin(HOME_AZ));
    const w2 = (b.maxX - b.minX) / 2 + 4;
    const d2 = (b.maxZ - b.minZ) / 2 + 4;
    const halfW = w2 * ca + d2 * sa;
    const halfD = (d2 * ca + w2 * sa) * Math.cos(HOME_POLAR) + 3;
    const dist = Math.max(halfW / (Math.tan(h) * freeW), halfD / (Math.tan(v) * freeH)) * 1.17;
    cam.setViewOffset(size.width, size.height, -(ins.l - ins.r) / 2, -(ins.t - ins.b) / 2, size.width, size.height);
    const target = new THREE.Vector3(b.cx, 0, b.cz);
    const first = !home.current;
    home.current = { target, dist };
    if (first) {
      const off = new THREE.Vector3().setFromSphericalCoords(dist, HOME_POLAR, HOME_AZ);
      camera.position.copy(target).add(off);
      ctl.current?.target.copy(target);
      ctl.current?.update();
    } else want.current = { target: target.clone(), dist };
    const fog = scene.fog as THREE.Fog | null;
    if (fog) {
      fog.near = dist * 1.25;
      fog.far = dist * 3.4;
    }
  }, [built, camera, scene, size.width, size.height, insets?.l, insets?.r, insets?.t, insets?.b]);

  // fly to the selection
  useEffect(
    () =>
      useUI.subscribe((s, prev) => {
        if (s.selection === prev.selection || !s.selection || s.selection.feed !== feedKey) return;
        const sel = s.selection;
        // people may not have a rendered position on the very first frame; retry shortly
        const go = (tries: number) => {
          const box = boxFor(sel, feed, positions);
          if (!box) {
            if (tries > 0) setTimeout(() => go(tries - 1), 80);
            return;
          }
          const span = Math.max(box.s[0], box.s[2]);
          const cur = camera.position.distanceTo(ctl.current?.target ?? new THREE.Vector3());
          const dist = Math.min(cur, Math.max(74, span * 2.6 + 56));
          want.current = { target: new THREE.Vector3(box.c[0], 0, box.c[2]), dist };
        };
        go(4);
      }),
    [camera, feed, feedKey, positions],
  );

  // buttons in the camera pill
  useEffect(
    () =>
      useUI.subscribe((s, prev) => {
        const c = s.camCmd;
        if (!c || c === prev.camCmd || !ctl.current) return;
        if (sync && feedKey !== "a") return; // one rig leads, the other follows through the shared pose
        lastTouch.current = performance.now();
        const t = ctl.current.target;
        const d = camera.position.distanceTo(t);
        if (c.type === "zoom") want.current = { target: (want.current?.target ?? t).clone(), dist: THREE.MathUtils.clamp((want.current?.dist ?? d) * c.amount, 12, 900) };
        else if (c.type === "rotate") spin.current += c.amount;
        else if (c.type === "tilt") tilt.current += c.amount;
        else if (c.type === "reset" && home.current) {
          want.current = { target: home.current.target.clone(), dist: home.current.dist };
          const az = ctl.current.getAzimuthalAngle();
          spin.current = Math.atan2(Math.sin(HOME_AZ - az), Math.cos(HOME_AZ - az));
          tilt.current = HOME_POLAR - ctl.current.getPolarAngle();
        }
      }),
    [camera, feedKey, sync],
  );

  useFrame((_, dt) => {
    const c = ctl.current;
    if (!c) return;
    const now = performance.now();
    const k = 1 - Math.exp(-Math.min(dt, 0.1) * 3.4);
    let moving = dragging.current;
    const off = camera.position.clone().sub(c.target);
    if (want.current && !dragging.current) {
      const w = want.current;
      c.target.lerp(w.target, k);
      const d = off.length();
      off.setLength(d + (w.dist - d) * k);
      if (c.target.distanceTo(w.target) < 0.05 && Math.abs(off.length() - w.dist) < 0.1) want.current = null;
      moving = true;
    }
    if (Math.abs(spin.current) > 0.001 || Math.abs(tilt.current) > 0.001) {
      const sph = new THREE.Spherical().setFromVector3(off);
      const ds = spin.current * k;
      const dtl = tilt.current * k;
      spin.current -= ds;
      tilt.current -= dtl;
      sph.theta += ds;
      sph.phi = THREE.MathUtils.clamp(sph.phi + dtl, MIN_POLAR, MAX_POLAR);
      off.setFromSpherical(sph);
      moving = true;
    }
    if (moving) camera.position.copy(c.target).add(off);
    // Slow idle drift once nobody has touched the camera for a while: a gentle sway of about twenty degrees either
    // side of where the view was left, never a full turn (from behind, the floor labels would read mirrored).
    const idle = !moving && now - lastTouch.current > 6000;
    const drifting = idle && (!sync || feedKey === "a");
    if (drifting) {
      if (swayFrom.current == null) swayFrom.current = now;
      const w = 0.045; // radians per second of phase
      const ph = ((now - swayFrom.current) / 1000) * w;
      const dth = 0.35 * w * Math.cos(ph) * Math.min(dt, 0.1);
      const sph = new THREE.Spherical().setFromVector3(off);
      sph.theta += dth;
      off.setFromSpherical(sph);
      camera.position.copy(c.target).add(off);
    } else swayFrom.current = null;
    c.autoRotate = false;
    c.update();

    // test hook: where an entity is on screen (used by scripts/screenshots.mjs to click people)
    const hg = (window as unknown as { __hg?: { project?: Record<string, (key: string) => [number, number] | null> } }).__hg;
    if (hg && !hg.project?.[feedKey]) {
      hg.project = hg.project ?? {};
      hg.project[feedKey] = (key: string) => {
        const p = positions.get(key);
        if (!p) return null;
        const v3 = new THREE.Vector3(p[0], 0.9, p[1]).project(camera);
        const r = gl.domElement.getBoundingClientRect();
        return [r.left + ((v3.x + 1) / 2) * r.width, r.top + ((1 - v3.y) / 2) * r.height];
      };
    }

    if (sync) {
      if (moving || drifting || share.owner === "") {
        share.owner = feedKey;
        share.stamp = now;
        share.pos.copy(camera.position);
        share.target.copy(c.target);
      } else if (share.owner !== feedKey && share.stamp > applied.current) {
        applied.current = share.stamp;
        camera.position.copy(share.pos);
        c.target.copy(share.target);
        c.update();
      }
    }
  });

  return (
    <OrbitControls
      ref={ctl}
      makeDefault
      enableDamping
      dampingFactor={0.09}
      minPolarAngle={MIN_POLAR}
      maxPolarAngle={MAX_POLAR}
      minDistance={10}
      maxDistance={900}
      autoRotateSpeed={0.22}
      screenSpacePanning={false}
      zoomSpeed={0.8}
      rotateSpeed={0.6}
      onStart={() => {
        dragging.current = true;
        want.current = null;
        spin.current = 0;
        tilt.current = 0;
        lastTouch.current = performance.now();
      }}
      onEnd={() => {
        dragging.current = false;
        lastTouch.current = performance.now();
      }}
    />
  );
}
