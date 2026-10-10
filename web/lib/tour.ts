// The guided demo: the six steps of the README's demo, each one a scripted state of the real app.
// A step only runs with managers and rollouts that exist right now; otherwise it is skipped and says why.
// Captions describe what to look at. The only numbers in them are the held-out comparison of a learned manager, which
// lib/story.ts composes from the results table (margin, interval, and the wait, walk-outs and deaths that came with it).
import { enter } from "./nav";
import { loadLists, startLiveCompare, startPlay, transport } from "./session";
import { useUI } from "./ui";
import type { ManagerInfo, RolloutListItem } from "./types";
import { heldOutVerdict, namedManager } from "./story";

export interface TourStep {
  title: string;
  caption: string;
  /** set when the step cannot run right now */
  skip?: string;
  run: () => Promise<void>;
}

const ui = () => useUI.getState();
const named = namedManager;
/** The held-out verdict of a learned manager, with its margin and what came with it (nothing when there is no comparison). */
const story = (m: ManagerInfo | null | undefined, scenario: string) => (m ? heldOutVerdict(m.id, scenario) : "");
const sp = (s: string) => (s ? ` ${s}` : "");

/** A manager for an objective: a learned agent if one is available, otherwise a tuned heuristic. */
function managerFor(test: RegExp): ManagerInfo | null {
  const ok = ui().managers.filter((m) => m.kind !== "human" && m.available !== false && test.test(`${m.objective ?? ""} ${m.id}`));
  return ok.find((m) => m.kind === "learned") ?? ok.find((m) => m.kind === "tuned_heuristic") ?? ok[0] ?? null;
}
const rolloutOf = (managerId: string | undefined, scenario: string): RolloutListItem | undefined =>
  managerId ? ui().rollouts.find((r) => r.has_segments && r.manager.id === managerId && r.scenario === scenario) : undefined;
const COST = /min_cost/;
const WAIT = /min_wait/;
const CONSTRAINED = /p95|s\.t\./;

function normalScenario(): string {
  const s = ui().scenarios;
  return (s.find((x) => x.id === "normal_week") ?? s.find((x) => /normal/i.test(x.id)) ?? s[0])?.id ?? "normal_week";
}
function surgeScenario(): string | null {
  return ui().scenarios.find((x) => /flu|surge/i.test(x.id))?.id ?? null;
}

export function buildTour(): TourStep[] {
  const s = ui();
  const online = s.online === true;
  const normal = normalScenario();
  const surge = surgeScenario();
  const cost = managerFor(COST);
  const wait = managerFor(WAIT);
  const con = managerFor(CONSTRAINED);
  const baseline = s.rollouts.find((r) => r.has_segments && r.scenario === normal && (r.manager.kind === "fixed" || r.manager.kind === "rule_based")) ?? s.rollouts.find((r) => r.has_segments && r.scenario === normal) ?? s.rollouts.find((r) => r.has_segments);
  const costR = rolloutOf(cost?.id, normal);
  const waitR = rolloutOf(wait?.id, normal);
  const conR = rolloutOf(con?.id, normal);
  const surgeA = surge ? rolloutOf(cost?.id, surge) : undefined;
  const surgeB = surge ? (rolloutOf(wait?.id, surge) ?? rolloutOf(con?.id, surge)) : undefined;
  const surgeBManager = surge && rolloutOf(wait?.id, surge) ? wait : con;

  return [
    {
      title: "A normal day",
      caption: baseline
        ? `The hospital on an ordinary weekday, run by ${named(baseline.manager)}. Patients are coloured by acuity, staff by role. Click anyone, or any bed, to see their state and where every number behind them comes from.`
        : "The hospital on an ordinary weekday.",
      skip: baseline ? undefined : "no recorded rollout is available",
      run: async () => {
        useUI.setState({ scenarioId: normal, speed: 4, paused: false, watchId: baseline!.rollout_id });
        await enter("watch");
        // a Tuesday mid-morning, or the nearest recorded moment to it
        transport.seekTick(288 + 120, true);
      },
    },
    {
      title: "Hand it to a cost-tuned manager",
      caption: cost
        ? online
          ? `${named(cost)} now runs the hospital live, at full speed. Its objective is cost.${sp(story(cost, normal))} Its decisions appear in the feed as it makes them; the cards show the wait and cost that result.`
          : `A recorded run of ${named(cost)}, whose objective is cost.${sp(story(cost, normal))} Its decisions are in the feed; the cards show the wait and cost that result.`
        : "",
      skip: !cost ? "no cost-tuned manager is available yet" : !online && !costR ? "the simulator is offline and no recording of a cost-tuned manager exists" : undefined,
      run: async () => {
        if (online) {
          useUI.setState({ scenarioId: normal, speed: 600, paused: false });
          await enter("play");
          ui().setPlay({ manager: cost!.id });
          await startPlay();
        } else {
          useUI.setState({ scenarioId: normal, speed: 12, paused: false, watchId: costR!.rollout_id });
          await enter("watch");
        }
      },
    },
    {
      title: "Same patients, wait-tuned manager",
      caption: cost && wait ? `Side by side on the same seed, so both face the same arrivals: A is ${named(cost)}, B is ${named(wait)}. The table gives each side's totals for the episode and the difference; rows that are close mean the two did not differ much on that measure. What each manager is, and how it did against its tuned heuristic on held-out seeds, is in the panel on the right.` : "",
      skip: !cost || !wait ? "needs both a cost-tuned and a wait-tuned manager" : !(costR && waitR) && !online ? "no recordings of both managers, and the simulator is offline" : undefined,
      run: async () => {
        useUI.setState({ scenarioId: normal, speed: 12, paused: false });
        if (costR && waitR) {
          useUI.setState({ compareIds: [costR.rollout_id, waitR.rollout_id] });
          await enter("compare");
        } else {
          useUI.setState({ compareManagers: [cost!.id, wait!.id], speed: 48 });
          await enter("compare");
          await startLiveCompare(cost!.id, wait!.id);
        }
      },
    },
    {
      title: "A constrained manager",
      caption: con ? `${named(con)}: its objective is the lowest cost that still keeps the 95th-percentile wait under a limit.${sp(story(con, normal))} Its decisions are listed as they happen.` : "",
      skip: !con ? "no constrained manager is available yet" : !conR ? "no recording of the constrained manager exists yet" : undefined,
      run: async () => {
        useUI.setState({ scenarioId: normal, speed: 12, paused: false, watchId: conR!.rollout_id });
        await enter("watch");
      },
    },
    {
      title: "Throw a flu surge at them",
      caption: surgeA && surgeB && cost && surgeBManager ? `The same comparison under a flu surge: A is ${named(cost)}, B is ${named(surgeBManager)}. The table shows how each one's waits and costs held up.` : "",
      skip: !surge ? "no flu-surge scenario is defined" : !(surgeA && surgeB) ? "no flu-surge recordings of two managers exist yet" : undefined,
      run: async () => {
        useUI.setState({ scenarioId: surge!, speed: 12, paused: false, compareIds: [surgeA!.rollout_id, surgeB!.rollout_id] });
        await enter("compare");
      },
    },
    {
      title: "The trade-off",
      caption: "Every evaluated manager, cost against wait, with intervals across held-out seeds. Marks that sit on top of each other did not differ: a numbered badge says how many share a spot, and clicking it steps through them. Click one for its details and its held-out comparison. Your own Play run appears here too, flagged if it was too short to compare.",
      run: async () => {
        useUI.setState({ scenarioId: normal });
        await enter("tradeoff");
      },
    },
  ];
}

let steps: TourStep[] = [];
export const tourSteps = () => steps;

async function go(index: number) {
  await loadLists().catch(() => undefined);
  steps = buildTour();
  const step = steps[index];
  if (!step || step.skip) return;
  useUI.setState({ tour: { index, busy: true }, selection: null });
  try {
    await step.run();
  } catch (e) {
    ui().toast(`This step could not be shown: ${String((e as Error)?.message ?? e)}`, "error");
  } finally {
    if (ui().tour?.index === index) useUI.setState({ tour: { index, busy: false } });
  }
}

export const tour = {
  async start() {
    await loadLists().catch(() => undefined);
    steps = buildTour();
    const first = steps.findIndex((s) => !s.skip);
    if (first < 0) return ui().toast("Nothing to show yet: no rollouts or managers are available.", "warn");
    await go(first);
  },
  async next() {
    const t = ui().tour;
    if (!t) return;
    steps = buildTour();
    for (let i = t.index + 1; i < steps.length; i++) if (!steps[i].skip) return go(i);
  },
  async back() {
    const t = ui().tour;
    if (!t) return;
    steps = buildTour();
    for (let i = t.index - 1; i >= 0; i--) if (!steps[i].skip) return go(i);
  },
  /** Leave the app where it is, at a calm speed. */
  exit() {
    useUI.setState({ tour: null, speed: Math.min(ui().speed, 12) });
  },
  hasNext: () => steps.some((s, i) => i > (ui().tour?.index ?? 0) && !s.skip),
  hasBack: () => steps.some((s, i) => i < (ui().tour?.index ?? 0) && !s.skip),
};
