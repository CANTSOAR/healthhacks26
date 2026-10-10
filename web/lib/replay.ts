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
  loop = true;
  onEnd: (() => void) | null = null;

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
      if (this.i >= this.ticks.length - 1) {
        this.onEnd?.();
        if (!this.loop) {
          this.playing = false;
          return;
        }
        this.i = 0;
        this.emit(true);
      } else {
        const prev = this.ticks[this.i];
        this.i++;
        this.emit(this.ticks[this.i] - prev > this.every * 3);
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
  setPlaying(p: boolean) {
    this.playing = p;
    this.schedule();
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
  /** Jump to the recorded snapshot closest to tick t. */
  seekTick(t: number) {
    let best = 0;
    let bd = Infinity;
    for (let k = 0; k < this.ticks.length; k++) {
      const d = Math.abs(this.ticks[k] - t);
      if (d < bd) {
        bd = d;
        best = k;
      }
    }
    this.seekIndex(best);
  }
  dispose() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.playing = false;
  }
}
