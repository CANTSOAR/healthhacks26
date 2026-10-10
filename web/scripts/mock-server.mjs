// A stand-in for the real server, for developing and testing the web client's LIVE path (HTTP + websocket)
// before `server/` exists. It follows contracts/api.md but it is NOT the simulator: patients follow a fixed
// toy pipeline with made-up durations, and every metric it emits is a counter over that toy flow or noise.
//   node scripts/mock-server.mjs [port=8010]
// then open http://localhost:3000/?api=http://localhost:8010
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { WebSocketServer } from "ws";

const port = +(process.argv[2] ?? 8010);
const fx = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../public/fixtures");
const J = (f) => JSON.parse(fs.readFileSync(path.join(fx, f), "utf8"));
const enums = J("enums.json");
const refs = J("catalog-refs.json");
const base = J("rollout.fixture.json");
const layouts = { fixture: J("layout.fixture.json") };
if (fs.existsSync(path.join(fx, "rwjuh_nb.layout.json"))) layouts.rwjuh_nb = J("rwjuh_nb.layout.json");
const humanRuns = [];
const tag = (m) => ({ ...m, label: m.label.replace("[fixture]", "[mock]"), available: true });

const routes = {
  "/api/status": () => ({ services: { sim: { live: true }, llm: { live: false, provider: "offline", model: null }, voice: { live: false, provider: "browser" }, data: { live: false, provider: "public_extracts" } }, torch: null, device: "mock", version: "mock-server" }),
  "/api/enums": () => enums,
  "/api/metrics": () => J("metrics.json"),
  "/api/catalog": () => J("catalog.json"),
  "/api/scenarios": () => J("scenarios.json"),
  "/api/hospitals": () => J("hospitals.json"),
  "/api/managers": () => J("managers.json").map(tag),
  "/api/rollouts": () => J("rollouts.json"),
  "/api/results": () => ({ ...J("results.json"), generated: "mock-server", human_runs: humanRuns }),
};

const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://x");
  const send = (code, body) => {
    res.writeHead(code, { "content-type": "application/json", "access-control-allow-origin": "*", "access-control-allow-headers": "content-type", "access-control-allow-methods": "GET,POST,OPTIONS" });
    res.end(JSON.stringify(body));
  };
  if (req.method === "OPTIONS") return send(204, {});
  const p = decodeURIComponent(url.pathname);
  if (req.method === "POST" && p === "/api/results/human") {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      try {
        humanRuns.push({ ...JSON.parse(body), created: new Date().toISOString() });
        console.log("POST /api/results/human", body.slice(0, 200));
        send(200, { ok: true });
      } catch {
        send(400, { error: "bad json" });
      }
    });
    return;
  }
  if (routes[p]) return send(200, routes[p]());
  let m;
  if ((m = p.match(/^\/api\/catalog\/ref\/(.+)$/))) return refs[m[1]] ? send(200, refs[m[1]]) : send(404, { error: "unknown catalog_ref" });
  if ((m = p.match(/^\/api\/layout\/(.+)$/))) return send(200, layouts[m[1]] ?? layouts.fixture);
  if ((m = p.match(/^\/api\/rollouts\/(.+)$/))) return send(200, J(m[1] === "fixture_b" ? "rollout.fixture_b.json" : "rollout.fixture.json"));
  if ((m = p.match(/^\/api\/runs\/([^/]+)\/patients\/(\d+)$/))) return send(200, { live: {}, latent_truth_available: true, known_state: { triage_note: "mock server: no clinical detail", vitals_taken: true }, interactions: [], catalog_refs: [] });
  if ((m = p.match(/^\/api\/runs\/([^/]+)\/staff\/(.+)$/))) return send(200, { live: {}, profile: { note: "mock server: fictional staff" }, catalog_refs: [] });
  send(404, { error: "not found" });
});

// ------------------------------------------------------------------ toy flow
function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}
// same placement rule as the simulator (sim/layoutmodel.py) and web/components/scene/build.ts
const slotsOf = (r) => {
  if (r.slots?.length) return r.slots;
  const cap = Math.max(0, r.capacity);
  const cols = Math.max(1, Math.ceil(Math.sqrt((cap * Math.max(r.w, 0.1)) / Math.max(r.d, 0.1))));
  const rows = Math.ceil(cap / cols) || 1;
  return Array.from({ length: cap }, (_, k) => [r.x - r.w / 2 + ((k % cols) + 0.5) * (r.w / cols), r.z - r.d / 2 + (Math.floor(k / cols) + 0.5) * (r.d / rows)]);
};
const S = Object.fromEntries(enums.patient_state.map((n, i) => [n, i]));

function makeRun(msg) {
  const layout = layouts[msg.hospital_id] ?? layouts.fixture;
  const rand = rng(msg.seed ?? 1);
  const rooms = layout.rooms;
  const idx = (types) => rooms.map((r, i) => (types.includes(r.type) && r.physical !== false ? i : -1)).filter((i) => i >= 0);
  const pool = { wait: idx(["waiting_room"]), triage: idx(["triage"]), bay: idx(["treatment_bay", "resus_bay", "fast_track", "peds_ed"]), img: idx(["ct", "xray", "mri", "ultrasound"]), ward: idx(["ward_unit", "icu_bed", "stepdown_bed"]), door: idx(["entrance"]), station: idx(["nurse_station"]) };
  const free = new Map(); // room index -> free slot indices
  rooms.forEach((r, i) => free.set(i, slotsOf(r).map((_, k) => k)));
  const take = (list) => {
    const options = list.filter((i) => free.get(i).length);
    if (!options.length) return null;
    const room = options[Math.floor(rand() * options.length)];
    const f = free.get(room);
    const slot = f.splice(Math.floor(rand() * f.length), 1)[0];
    return { room, slot, pos: slotsOf(rooms[room])[slot] ?? [rooms[room].x, rooms[room].z] };
  };
  const give = (h) => h && free.get(h.room).push(h.slot);
  const spec = base.header.action_spec;
  const settings = Object.fromEntries(spec.map((h) => [h.name, h.default]));
  const run = { t: 0, patients: [], nextId: 1, settings, pending: {}, manager: msg.manager ?? "human", surge: 0, hourly: {}, layout, seen: 0, waitSum: 0, arrivals: 0, lwbs: 0, treated: 0, hours: 0, costSum: 0, marginSum: 0 };
  const staff = [];
  const roles = [["MD", 0, 14, pool.bay], ["RN", 3, 44, pool.bay], ["RN", 3, 6, pool.station], ["TECH", 5, 6, pool.img], ["REG", 6, 3, pool.wait]];
  const counters = {};
  for (const [prefix, role, n, where] of roles)
    for (let k = 0; k < n; k++) {
      counters[prefix] = (counters[prefix] ?? 0) + 1;
      const room = where.length ? where[Math.floor(rand() * where.length)] : 0;
      staff.push({ id: `${prefix}-${String(counters[prefix]).padStart(2, "0")}`, role, room, x: rooms[room].x, z: rooms[room].z, tx: rooms[room].x, tz: rooms[room].z, where, fatigue: 0.15 + rand() * 0.3, busy: false });
    }
  const door = () => (pool.door.length ? rooms[pool.door[Math.floor(rand() * pool.door.length)]] : { x: 0, z: 0 });
  const moveTo = (p, h, state, dur) => {
    give(p.hold);
    p.hold = h;
    p.room = h ? h.room : -1;
    p.from = [p.x, p.z];
    p.to = h ? h.pos : [door().x, door().z];
    p.walk = Math.max(1, Math.round(Math.hypot(p.to[0] - p.x, p.to[1] - p.z) / 60)); // ticks at ~12 m per simulated minute
    p.walked = 0;
    p.next = state;
    p.state = S.walking;
    p.stateT = run.t;
    p.left = dur;
  };
  run.tick = () => {
    const t = run.t;
    const hour = Math.floor(((t * 5) % 1440) / 60);
    const rate = (0.5 + 1.0 * Math.exp(-(((hour - 13) / 5) ** 2))) * (run.surge > 0 ? 2.2 : 1);
    const events = [];
    const decisions = [];
    if (run.surge > 0) run.surge--;
    for (let k = 0; k < 3; k++)
      if (rand() < rate / 3) {
        const d = door();
        const acuity = [3, 3, 3, 4, 4, 2, 2, 5, 3, 1][Math.floor(rand() * 10)];
        const p = { id: run.nextId++, acuity, condition: Math.floor(rand() * 9), state: S.waiting_triage, exit: 0, room: -1, x: d.x, z: d.z, arrived: t, stateT: t, mode: rand() < 0.2 ? 1 : 0, age: Math.floor(rand() * 4), payer: Math.floor(rand() * 5), flags: 0, hold: null, left: 0 };
        run.patients.push(p);
        run.arrivals++;
        const h = take(pool.wait);
        if (h) moveTo(p, h, S.waiting_triage, 2 + Math.floor(rand() * 8));
      }
    for (const p of run.patients) {
      if (p.state === S.exited) {
        p.gone = true;
        continue;
      }
      if (p.state === S.walking) {
        p.walked++;
        const a = Math.min(1, p.walked / p.walk);
        p.x = p.from[0] + (p.to[0] - p.from[0]) * a;
        p.z = p.from[1] + (p.to[1] - p.from[1]) * a;
        if (a >= 1) {
          p.state = p.next;
          p.stateT = t;
          if (p.next === S.exited) {
            give(p.hold);
            p.hold = null;
          }
        }
        continue;
      }
      if (--p.left > 0) continue;
      const stay = (n) => {
        p.state = n.s;
        p.stateT = t;
        p.left = n.d;
      };
      if (p.state === S.waiting_triage) {
        const h = take(pool.triage);
        if (h) moveTo(p, h, S.in_triage, 1);
        else if (t - p.arrived > 36 && rand() < 0.03) {
          p.exit = 3;
          run.lwbs++;
          events.push({ t, kind: "lwbs", text: `P-${String(p.id).padStart(6, "0")} left without being seen`, entity: p.id });
          moveTo(p, null, S.exited, 0);
        }
      } else if (p.state === S.in_triage) {
        const h = take(pool.wait);
        if (h) moveTo(p, h, S.waiting_bay, 1 + Math.floor(rand() * 10));
      } else if (p.state === S.waiting_bay) {
        const h = take(pool.bay);
        if (h) moveTo(p, h, S.waiting_provider, 2 + Math.floor(rand() * 8));
      } else if (p.state === S.waiting_provider) {
        run.seen++;
        run.waitSum += (t - p.arrived) * 5;
        stay({ s: S.with_provider, d: 3 + Math.floor(rand() * 4) });
      } else if (p.state === S.with_provider) {
        if (rand() < 0.4) {
          const h = take(pool.img);
          if (h) {
            p.bay = p.hold;
            p.hold = null; // keep the bay while at imaging
            moveTo(p, h, S.in_test, 3);
            continue;
          }
        }
        stay({ s: S.waiting_results, d: 6 + Math.floor(rand() * 14) });
      } else if (p.state === S.in_test) {
        const back = p.bay;
        p.bay = null;
        if (back) {
          give(p.hold);
          p.hold = null;
          moveTo(p, back, S.waiting_results, 6 + Math.floor(rand() * 10));
        } else stay({ s: S.waiting_results, d: 6 });
      } else if (p.state === S.waiting_results) {
        if (rand() < 0.22) {
          p.flags |= 2;
          stay({ s: S.boarding, d: 6 + Math.floor(rand() * 20) });
        } else {
          p.exit = 1;
          run.treated++;
          moveTo(p, null, S.exited, 0);
        }
      } else if (p.state === S.boarding) {
        const h = take(pool.ward);
        if (h) moveTo(p, h, S.in_ward, 200 + Math.floor(rand() * 500));
      } else if (p.state === S.in_ward) {
        p.exit = 2;
        run.treated++;
        moveTo(p, null, S.exited, 0);
      }
    }
    run.patients = run.patients.filter((p) => !p.gone);
    // staff drift between rooms of their kind
    for (const s of staff) {
      if (Math.hypot(s.tx - s.x, s.tz - s.z) < 0.5) {
        if (rand() < 0.12 && s.where.length) {
          s.room = s.where[Math.floor(rand() * s.where.length)];
          s.tx = rooms[s.room].x + (rand() - 0.5) * Math.min(1.6, rooms[s.room].w - 1);
          s.tz = rooms[s.room].z + rooms[s.room].d * 0.3;
        }
        s.busy = rand() < 0.7;
      } else {
        const d = Math.hypot(s.tx - s.x, s.tz - s.z);
        const stepLen = Math.min(d, 30);
        s.x += ((s.tx - s.x) / d) * stepLen;
        s.z += ((s.tz - s.z) / d) * stepLen;
      }
      s.fatigue = Math.min(0.95, Math.max(0.05, s.fatigue + (s.busy ? 0.0015 : -0.002)));
    }
    // apply pending knob changes at their boundary
    const boundary = { hourly: t % 12 === 0, daily: t % 288 === 0, weekly: t % (288 * 7) === 0, monthly: t % (288 * 28) === 0 };
    for (const h of spec) {
      if (!boundary[h.cadence] || run.pending[h.name] == null) continue;
      const v = run.pending[h.name];
      delete run.pending[h.name];
      if (v === settings[h.name]) continue;
      decisions.push({ t, head: h.name, value: v, prev: settings[h.name], cadence: h.cadence, label: `${h.name.replace(/_/g, " ")}: ${h.options[settings[h.name]]} -> ${h.options[v]}` });
      settings[h.name] = v;
    }
    if (run.manager !== "human" && t % 12 === 0 && rand() < 0.35) {
      const h = spec[Math.floor(rand() * 6)];
      run.pending[h.name] = Math.floor(rand() * h.options.length);
    }
    const inEd = run.patients.filter((p) => p.state !== S.in_ward && p.state !== S.exited);
    const waiting = inEd.filter((p) => [S.waiting_triage, S.in_triage, S.waiting_bay, S.waiting_provider].includes(p.state)).length;
    const baysUsed = new Set(inEd.filter((p) => pool.bay.includes(p.room)).map((p) => p.room)).size;
    const P = run.patients;
    const snapshot = {
      t,
      clock: { day: Math.floor((t * 5) / 1440), minute_of_day: (t * 5) % 1440, dow: Math.floor((t * 5) / 1440) % 7 },
      layout_version: 1,
      patients: {
        id: P.map((p) => p.id), acuity: P.map((p) => p.acuity), condition: P.map((p) => p.condition), state: P.map((p) => p.state), exit: P.map((p) => p.exit), room: P.map((p) => p.room),
        x: P.map((p) => +p.x.toFixed(2)), z: P.map((p) => +p.z.toFixed(2)), age_min: P.map((p) => (t - p.arrived) * 5), state_min: P.map((p) => (t - p.stateT) * 5),
        arrival_mode: P.map((p) => p.mode), age_band: P.map((p) => p.age), payer: P.map((p) => p.payer), flags: P.map((p) => p.flags), staff: P.map(() => -1),
      },
      staff: { id: staff.map((s) => s.id), name: staff.map(() => null), role: staff.map((s) => s.role), state: staff.map((s) => (Math.hypot(s.tx - s.x, s.tz - s.z) > 0.5 ? 3 : s.busy ? 2 : 1)), room: staff.map((s) => s.room), x: staff.map((s) => +s.x.toFixed(2)), z: staff.map((s) => +s.z.toFixed(2)), patient: staff.map(() => -1), fatigue: staff.map((s) => +s.fatigue.toFixed(2)) },
      rooms: { status: rooms.map((r, i) => (free.get(i).length < slotsOf(r).length ? 2 : 1)), occupancy: rooms.map((r, i) => slotsOf(r).length - free.get(i).length), queue: rooms.map(() => 0) },
      equipment: { status: layout.equipment.map((e) => (free.get(rooms.findIndex((r) => r.id === e.room))?.length === 0 ? 1 : 0)) },
      ambulances: t % 40 < 14 && pool.door.length ? [{ id: `AMB-${1 + (Math.floor(t / 40) % 6)}`, x: door().x + 30 - (t % 40) * 3, z: door().z + 10, state: t % 40 < 8 ? "approaching" : "unloading" }] : [],
      kpis: { settings: { ...settings }, ed_census: inEd.length, waiting_count: waiting, wait_mean_min: run.seen ? +(run.waitSum / run.seen).toFixed(1) : 0, wait_p95_min: run.seen ? Math.round((run.waitSum / run.seen) * 2.4) : 0, bay_occupancy: +(baysUsed / Math.max(1, pool.bay.length)).toFixed(3), lwbs_rate: run.arrivals ? +(run.lwbs / run.arrivals).toFixed(3) : 0 },
      events,
      decisions,
    };
    let hourMsg = null;
    if (t > 0 && t % 12 === 0) {
      const cost = 9000 + staff.length * 62 + inEd.length * 18 + (settings.rn_night + settings.rn_day + settings.md_day) * 400;
      const revenue = run.treated * 0 + inEd.length * 95 + 6000;
      run.hours++;
      run.costSum += cost;
      run.marginSum += revenue - cost;
      const mask = Object.fromEntries(spec.map((h) => [h.name, h.cadence === "hourly" || (h.cadence === "daily" && (t + 12) % 288 === 0)]));
      hourMsg = { type: "hour", t, metrics: { arrivals: Math.round(rate * 12), first_seen: Math.round(rate * 11), door_to_provider_sum_min: Math.round(rate * 11 * snapshot.kpis.wait_mean_min), wait_mean_min: snapshot.kpis.wait_mean_min, ed_census: inEd.length, waiting_count: waiting, lwbs: 0, cost_total: cost, margin: revenue - cost, treated: Math.round(rate * 10) }, pending: { ...run.pending }, mask };
    }
    run.t++;
    return { snapshot, hourMsg };
  };
  run.summary = () => ({ wait_mean_min: run.seen ? +(run.waitSum / run.seen).toFixed(2) : 0, wait_p95_min: run.seen ? +((run.waitSum / run.seen) * 2.4).toFixed(1) : 0, lwbs_rate: run.arrivals ? +(run.lwbs / run.arrivals).toFixed(4) : 0, cost_per_day: run.hours ? Math.round((run.costSum / run.hours) * 24) : 0, margin_per_day: run.hours ? Math.round((run.marginSum / run.hours) * 24) : 0 });
  return run;
}

const wss = new WebSocketServer({ server, path: "/ws/sim" });
wss.on("connection", (ws) => {
  let run = null;
  let timer = null;
  let tps = 12;
  let paused = false;
  const send = (m) => ws.readyState === 1 && ws.send(JSON.stringify(m));
  const step = () => {
    if (!run) return;
    const { snapshot, hourMsg } = run.tick();
    send({ type: "snapshot", snapshot });
    if (hourMsg) send(hourMsg);
    if (run.t % 288 === 0) send({ type: "summary", summary: run.summary() });
  };
  const loop = () => {
    clearInterval(timer);
    if (run && !paused && tps > 0) timer = setInterval(step, 1000 / tps);
  };
  ws.on("message", (raw) => {
    let m;
    try {
      m = JSON.parse(String(raw));
    } catch {
      return send({ type: "error", message: "bad json" });
    }
    if (m.type === "start") {
      run = makeRun(m);
      tps = m.speed ?? 12;
      paused = false;
      // warm up a simulated morning so the building is busy from the first frame
      for (let i = 0; i < 288 * 2 + 12 * 9; i++) run.tick();
      run.t0 = run.t;
      send({ type: "header", run_id: `mock-${Date.now()}`, scenario: m.scenario, seed: m.seed, hospital_id: run.layout.hospital_id, manager: m.manager === "human" ? { id: "human", kind: "human", label: "You" } : { id: m.manager, kind: "learned", label: `${m.manager} [mock]` }, tick_minutes: 5, enums, layout: run.layout, action_spec: base.header.action_spec, metric_defs: {} });
      loop();
    } else if (!run) send({ type: "error", message: "send start first" });
    else if (m.type === "action") Object.assign(run.pending, m.actions ?? {});
    else if (m.type === "manager") run.manager = m.manager;
    else if (m.type === "speed") ((tps = m.ticks_per_second), (paused = tps === 0), loop());
    else if (m.type === "pause") ((paused = true), loop());
    else if (m.type === "resume") ((paused = false), loop());
    else if (m.type === "step") paused && step();
    else if (m.type === "inject") ((run.surge = 288), send({ type: "snapshot", snapshot: { ...run.tick().snapshot, events: [{ t: run.t, kind: "scenario", text: `Injected: ${m.event} (mock)`, entity: null }] } }));
    else if (m.type === "detail") send({ type: "detail", entity: m.entity, live: {}, catalog: {}, interactions: [] });
    else if (m.type === "stop") {
      send({ type: "summary", summary: run.summary() });
      clearInterval(timer);
      run = null;
    }
  });
  ws.on("close", () => clearInterval(timer));
});
server.listen(port, () => console.log(`mock server (not the simulator) on http://localhost:${port}`));
