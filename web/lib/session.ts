// Owns the two feeds and whatever is currently writing to them (a replay player or the live socket).
import { api, onReachability } from "./api";
import { createFeed, resetFeed, type Feed, type FeedState } from "./feed";
import { LiveSim } from "./live";
import { ReplayPlayer } from "./replay";
import { SPEEDS, useUI } from "./ui";
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
      if (!s.paused && s.windowEnd) useUI.setState({ windowEnd: null });
      player?.setPlaying(!s.paused);
      liveSim?.send({ type: s.paused ? "pause" : "resume" });
      if (s.paused) void refreshPlayable();
      liveB?.send({ type: s.paused ? "pause" : "resume" });
    }
  });
  onReachability((online) => useUI.setState({ online }));
  useUI.subscribe((s, prev) => {
    if (s.selection !== prev.selection && liveSim && s.mode === "play" && s.play.state === "live") saveRun({ selection: s.selection ? { kind: s.selection.kind, id: s.selection.id } : null });
  });
}

export async function refreshStatus() {
  const r = await api.status();
  useUI.setState({ status: r.data, online: r.source === "live" });
  return r;
}

export async function loadLists() {
  const [sc, ho, ma, ro, re] = await Promise.all([api.scenarios(), api.hospitals(), api.managers(), api.rollouts(), api.results().catch(() => null)]);
  const s = ui();
  useUI.setState({
    scenarios: sc.data,
    hospitals: ho.data,
    managers: ma.data,
    rollouts: ro.data,
    listsSource: ro.source,
    results: re?.data ?? null,
    scenarioId: sc.data.some((x) => x.id === s.scenarioId) ? s.scenarioId : (sc.data[0]?.id ?? s.scenarioId),
    hospitalId: ho.data.some((x) => x.id === s.hospitalId) ? s.hospitalId : (ho.data[0]?.id ?? s.hospitalId),
  });
  return ro.data;
}

/** Show a hospital with nobody in it (Play mode before a run starts). */
export async function showLayoutOnly(keepNote = false) {
  void keepNote;
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
    watchWindows(player, gen);
    useUI.setState({ windowEnd: null, chartCursor: null });
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
    watchWindows(player, gen);
    useUI.setState({ windowEnd: null, chartCursor: null });
    player.setSpeed(ui().speed);
    player.setPlaying(!ui().paused);
    player.start();
  } finally {
    if (gen === generation) useUI.setState({ loading: null });
  }
}

// ------------------------------------------------------------------ the live run this tab owns
// Kept in sessionStorage so a reload, a mode switch or a trip to /encounter rejoins the run instead of losing it.
// The server keeps a run (paused) for at least ten minutes after its socket closes.
export interface SavedRun {
  run_id: string;
  scenario?: string;
  hospital?: string;
  selection?: { kind: string; id: string | number } | null;
}
const RUN_KEY = "hg.run";
export function savedRun(): SavedRun | null {
  try {
    const v = JSON.parse(window.sessionStorage.getItem(RUN_KEY) || "null") as SavedRun | null;
    return v && typeof v.run_id === "string" ? v : null;
  } catch {
    return null;
  }
}
export function saveRun(patch: Partial<SavedRun>) {
  try {
    const cur = savedRun();
    const next = { ...(cur ?? {}), ...patch } as SavedRun;
    if (next.run_id) window.sessionStorage.setItem(RUN_KEY, JSON.stringify(next));
    useUI.setState({ hasSavedRun: !!next.run_id });
  } catch {
    /* storage blocked */
  }
}
export function clearRun() {
  try {
    window.sessionStorage.removeItem(RUN_KEY);
  } catch {
    /* storage blocked */
  }
  useUI.setState({ hasSavedRun: false });
}
/** True while this tab drives a live Play run (used to guard scenario / hospital changes). */
export const runIsLive = () => !!liveSim && ui().mode === "play" && ui().play.state === "live";

/** Stop at the end of a recorded window and say so, instead of looping. */
function watchWindows(p: ReplayPlayer, gen: number) {
  p.onWindowEnd = (info) => {
    if (gen !== generation) return;
    useUI.setState({ windowEnd: info, paused: true });
  };
}

export const transport = {
  /** Returns false when tick t has no 3D recording (the scene then stays where it is). */
  seekTick(t: number, snap = false): boolean {
    if (!player) return false;
    const ok = player.seekTick(t, snap);
    if (ok) useUI.setState({ windowEnd: null, chartCursor: null });
    return ok;
  },
  nextWindow() {
    player?.nextWindow();
    useUI.setState({ windowEnd: null, chartCursor: null, paused: false });
    player?.setPlaying(true);
  },
  replayWindow() {
    player?.replayWindow();
    useUI.setState({ windowEnd: null, chartCursor: null, paused: false });
    player?.setPlaying(true);
  },
  windows: () => player?.windowTicks() ?? [],
  step() {
    player?.step();
    liveSim?.send({ type: "step" });
  },
  canSeek: () => !!player,
};

/** While the clock is paused no `hour` message arrives, so ask the server who can be played. */
export async function refreshPlayable() {
  const h = feeds.a.getState().header;
  if (!liveSim || !h?.live) return;
  try {
    const r = await api.runPlayable(h.id);
    if (Array.isArray(r.playable)) feeds.a.setState({ playable: new Set(r.playable.map(Number)) });
  } catch {
    /* older server: the state-based rule stays in use */
  }
}

/** Events worth interrupting for. Routine ones (a patient leaving, a call-out) stay in the feed only. */
const LOUD: Record<string, "info" | "warn"> = { scenario: "warn", arrival_surge: "warn", equipment_down: "warn", equipment_up: "info", structural_started: "info", structural_done: "info", diversion_on: "warn", diversion_off: "info", death: "warn" };
function announce(events: import("./types").SimEvent[]) {
  for (const e of events) if (LOUD[e.kind]) ui().toast(e.text, LOUD[e.kind]);
}

// ------------------------------------------------------------------ Play mode

/**
 * Start a live run, or with `attach` rejoin one the server still holds. `select` picks an entity once the first
 * snapshot is in (used when coming back from an encounter, so the camera lands on that patient).
 */
export async function startPlay(opts: { attach?: string; select?: { kind: string; id: string | number } | null } = {}) {
  teardown();
  const gen = generation;
  const s = ui();
  s.setPlay({ state: "connecting", requested: {}, posted: null, note: null });
  useUI.setState({ selection: null, paused: false });
  if (!opts.attach) clearRun(); // a fresh start replaces any remembered run
  resetFeed(feeds.b);
  const sim = new LiveSim(
    feeds.a,
    { scenario: s.scenarioId, seed: s.play.seed, manager: s.play.manager, speed: s.speed, hospital_id: s.hospitalId, attach: opts.attach },
    {
      state: (st) => {
        if (gen !== generation) return;
        if (st === "closed" && ui().play.state === "live") {
          // the socket dropped (server restart, network): the run may still be on the server, so offer to rejoin
          liveSim = null;
          ui().setPlay({ state: "idle", note: "The connection to the simulator closed. If the run is still on the server you can rejoin it." });
        }
      },
      events: announce,
      error: (m) => ui().toast(m, "error"),
      detached: () => {
        if (gen !== generation) return;
        liveSim = null;
        ui().setPlay({ state: "idle", note: "This run is now open in another tab or window. Use “Rejoin run” to bring it back here." });
      },
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
    const h = feeds.a.getState().header;
    ui().setPlay({ state: "live", ...(h ? { manager: h.manager.id, seed: h.seed } : {}) });
    const patch: Partial<ReturnType<typeof useUI.getState>> = { online: true };
    if (opts.attach && h) {
      // the menus follow the run that was rejoined
      if (ui().scenarios.some((x) => x.id === h.scenario)) patch.scenarioId = h.scenario;
      if (ui().hospitals.some((x) => x.id === h.hospital_id)) patch.hospitalId = h.hospital_id;
      if (sim.attachedSpeed && SPEEDS.includes(sim.attachedSpeed)) patch.speed = sim.attachedSpeed;
    }
    useUI.setState(patch);
    if (h) saveRun({ run_id: h.id, scenario: h.scenario, hospital: h.hospital_id });
    if (opts.attach) {
      sim.send({ type: "resume" });
      ui().toast("Rejoined your run where it was paused.", "info");
    }
    if (opts.select) selectWhenPresent(opts.select, gen);
    void refreshPlayable();
    return;
  }
  liveSim = null;
  if (opts.attach) {
    // never fall back to a fixture when the user expected their own run back
    if (sim.gone) {
      clearRun();
      ui().setPlay({ state: "idle", note: "That run is no longer on the server. Runs are kept for about ten minutes after their connection closes (thirty with an encounter open). Start a new one below." });
    } else ui().setPlay({ state: "idle", note: "Could not reach the simulator to rejoin your run. It may still be there: try “Rejoin run” again in a moment." });
    await showLayoutOnly(true);
    return;
  }
  // No simulator: replay the bundled fixture so the screen still works, and say so.
  const r = await api.rollout("fixture");
  if (gen !== generation) return;
  player = new ReplayPlayer([{ feed: feeds.a, rollout: r.data, origin: "fixture" }]);
  player.loop = true;
  player.setSpeed(ui().speed);
  player.start();
  ui().setPlay({ state: "fixture", note: "Simulator offline: replaying a recorded fixture. Knob changes are noted but not simulated." });
}

/** Select an entity as soon as it shows up in a snapshot (gives up after a few seconds). */
function selectWhenPresent(sel: { kind: string; id: string | number }, gen: number) {
  const started = Date.now();
  const tryNow = () => {
    if (gen !== generation) return true;
    const snap = feeds.a.getState().snap;
    if (!snap) return false;
    const there = sel.kind === "patient" ? snap.patients.id.includes(Number(sel.id)) : sel.kind === "staff" ? snap.staff.id.includes(String(sel.id)) : true;
    if (there) {
      ui().select({ kind: sel.kind as import("./types").SelKind, id: sel.kind === "patient" ? Number(sel.id) : sel.id, feed: "a" });
      if (sel.kind === "patient") useUI.setState({ listTab: "patients" });
      return true;
    }
    if (Date.now() - started > 6000) {
      if (sel.kind === "patient") ui().toast(`Patient P-${String(sel.id).padStart(6, "0")} has left the hospital.`, "info");
      return true;
    }
    return false;
  };
  if (tryNow()) return;
  const unsub = feeds.a.subscribe(() => {
    if (tryNow()) unsub();
  });
}

const PLAYABLE_STATES = new Set(["waiting_triage", "in_triage", "waiting_bay", "waiting_provider", "with_provider"]);
/**
 * Can this patient's clinician encounter be played right now? Only in a live run. The server's list (`hour.playable`)
 * is used when it sends one; otherwise the patient must not have finished with the provider yet.
 */
export function isPlayable(f: FeedState, patientIdx: number): boolean {
  if (f.origin !== "live" || !f.header?.live || !f.snap || patientIdx < 0) return false;
  const id = f.snap.patients.id[patientIdx];
  // The server's list arrives once a simulated hour and patients move on faster than that, so a listed patient must
  // also still be in a state before the end of the provider visit.
  const early = PLAYABLE_STATES.has(f.header.enums.patient_state[f.snap.patients.state[patientIdx]] ?? "");
  return f.playable ? early && f.playable.has(id) : early;
}
/** Why not, in words (used when the per-patient route has not said). */
export function notPlayableReason(f: FeedState, patientIdx: number): string {
  if (f.origin !== "live" || !f.header?.live) return "Encounters are played from a live run. Start one in Play, then pick a patient who has not seen the provider yet.";
  if (patientIdx < 0 || !f.snap) return "This patient is not in the hospital at this moment.";
  const st = f.header.enums.patient_state[f.snap.patients.state[patientIdx]] ?? "";
  if (st === "in_ward" || st === "boarding") return "This patient has already been seen and admitted. Pick someone who is still waiting or with the provider.";
  if (st === "exited") return "This patient has left the hospital.";
  return "This patient's encounter with the provider has already happened. Pick someone who is still waiting or with the provider.";
}

export const playCtl = {
  /** Pause the run before stepping into an encounter, so the patient cannot move on meanwhile. */
  pauseForEncounter() {
    if (!liveSim) return;
    liveSim.send({ type: "pause" });
    useUI.setState({ paused: true });
  },
  /**
   * Pause the hospital, ask the server who can be played at this instant, and select one of them. Pausing first
   * matters: at speed, a provider visit lasts a few real seconds and the patient would be gone before the click lands.
   */
  async findPlayable(): Promise<boolean> {
    if (!liveSim) return false;
    liveSim.send({ type: "pause" });
    useUI.setState({ paused: true });
    await new Promise((r) => setTimeout(r, 250)); // let the last snapshot before the pause arrive
    await refreshPlayable();
    const f = feeds.a.getState();
    const snap = f.snap;
    if (!snap) return false;
    const en = f.header?.enums.patient_state ?? [];
    // someone already in a bay waiting for the provider is the best pick; then with the provider; then earlier in the pathway
    const want = ["waiting_provider", "with_provider", "waiting_bay", "in_triage", "waiting_triage"];
    let best = -1;
    let bestRank = 99;
    const child = f.header?.enums.age_band.indexOf("age_0_17") ?? -1;
    for (let i = 0; i < snap.patients.id.length; i++) {
      if (!isPlayable(f, i)) continue;
      const r = want.indexOf(en[snap.patients.state[i]] ?? "");
      // adults first: the encounter engine refuses very young children and adult-only teaching cases for children
      const rank = (r < 0 ? 50 : r) + (snap.patients.age_band[i] === child ? 10 : 0);
      if (rank < bestRank || (rank === bestRank && best >= 0 && snap.patients.state_min[i] > snap.patients.state_min[best])) {
        best = i;
        bestRank = rank;
      }
    }
    if (best < 0) {
      useUI.setState({ paused: false });
      ui().toast("Nobody is waiting for or with a provider right now. Let the clock run for a moment and try again.", "warn");
      return false;
    }
    ui().select({ kind: "patient", id: snap.patients.id[best], feed: "a" });
    useUI.setState({ listTab: "patients" });
    ui().toast("Paused the hospital so this patient stays put. Play their encounter from the panel on the right, or press play to carry on.", "info");
    return true;
  },
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
    clearRun();
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
