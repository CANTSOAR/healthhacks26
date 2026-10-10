// Owns the two feeds and whatever is currently writing to them (a replay player or the live socket).
import { api, onReachability } from "./api";
import { createFeed, resetFeed, type Feed } from "./feed";
import { LiveSim } from "./live";
import { ReplayPlayer } from "./replay";
import { useUI } from "./ui";
import type { HumanRun } from "./types";

export const feeds: Record<string, Feed> = { a: createFeed("a"), b: createFeed("b") };
export const feedOf = (key: string): Feed => feeds[key] ?? feeds.a;

let player: ReplayPlayer | null = null;
let liveSim: LiveSim | null = null;
let liveB: LiveSim | null = null; // second socket for a live Compare
let generation = 0;

function teardown() {
  generation++;
  player?.dispose();
  player = null;
  liveSim?.close();
  liveSim = null;
  liveB?.close();
  liveB = null;
}

const ui = () => useUI.getState();

// keep the active writer in step with the transport controls
if (typeof window !== "undefined") {
  useUI.subscribe((s, prev) => {
    if (s.speed !== prev.speed) {
      player?.setSpeed(s.speed);
      liveSim?.setSpeed(s.speed);
      liveB?.setSpeed(s.speed);
    }
    if (s.paused !== prev.paused) {
      player?.setPlaying(!s.paused);
      liveSim?.send({ type: s.paused ? "pause" : "resume" });
      liveB?.send({ type: s.paused ? "pause" : "resume" });
    }
  });
  onReachability((online) => useUI.setState({ online }));
}

export async function refreshStatus() {
  const r = await api.status();
  useUI.setState({ status: r.data, online: r.source === "live" });
  return r;
}

export async function loadLists() {
  const [sc, ho, ma, ro] = await Promise.all([api.scenarios(), api.hospitals(), api.managers(), api.rollouts()]);
  const s = ui();
  useUI.setState({
    scenarios: sc.data,
    hospitals: ho.data,
    managers: ma.data,
    rollouts: ro.data,
    listsSource: ro.source,
    scenarioId: sc.data.some((x) => x.id === s.scenarioId) ? s.scenarioId : (sc.data[0]?.id ?? s.scenarioId),
    hospitalId: ho.data.some((x) => x.id === s.hospitalId) ? s.hospitalId : (ho.data[0]?.id ?? s.hospitalId),
  });
  return ro.data;
}

/** Show a hospital with nobody in it (Play mode before a run starts). */
export async function showLayoutOnly() {
  teardown();
  const gen = generation;
  const [lay, en] = await Promise.all([api.layout(ui().hospitalId), api.enums()]);
  if (gen !== generation) return;
  resetFeed(feeds.a);
  resetFeed(feeds.b);
  feeds.a.setState({ origin: lay.source === "live" ? "live" : "fixture", layout: lay.data, layoutRev: 1 });
  enumsFallback = en.data;
}
export let enumsFallback: import("./types").Enums | null = null;

export async function openWatch(rolloutId: string) {
  teardown();
  const gen = generation;
  useUI.setState({ loading: "Loading rollout…", watchId: rolloutId, selection: null });
  try {
    const r = await api.rollout(rolloutId);
    if (gen !== generation) return;
    resetFeed(feeds.b);
    player = new ReplayPlayer([{ feed: feeds.a, rollout: r.data, origin: r.source === "live" ? "replay" : "fixture" }]);
    player.setSpeed(ui().speed);
    player.setPlaying(!ui().paused);
    player.start();
  } finally {
    if (gen === generation) useUI.setState({ loading: null });
  }
}

export async function openCompare(idA: string, idB: string) {
  teardown();
  const gen = generation;
  useUI.setState({ loading: "Loading rollouts…", compareIds: [idA, idB], selection: null, compareLive: "off" });
  try {
    const [a, b] = await Promise.all([api.rollout(idA), api.rollout(idB)]);
    if (gen !== generation) return;
    player = new ReplayPlayer([
      { feed: feeds.a, rollout: a.data, origin: a.source === "live" ? "replay" : "fixture" },
      { feed: feeds.b, rollout: b.data, origin: b.source === "live" ? "replay" : "fixture" },
    ]);
    player.setSpeed(ui().speed);
    player.setPlaying(!ui().paused);
    player.start();
  } finally {
    if (gen === generation) useUI.setState({ loading: null });
  }
}

export const transport = {
  seekTick(t: number) {
    player?.seekTick(t);
  },
  step() {
    player?.step();
    liveSim?.send({ type: "step" });
  },
  canSeek: () => !!player,
};

/** Events worth interrupting for. Routine ones (a patient leaving, a call-out) stay in the feed only. */
const LOUD: Record<string, "info" | "warn"> = { scenario: "warn", arrival_surge: "warn", equipment_down: "warn", equipment_up: "info", structural_started: "info", structural_done: "info", diversion_on: "warn", diversion_off: "info", death: "warn" };
function announce(events: import("./types").SimEvent[]) {
  for (const e of events) if (LOUD[e.kind]) ui().toast(e.text, LOUD[e.kind]);
}

// ------------------------------------------------------------------ Play mode

export async function startPlay() {
  teardown();
  const gen = generation;
  const s = ui();
  s.setPlay({ state: "connecting", requested: {}, posted: null, note: null });
  useUI.setState({ selection: null, paused: false });
  resetFeed(feeds.b);
  const sim = new LiveSim(
    feeds.a,
    { scenario: s.scenarioId, seed: s.play.seed, manager: s.play.manager, speed: s.speed, hospital_id: s.hospitalId },
    {
      state: (st) => {
        if (gen !== generation) return;
        if (st === "closed" && ui().play.state === "live") {
          ui().setPlay({ state: "ended", note: "The simulation connection closed." });
          void postHumanRun();
        }
      },
      events: announce,
      error: (m) => ui().toast(m, "error"),
      manager: (m) => {
        if (gen !== generation) return;
        // the server confirms who is in charge; a manager that fails hands control back to the human
        const known = ui().managers.find((x) => x.id === m.id);
        if (known && feeds.a.getState().header) feeds.a.setState((s) => (s.header ? { header: { ...s.header, manager: { ...m, kind: known.kind, label: known.label } } } : {}));
        if (ui().play.manager !== m.id) ui().setPlay({ manager: m.id });
        ui().toast(m.id === "human" ? "You are back in charge of the hospital." : `${known?.label ?? m.label} is now running the hospital.`, "info");
      },
    },
  );
  liveSim = sim;
  const ok = await sim.connect();
  if (gen !== generation) return;
  if (ok) {
    ui().setPlay({ state: "live" });
    useUI.setState({ online: true });
    return;
  }
  // No simulator: replay the bundled fixture so the screen still works, and say so.
  liveSim = null;
  const r = await api.rollout("fixture");
  if (gen !== generation) return;
  player = new ReplayPlayer([{ feed: feeds.a, rollout: r.data, origin: "fixture" }]);
  player.loop = true;
  player.setSpeed(ui().speed);
  player.start();
  ui().setPlay({ state: "fixture", note: "Simulator offline: replaying a recorded fixture. Knob changes are noted but not simulated." });
}

export const playCtl = {
  action(head: string, value: number) {
    const s = ui();
    s.setPlay({ requested: { ...s.play.requested, [head]: value } });
    liveSim?.send({ type: "action", actions: { [head]: value } });
  },
  inject(event: string, label?: string) {
    if (!liveSim) return;
    liveSim.send({ type: "inject", event });
    ui().toast(`Injected: ${label ?? event}. It starts at the next simulated hour.`, "info");
  },
  manager(id: string) {
    ui().setPlay({ manager: id });
    liveSim?.send({ type: "manager", manager: id });
  },
  detail(kind: string, id: string | number) {
    liveSim?.send({ type: "detail", entity: { kind, id } });
  },
  async stop() {
    const s = ui();
    if (s.play.state === "live" && liveSim) await liveSim.stop(); // resolves on the summary marked final
    await postHumanRun();
    player?.setPlaying(false);
    liveSim?.close();
    liveSim = null;
    ui().setPlay({ state: "ended" });
  },
  isLive: () => !!liveSim,
};

/** Episode summary per contracts/metrics.yaml `episode_summary`, from hourly series (used when the server sent none). */
export function summarise(hourly: Record<string, number[]>, hours: number): Record<string, number> {
  const sum = (k: string) => (hourly[k] ?? []).slice(0, hours).reduce((a, b) => a + b, 0);
  const days = Math.max(hours / 24, 1 / 24);
  const out: Record<string, number> = {};
  const seen = sum("first_seen");
  if (seen > 0) out.wait_mean_min = sum("door_to_provider_sum_min") / seen;
  const arr = sum("arrivals");
  if (arr > 0) out.lwbs_rate = sum("lwbs") / arr;
  out.cost_per_day = sum("cost_total") / days;
  out.margin_per_day = sum("margin") / days;
  const treated = sum("treated");
  if (treated > 0) out.cost_per_treated = sum("cost_total") / treated;
  return out;
}

async function postHumanRun() {
  const s = ui();
  if (s.play.posted) return;
  const f = feeds.a.getState();
  if (!f.header || !f.snap) return;
  const live = f.origin === "live";
  const hours = live ? Math.max(0, ...Object.values(f.hourly).map((a) => a.length)) : Math.floor(f.snap.t / 12) - Math.floor((f.segments[0]?.start ?? 0) / 12);
  const summary = live && f.summary ? f.summary : summarise(live ? f.hourly : sliceHourly(f.hourly, Math.floor((f.segments[0]?.start ?? 0) / 12)), Math.max(1, hours));
  if (!Object.keys(summary).length) return;
  const run: HumanRun = {
    label: live ? "You" : "You (fixture playback, not a simulator run)",
    scenario: live ? f.header.scenario : s.scenarioId,
    seed: f.header.seed,
    // fractional: the trade-off chart shows the run length and whether it is comparable to the evaluation protocol
    days: Math.max(0.01, +((f.snap.t * (f.header.tick_minutes || 5)) / 1440).toFixed(3)),
    summary,
  };
  const where = await api.postHumanRun(run);
  ui().setPlay({ posted: { where, at: Date.now() } });
}
const sliceHourly = (h: Record<string, number[]>, from: number) => Object.fromEntries(Object.entries(h).map(([k, v]) => [k, v.slice(from)]));

// ------------------------------------------------------------------ live Compare

/** Two sockets, same scenario and seed, two managers: the server guarantees both see the same patients. */
export async function startLiveCompare(managerA: string, managerB: string) {
  teardown();
  const gen = generation;
  const s = ui();
  useUI.setState({ selection: null, paused: false, compareLive: "connecting", compareNote: null });
  const mk = (feed: Feed, manager: string) =>
    new LiveSim(feed, { scenario: s.scenarioId, seed: s.play.seed, manager, speed: s.speed, hospital_id: s.hospitalId }, {
      state: (st) => {
        if (gen === generation && st === "closed" && ui().compareLive === "live") useUI.setState({ compareLive: "off", compareNote: "A simulation connection closed." });
      },
    });
  const a = mk(feeds.a, managerA);
  const b = mk(feeds.b, managerB);
  liveSim = a;
  liveB = b;
  const [okA, okB] = await Promise.all([a.connect(4000), b.connect(4000)]);
  if (gen !== generation) return;
  if (okA && okB) {
    useUI.setState({ compareLive: "live", online: true });
    return;
  }
  teardown();
  useUI.setState({ compareLive: "off", compareNote: "The simulator is not reachable, so a live comparison cannot start. Recorded rollouts are shown instead." });
  const ids = ui().compareIds;
  await openCompare(ids[0] ?? "fixture", ids[1] ?? "fixture_b");
}
export async function stopLiveCompare() {
  await Promise.all([liveSim?.stop(), liveB?.stop()]);
  liveSim?.close();
  liveB?.close();
  liveSim = null;
  liveB = null;
  useUI.setState({ compareLive: "ended" });
}

if (typeof window !== "undefined") (window as unknown as { __hg?: unknown }).__hg = { feeds, ui: useUI }; // for debugging from the console

export function stopAll() {
  teardown();
}
