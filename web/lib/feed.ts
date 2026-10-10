// A "feed" is one stream of simulator snapshots plus everything that describes it (header, layout, hourly
// metrics, decisions). The scene and every panel read from a feed; a replay player or the live websocket writes to it.
// Compare mode uses two feeds ("a" and "b").
import { createStore, type StoreApi } from "zustand/vanilla";
import type { ActionHead, Decision, Enums, Layout, ManagerInfo, SimEvent, Snapshot } from "./types";

export interface FeedHeader {
  id: string; // run_id (live) or rollout_id (replay)
  live: boolean;
  manager: ManagerInfo;
  scenario: string;
  seed: number;
  hospital_id: string;
  tick_minutes: number;
  days?: number;
  enums: Enums;
  action_spec: ActionHead[];
  summary?: Record<string, number>;
}
export interface JourneyEntry {
  s: number; // patient_state index
  t: number; // tick the state was first observed
  exit: number;
  room: number;
}
/** Where a feed's numbers come from. "fixture" = bundled placeholder data, shown because the server is unreachable. */
export type FeedOrigin = "none" | "live" | "replay" | "fixture";

export interface FeedState {
  key: string;
  origin: FeedOrigin;
  header: FeedHeader | null;
  layout: Layout | null;
  layoutRev: number;
  snap: Snapshot | null;
  /** performance.now() when `snap` arrived, and the expected gap to the next one: the scene interpolates across it. */
  snapAt: number;
  tickMs: number;
  /** bumps when the stream jumps (scrub, restart) so the scene snaps instead of gliding */
  jump: number;
  hourly: Record<string, number[]>;
  /** hour-of-episode that hourly[...][0] describes (0 for replays; live runs may join late) */
  hour0: number;
  decisions: Decision[];
  events: SimEvent[];
  journeys: Map<number, JourneyEntry[]>;
  /** the headline numbers about once a simulated hour, so a card can say how its own number moved */
  kpiHist: { t: number; wait: number; waiting: number }[];
  /** ids the server says can be played right now (null until it sends such a list) */
  playable: Set<number> | null;
  pending: Record<string, number>;
  mask: Record<string, boolean>;
  summary: Record<string, number> | null;
  /** tick ranges for which snapshots exist (replays) */
  segments: { start: number; end: number; label?: string }[];
  error: string | null;
}
export type Feed = StoreApi<FeedState>;

const empty = (key: string): FeedState => ({
  key,
  origin: "none",
  header: null,
  layout: null,
  layoutRev: 0,
  snap: null,
  snapAt: 0,
  tickMs: 1000,
  jump: 0,
  hourly: {},
  hour0: 0,
  decisions: [],
  events: [],
  journeys: new Map(),
  kpiHist: [],
  playable: null,
  pending: {},
  mask: {},
  summary: null,
  segments: [],
  error: null,
});

export function createFeed(key: string): Feed {
  return createStore<FeedState>(() => empty(key));
}
export function resetFeed(feed: Feed) {
  feed.setState(empty(feed.getState().key), true);
}

export function recordJourney(journeys: Map<number, JourneyEntry[]>, snap: Snapshot) {
  const p = snap.patients;
  for (let i = 0; i < p.id.length; i++) {
    const id = p.id[i];
    let j = journeys.get(id);
    if (!j) {
      j = [];
      journeys.set(id, j);
    }
    const last = j[j.length - 1];
    if (!last || last.s !== p.state[i]) {
      // first sighting: back-date to when the state began, as the snapshot reports it
      const t = last ? snap.t : snap.t - Math.round(p.state_min[i] / 5);
      j.push({ s: p.state[i], t, exit: p.exit[i], room: p.room[i] });
    } else if (p.exit[i] !== last.exit) last.exit = p.exit[i];
  }
}

/** Push one snapshot. `record` appends its decisions/events/journey steps (live streams; replays preload them). */
export function pushSnapshot(feed: Feed, snap: Snapshot, tickMs: number, opts: { record?: boolean; jump?: boolean } = {}) {
  const st = feed.getState();
  const patch: Partial<FeedState> = { snap, snapAt: performance.now(), tickMs };
  if (opts.jump) patch.jump = st.jump + 1;
  {
    const k = snap.kpis as Record<string, unknown>;
    const last = st.kpiHist[st.kpiHist.length - 1];
    if (last && (snap.t < last.t || snap.t - last.t > 60)) patch.kpiHist = [{ t: snap.t, wait: Number(k.wait_mean_min), waiting: Number(k.waiting_count) }];
    else if (!last || snap.t - last.t >= 6) patch.kpiHist = st.kpiHist.concat([{ t: snap.t, wait: Number(k.wait_mean_min), waiting: Number(k.waiting_count) }]).slice(-40);
  }
  if (opts.record) {
    if (snap.decisions?.length) patch.decisions = st.decisions.concat(snap.decisions).slice(-500);
    if (snap.events?.length) patch.events = st.events.concat(snap.events).slice(-500);
    recordJourney(st.journeys, snap);
  }
  feed.setState(patch);
}

export function setLayout(feed: Feed, layout: Layout) {
  feed.setState((s) => ({ layout, layoutRev: s.layoutRev + 1 }));
}

/** Index of a room id in the layout, cached per layout object. */
const roomIndexCache = new WeakMap<Layout, Map<string, number>>();
export function roomIndex(layout: Layout): Map<string, number> {
  let m = roomIndexCache.get(layout);
  if (!m) {
    m = new Map(layout.rooms.map((r, i) => [r.id, i]));
    roomIndexCache.set(layout, m);
  }
  return m;
}
