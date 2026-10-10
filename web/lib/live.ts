// Client for WS /ws/sim (contracts/api.md). Writes into a feed.
import { wsBase } from "./api";
import { pushSnapshot, resetFeed, setLayout, type Feed } from "./feed";
import type { ManagerInfo, ServerMsg, SimEvent } from "./types";

export interface StartParams {
  scenario: string;
  seed: number;
  manager: string; // "human" or a manager id
  speed: number; // ticks per second
  hospital_id: string;
}
export type LiveState = "connecting" | "open" | "closed" | "failed";

export class LiveSim {
  private ws: WebSocket | null = null;
  private lastAt = 0;
  private ema = 0;
  state: LiveState = "connecting";
  gotHeader = false;
  private finalWaiters: (() => void)[] = [];

  constructor(
    private feed: Feed,
    private params: StartParams,
    private on: {
      state: (s: LiveState) => void;
      summary?: (s: Record<string, number>) => void;
      events?: (e: SimEvent[]) => void;
      manager?: (m: ManagerInfo) => void;
      error?: (message: string) => void;
    },
  ) {}

  /** Resolves true once the server has sent its header; false when the socket cannot be opened in time. */
  connect(timeoutMs = 2500): Promise<boolean> {
    return new Promise((resolve) => {
      let settled = false;
      const done = (ok: boolean) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(ok);
      };
      const timer = setTimeout(() => {
        if (!this.gotHeader) {
          this.setState("failed");
          this.close();
          done(false);
        }
      }, timeoutMs);
      let ws: WebSocket;
      try {
        ws = new WebSocket(wsBase() + "/ws/sim");
      } catch {
        this.setState("failed");
        done(false);
        return;
      }
      this.ws = ws;
      ws.onopen = () => {
        resetFeed(this.feed);
        this.feed.setState({ origin: "live" });
        this.send({ type: "start", ...this.params });
      };
      ws.onerror = () => {
        if (!this.gotHeader) {
          this.setState("failed");
          done(false);
        }
      };
      ws.onclose = () => {
        if (this.state !== "failed") this.setState("closed");
        done(this.gotHeader);
      };
      ws.onmessage = (ev) => {
        let msg: ServerMsg;
        try {
          msg = JSON.parse(typeof ev.data === "string" ? ev.data : "") as ServerMsg;
        } catch {
          return;
        }
        this.handle(msg);
        if (msg.type === "header") {
          this.setState("open");
          done(true);
        }
      };
    });
  }

  private setState(s: LiveState) {
    this.state = s;
    this.on.state(s);
  }

  private handle(msg: ServerMsg) {
    const feed = this.feed;
    switch (msg.type) {
      case "header": {
        this.gotHeader = true;
        feed.setState((s) => ({
          origin: "live",
          header: {
            id: msg.run_id,
            live: true,
            manager: msg.manager,
            scenario: msg.scenario,
            seed: msg.seed,
            hospital_id: msg.hospital_id,
            tick_minutes: msg.tick_minutes ?? 5,
            enums: msg.enums,
            action_spec: msg.action_spec ?? [],
          },
          layout: msg.layout,
          layoutRev: s.layoutRev + 1,
          error: null,
        }));
        break;
      }
      case "snapshot": {
        const now = performance.now();
        const gap = this.lastAt ? now - this.lastAt : 1000 / Math.max(1, this.params.speed);
        this.lastAt = now;
        // smoothed arrival interval; a long gap (pause) must not stretch the glide
        this.ema = this.ema ? this.ema * 0.7 + Math.min(gap, 2000) * 0.3 : Math.min(gap, 2000);
        const prev = feed.getState().snap;
        const jump = !prev || Math.abs(msg.snapshot.t - prev.t) > 6;
        pushSnapshot(feed, msg.snapshot, Math.max(16, Math.min(2000, this.ema)), { record: true, jump });
        if (msg.snapshot.events?.length) this.on.events?.(msg.snapshot.events);
        break;
      }
      case "hour": {
        this.syncManager(msg as unknown as { manager?: string; manager_info?: ManagerInfo });
        // The server also sends `hour` as an immediate acknowledgement of action / manager / inject, with empty
        // metrics: it only updates the queued knobs and the mask, and must not add a point to the charts.
        if (msg.ack || !msg.metrics || Object.keys(msg.metrics).length === 0) {
          feed.setState((s) => ({ pending: msg.pending ?? s.pending, mask: msg.mask ?? s.mask }));
          break;
        }
        feed.setState((s) => {
          const hourly: Record<string, number[]> = { ...s.hourly };
          for (const [k, v] of Object.entries(msg.metrics ?? {})) hourly[k] = (hourly[k] ?? []).concat([v]);
          // the message at tick t closes the hour that ended there
          const first = !Object.keys(s.hourly).length;
          return { hourly, hour0: first ? Math.max(0, Math.round(msg.t / 12) - 1) : s.hour0, pending: msg.pending ?? s.pending, mask: msg.mask ?? s.mask };
        });
        break;
      }
      case "layout":
        setLayout(feed, msg.layout);
        break;
      case "summary":
        feed.setState({ summary: msg.summary });
        this.on.summary?.(msg.summary);
        if (msg.final) this.finalWaiters.splice(0).forEach((f) => f());
        break;
      case "error":
        feed.setState({ error: msg.message });
        this.on.error?.(msg.message);
        break;
      default:
        break;
    }
  }

  /** `hour` messages say who is in charge (server extra: `manager`, and `manager_info` after a hand-over). */
  private syncManager(m: { manager?: string; manager_info?: ManagerInfo }) {
    const h = this.feed.getState().header;
    if (!h || !m.manager || (h.manager.id === m.manager && !m.manager_info)) return;
    const info: ManagerInfo = m.manager_info ?? { id: m.manager, kind: m.manager === "human" ? "human" : h.manager.kind, label: m.manager === "human" ? "You" : m.manager };
    if (info.id === h.manager.id && info.label === h.manager.label) return;
    this.feed.setState({ header: { ...h, manager: info } });
    this.on.manager?.(info);
  }

  send(msg: Record<string, unknown>) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }
  /** Send `stop` and wait for the summary marked final (the server keeps the socket open afterwards). */
  stop(timeoutMs = 2500): Promise<void> {
    return new Promise((resolve) => {
      const t = setTimeout(resolve, timeoutMs);
      this.finalWaiters.push(() => {
        clearTimeout(t);
        resolve();
      });
      this.send({ type: "stop" });
    });
  }
  setSpeed(tps: number) {
    this.params.speed = tps;
    this.ema = 0;
    this.send({ type: "speed", ticks_per_second: tps });
  }
  close() {
    try {
      this.ws?.close();
    } catch {
      /* already closed */
    }
    this.ws = null;
  }
}
