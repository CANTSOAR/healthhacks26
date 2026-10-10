// Interface state shared by all panels (the simulation data itself lives in feeds, see feed.ts).
import { create } from "zustand";
import type { Source } from "./api";
import type { Hospital, ManagerInfo, RolloutListItem, Scenario, Selection, ServiceStatus } from "./types";

export type Mode = "play" | "watch" | "compare" | "tradeoff";
export type ListTab = "beds" | "staff" | "patients";
export type PlayState = "idle" | "connecting" | "live" | "fixture" | "ended";
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
  scenarioId: string;
  hospitalId: string;
  watchId: string | null;
  compareIds: [string | null, string | null];
  /** live Compare: two sockets on the same scenario and seed */
  compareLive: "off" | "connecting" | "live" | "ended";
  compareManagers: [string, string];
  compareNote: string | null;
  loading: string | null;
  play: {
    state: PlayState;
    manager: string;
    seed: number;
    requested: Record<string, number>;
    posted: null | { where: Source; at: number };
    note: string | null;
  };
  drawer: null | "controls" | "list" | "inspector";
  camCmd: CamCmd | null;
  select: (s: Selection | null) => void;
  set: (p: Partial<UIState>) => void;
  setPlay: (p: Partial<UIState["play"]>) => void;
  cam: (type: CamCmd["type"], amount: number) => void;
}

let camN = 0;
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
  scenarioId: "normal_week",
  hospitalId: "rwjuh_nb",
  watchId: null,
  compareIds: [null, null],
  compareLive: "off",
  compareManagers: ["fixed", "rule_based"],
  compareNote: null,
  loading: null,
  play: { state: "idle", manager: "human", seed: 7, requested: {}, posted: null, note: null },
  drawer: null,
  camCmd: null,
  select: (selection) => set((s) => ({ selection, drawer: selection && s.drawer !== "inspector" ? "inspector" : s.drawer })),
  set: (p) => set(p),
  setPlay: (p) => set((s) => ({ play: { ...s.play, ...p } })),
  cam: (type, amount) => set({ camCmd: { type, amount, n: ++camN } }),
}));

export const SPEEDS = [1, 4, 12, 48];
