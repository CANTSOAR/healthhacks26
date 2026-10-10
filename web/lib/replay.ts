// Plays recorded rollouts into feeds. One player can drive several tracks on one clock (Compare mode).
import { pushSnapshot, recordJourney, resetFeed, setLayout, type Feed, type FeedOrigin, type JourneyEntry } from "./feed";
import type { Layout, Rollout, Snapshot } from "./types";

interface Track {
  feed: Feed;
  rollout: Rollout;
  frames: Snapshot[];
  layoutAt: { t: number; layout: Layout }[];
  layout: Layout | null;
}

export class ReplayPlayer {
  private tracks: Track[] = [];
  private ticks: number[] = [];
  private i = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private tps = 4;
  private playing = true;
  private every = 1;
  /** true = wrap around silently (offline fixture playback); false = stop at the end of each recorded window */
  loop = false;
  /** playback reached the end of a recorded window; `next` says whether another window follows */
  onWindowEnd: ((info: { next: boolean }) => void) | null = null;
  /** recorded windows as index ranges into the snapshot list (a rollout stores snapshots only for chosen stretches) */
  windows: { from: number; to: number }[] = [];

  constructor(pairs: { feed: Feed; rollout: Rollout; origin: FeedOrigin }[]) {
    for (const { feed, rollout, origin } of pairs) {
      const frames = rollout.segments.flatMap((s) => s.snapshots).sort((a, b) => a.t - b.t);
      const journeys = new Map<number, JourneyEntry[]>();
      for (const f of frames) recordJourney(journeys, f);
      const h = rollout.header;
      const layoutAt = [{ t: -Infinity, layout: h.layout }];
      for (const c of rollout.structural_changes ?? []) if (c.layout) layoutAt.push({ t: c.t_effective, layout: c.layout });
      layoutAt.sort((a, b) => a.t - b.t);
      resetFeed(feed);
      feed.setState({
        origin,
        header: {
          id: h.rollout_id,
          live: false,
          manager: h.manager,
          scenario: h.scenario,
          seed: h.seed,
          hospital_id: h.hospital_id,
          tick_minutes: h.tick_minutes,
          days: h.days,
          enums: h.enums,
          action_spec: h.action_spec,
          summary: h.summary,
        },
        layout: h.layout,
        layoutRev: 1,
        hourly: rollout.hourly,
        decisions: rollout.decisions,
        events: frames.flatMap((f) => f.events ?? []),
        journeys,
        summary: h.summary ?? null,
        segments: rollout.segments.map((s) => ({ start: s.start_t, end: s.start_t + (s.snapshots.length - 1) * s.every_ticks, label: s.label })),
      });
      this.tracks.push({ feed, rollout, frames, layoutAt, layout: h.layout });
    }
    this.ticks = this.tracks[0]?.frames.map((f) => f.t) ?? [];
    this.every = this.tracks[0]?.rollout.segments[0]?.every_ticks ?? 1;
    let from = 0;
    for (let k = 1; k <= this.ticks.length; k++) {
      if (k === this.ticks.length || this.ticks[k] - this.ticks[k - 1] > this.every * 3) {
        this.windows.push({ from, to: k - 1 });
        from = k;
      }
    }
    this.emit(true);
  }

  get length() {
    return this.ticks.length;
  }
  get index() {
    return this.i;
  }
  get tick() {
    return this.ticks[this.i] ?? 0;
  }

  private frameMs() {
    return (1000 * this.every) / Math.max(0.25, this.tps);
  }

  private emit(jump: boolean) {
    const t = this.ticks[this.i];
    if (t == null) return;
    for (const tr of this.tracks) {
      // nearest frame at or before t (tracks may be recorded on different grids)
      let lo = 0;
      let hi = tr.frames.length - 1;
      while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (tr.frames[mid].t <= t) lo = mid;
        else hi = mid - 1;
      }
      const frame = tr.frames[lo];
      if (!frame) continue;
      let layout = tr.layoutAt[0].layout;
      for (const l of tr.layoutAt) if (l.t <= t) layout = l.layout;
      if (layout !== tr.layout) {
        tr.layout = layout;
        setLayout(tr.feed, layout);
      }
      pushSnapshot(tr.feed, frame, this.frameMs(), { jump });
    }
  }

  private schedule() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    if (!this.playing || this.ticks.length < 2) return;
    this.timer = setTimeout(() => {
      const w = this.windowOf(this.i);
      if (w && this.i >= w.to) {
        if (!this.loop) {
          // do not run on into another day, or back to the start, as if nothing happened
          this.playing = false;
          this.onWindowEnd?.({ next: w.to < this.ticks.length - 1 });
          return;
        }
        this.i = w.to >= this.ticks.length - 1 ? 0 : this.i + 1;
        this.emit(true);
      } else {
        this.i++;
        this.emit(false);
      }
      this.schedule();
    }, this.frameMs());
  }

  start() {
    this.schedule();
  }
  setSpeed(tps: number) {
    this.tps = tps;
    this.schedule();
  }
  private windowOf(i: number) {
    return this.windows.find((w) => i >= w.from && i <= w.to) ?? null;
  }
  setPlaying(p: boolean) {
    // pressing play at the end of a window carries on with the next one (or starts again after the last)
    if (p && !this.playing) {
      const w = this.windowOf(this.i);
      if (w && this.i >= w.to && this.ticks.length > 1) {
        this.i = w.to >= this.ticks.length - 1 ? 0 : w.to + 1;
        this.emit(true);
      }
    }
    this.playing = p;
    this.schedule();
  }
  /** Start of the window after the current one (wraps to the first). */
  nextWindow() {
    const k = this.windows.findIndex((w) => this.i >= w.from && this.i <= w.to);
    const n = this.windows[(k + 1) % Math.max(1, this.windows.length)];
    if (n) this.seekIndex(n.from);
  }
  replayWindow() {
    const w = this.windowOf(this.i);
    if (w) this.seekIndex(w.from);
  }
  windowTicks() {
    return this.windows.map((w) => ({ start: this.ticks[w.from], end: this.ticks[w.to] }));
  }
  step() {
    if (this.i < this.ticks.length - 1) {
      this.i++;
      this.emit(false);
    }
  }
  seekIndex(i: number) {
    this.i = Math.max(0, Math.min(this.ticks.length - 1, Math.round(i)));
    this.emit(true);
    this.schedule();
  }
  /**
   * Jump to the recorded snapshot at tick t. Returns false, without moving, when t is outside every recorded window
   * (`snap` = true jumps to the nearest snapshot regardless).
   */
  seekTick(t: number, snap = false): boolean {
    let best = 0;
    let bd = Infinity;
    for (let k = 0; k < this.ticks.length; k++) {
      const d = Math.abs(this.ticks[k] - t);
      if (d < bd) {
        bd = d;
        best = k;
      }
    }
    if (!snap && bd > Math.max(12, this.every * 3)) return false;
    this.seekIndex(best);
    return true;
  }
  dispose() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.playing = false;
  }
}
