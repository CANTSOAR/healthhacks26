// Interface state shared by all panels (the simulation data itself lives in feeds, see feed.ts).
import { create } from "zustand";
import type { Source } from "./api";
import type { Hospital, ManagerInfo, Results, RolloutListItem, Scenario, Selection, ServiceStatus } from "./types";

export type Mode = "play" | "watch" | "compare" | "tradeoff";
export type ListTab = "beds" | "staff" | "patients";
export type PlayState = "idle" | "connecting" | "live" | "fixture" | "ended";
export interface Toast {
  id: number;
  text: string;
  tone: "info" | "warn" | "error";
}
export type CamCmd = { type: "zoom" | "rotate" | "reset" | "tilt"; amount: number; n: number };

export interface UIState {
  mode: Mode;
  selection: Selection | null;
  hover: Selection | null;
  listTab: ListTab;
  speed: number; // ticks per second
  paused: boolean;
  /** null until the first status check finishes */
  online: boolean | null;
  status: ServiceStatus | null;
  scenarios: Scenario[];
  hospitals: Hospital[];
  managers: ManagerInfo[];
  rollouts: RolloutListItem[];
  listsSource: Source | null;
  results: Results | null;
  /** Watch: playback reached the end of a recorded window (next = another window follows) */
  windowEnd: null | { next: boolean };
  /** Watch: an hour the chart cursor was moved to that has no 3D recording */
  chartCursor: number | null;
  scenarioId: string;
  hospitalId: string;
  watchId: string | null;
  compareIds: [string | null, string | null];
  /** live Compare: two sockets on the same scenario and seed */
  compareLive: "off" | "connecting" | "live" | "ended";
  compareManagers: [string, string];
  compareNote: string | null;
  loading: string | null;
  /** a live run of this tab is remembered and can be rejoined */
  hasSavedRun: boolean;
  play: {
    state: PlayState;
    manager: string;
    seed: number;
    requested: Record<string, number>;
    posted: null | { where: Source; at: number };
    note: string | null;
  };
  drawer: null | "controls" | "list" | "inspector";
  /** guided demo: which step is showing (null = not running) */
  tour: null | { index: number; busy: boolean };
  toasts: Toast[];
  toast: (text: string, tone?: Toast["tone"]) => void;
  dismissToast: (id: number) => void;
  camCmd: CamCmd | null;
  select: (s: Selection | null) => void;
  set: (p: Partial<UIState>) => void;
  setPlay: (p: Partial<UIState["play"]>) => void;
  cam: (type: CamCmd["type"], amount: number) => void;
}

let camN = 0;
let toastN = 0;
export const useUI = create<UIState>((set) => ({
  mode: "watch",
  selection: null,
  hover: null,
  listTab: "beds",
  speed: 4,
  paused: false,
  online: null,
  status: null,
  scenarios: [],
  hospitals: [],
  managers: [],
  rollouts: [],
  listsSource: null,
  results: null,
  windowEnd: null,
  chartCursor: null,
  scenarioId: "normal_week",
  hospitalId: "rwjuh_nb",
  watchId: null,
  compareIds: [null, null],
  compareLive: "off",
  compareManagers: ["fixed", "rule_based"],
  compareNote: null,
  loading: null,
  hasSavedRun: false,
  play: { state: "idle", manager: "human", seed: 7, requested: {}, posted: null, note: null },
  drawer: null,
  tour: null,
  toasts: [],
  toast: (text, tone = "info") => {
    const id = ++toastN;
    set((s) => ({ toasts: [...s.toasts.filter((t) => t.text !== text), { id, text, tone }].slice(-4) }));
    if (typeof window !== "undefined") window.setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 6500);
  },
  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  camCmd: null,
  select: (selection) => set((s) => ({ selection, drawer: selection && s.drawer !== "inspector" ? "inspector" : s.drawer })),
  set: (p) => set(p),
  setPlay: (p) => set((s) => ({ play: { ...s.play, ...p } })),
  cam: (type, amount) => set({ camCmd: { type, amount, n: ++camN } }),
}));

/** Ticks per second. The last entry asks the server for as fast as it can go (it skips snapshots above ~30 per second). */
export const SPEEDS = [1, 4, 12, 48, 600];
export const speedLabel = (v: number) => (v >= 600 ? "Max" : `${v}×`);
