"use client";
import { useThree } from "@react-three/fiber";
import { useEffect } from "react";
import * as THREE from "three";
import type { PosMap } from "./People";

/**
 * Development aid for `scripts/repro-black-people.mjs`. Does nothing unless the page sets `window.__sceneDebugOn`
 * before the scene mounts; then, about twice a second, it publishes under `window.__sceneDebug[feedKey]` what each
 * instanced mesh looks like to the renderer and the colour of the pixels drawn over a sample of people.
 */
export function SceneDebug({ feedKey, positions }: { feedKey: string; positions: PosMap }) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  useEffect(() => {
    const w = window as unknown as { __sceneDebugOn?: boolean | string; __sceneDebug?: Record<string, unknown> };
    if (!w.__sceneDebugOn) return;
    w.__sceneDebug ??= {};
    const ctx = gl.getContext() as WebGL2RenderingContext;
    const v = new THREE.Vector3();
    const px = new Uint8Array(4);
    let frame = 0;
    const prev = scene.onAfterRender;
    scene.onAfterRender = () => {
      if (frame++ % 30 !== 0) return;
      const meshes: unknown[] = [];
      scene.traverse((o) => {
        const m = o as THREE.InstancedMesh;
        if (!m.isInstancedMesh) return;
        const mat = m.material as THREE.Material;
        const mp = gl.properties.get(mat) as { currentProgram?: { id: number; getAttributes: () => Record<string, { location: number }> }; instancingColor?: boolean };
        const ic = m.instanceColor;
        meshes.push({
          id: m.id,
          geo: m.geometry.type,
          count: m.count,
          cast: m.castShadow,
          receive: m.receiveShadow,
          hasInstanceColor: !!ic,
          colorVersion: ic?.version ?? -1,
          colors: ic ? Array.from((ic.array as Float32Array).slice(0, 9)).map((x) => +x.toFixed(3)) : [],
          program: mp.currentProgram?.id ?? -1,
          programInstancingColor: mp.instancingColor ?? null,
          colorAttrLocation: mp.currentProgram?.getAttributes().instanceColor?.location ?? -1,
          vao: (m.userData.dbgVao as unknown) ?? null,
        });
        // what the vertex array object used for this mesh's draw really has at the instance colour location
        if (!m.userData.dbgHooked) {
          m.userData.dbgHooked = true;
          m.onAfterRender = (_r, _s, cam, _g, material) => {
            if ((cam as THREE.Camera) !== camera || !(w as { __sceneDebugProbe?: boolean }).__sceneDebugProbe) return;
            const prog = (gl.properties.get(material) as typeof mp).currentProgram;
            const loc = prog?.getAttributes().instanceColor?.location ?? -1;
            if (loc < 0) return void (m.userData.dbgVao = { loc });
            const buf = ctx.getVertexAttrib(loc, ctx.VERTEX_ATTRIB_ARRAY_BUFFER_BINDING) as WebGLBuffer | null;
            let bytes = -1;
            if (buf) {
              const was = ctx.getParameter(ctx.ARRAY_BUFFER_BINDING);
              ctx.bindBuffer(ctx.ARRAY_BUFFER, buf);
              bytes = ctx.getBufferParameter(ctx.ARRAY_BUFFER, ctx.BUFFER_SIZE);
              ctx.bindBuffer(ctx.ARRAY_BUFFER, was);
            }
            m.userData.dbgVao = { loc, enabled: ctx.getVertexAttrib(loc, ctx.VERTEX_ATTRIB_ARRAY_ENABLED), divisor: ctx.getVertexAttrib(loc, ctx.VERTEX_ATTRIB_ARRAY_DIVISOR), buffer: !!buf, isBuffer: buf ? ctx.isBuffer(buf) : false, bytes };
          };
        }
      });
      // pixels over standing people: chest height, at the centre of the body capsule
      const W = ctx.drawingBufferWidth;
      const H = ctx.drawingBufferHeight;
      const samples: number[][] = [];
      for (const [key, p] of positions) {
        if (samples.length >= 60) break;
        if (!/^(patient|staff):/.test(key) || p[2]) continue;
        v.set(p[0], 0.75, p[1]).project(camera);
        if (Math.abs(v.x) > 0.95 || Math.abs(v.y) > 0.95) continue;
        const x = Math.round(((v.x + 1) / 2) * W);
        const y = Math.round(((v.y + 1) / 2) * H);
        ctx.readPixels(x, y, 1, 1, ctx.RGBA, ctx.UNSIGNED_BYTE, px);
        samples.push([px[0], px[1], px[2]]);
      }
      const dark = samples.filter((s) => s[0] < 45 && s[1] < 45 && s[2] < 45).length;
      w.__sceneDebug![feedKey] = { frame, people: positions.size, meshes, sampled: samples.length, dark, samples: samples.slice(0, 8) };
    };
    return () => {
      scene.onAfterRender = prev;
      delete w.__sceneDebug?.[feedKey];
    };
  }, [gl, scene, camera, feedKey, positions]);
  return null;
}
