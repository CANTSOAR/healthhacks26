// The guided demo: a short walk through the product, each step a scripted state of the real app.
// A step runs only with the plans and recordings the API lists right now; a step that cannot run is left out
// altogether, so the card never talks about something that is not there.
import { enter } from "./nav";
import { loadLists, transport } from "./session";
import { useUI, type Mode } from "./ui";
import type { RolloutListItem } from "./types";

export interface TourStep {
  title: string;
  caption: string;
  /** the mode this step shows: leaving it by hand ends the tour */
  mode: Mode;
  run: () => Promise<void>;
}

const ui = () => useUI.getState();

/** Plans to show as "the better plan", best first: the recommended one, then the other tuned plans. */
const PLAN_ORDER = ["tuned_same_budget", "tuned_min_wait", "tuned_balanced", "tuned_max_margin", "tuned_min_cost"];
const PLAN_WORDS: Record<string, string> = {
  tuned_same_budget: "the recommended plan (same budget, better flow)",
  tuned_min_wait: "the plan tuned for the shortest waits",
  tuned_balanced: "the balanced plan",
  tuned_max_margin: "the plan tuned for the best margin",
  tuned_min_cost: "the plan tuned for the lowest cost",
};

function scenarioIds() {
  const s = ui().scenarios;
  const normal = (s.find((x) => x.id === "normal_week") ?? s.find((x) => /normal/i.test(x.id)) ?? s[0])?.id ?? "normal_week";
  const surge = s.find((x) => /flu|surge/i.test(x.id))?.id ?? "flu_surge";
  return { normal, surge };
}

/** Current practice and a better plan, recorded on the same scenario and the same patients. */
function pair(scenario: string): { base: RolloutListItem; plan: RolloutListItem } | null {
  const usable = ui().rollouts.filter((r) => r.has_segments && r.scenario === scenario);
  const base = usable.find((r) => r.manager.id === "fixed") ?? usable.find((r) => r.manager.kind === "fixed");
  if (!base) return null;
  for (const id of PLAN_ORDER) {
    const plan = usable.find((r) => r.manager.id === id && r.seed === base.seed);
    if (plan) return { base, plan };
  }
  return null;
}
const words = (r: RolloutListItem) => PLAN_WORDS[r.manager.id] ?? "a tuned plan";

export function buildTour(): TourStep[] {
  const s = ui();
  const { normal, surge } = scenarioIds();
  const usable = s.rollouts.filter((r) => r.has_segments);
  const baseline = usable.find((r) => r.scenario === normal && r.manager.id === "fixed") ?? usable.find((r) => r.scenario === normal && r.manager.kind === "fixed") ?? usable.find((r) => r.scenario === normal) ?? usable[0];
  const isCurrent = baseline?.manager.kind === "fixed";
  const day = pair(normal);
  const flu = pair(surge);
  const steps: (TourStep | null)[] = [
    baseline
      ? {
          title: isCurrent ? "A normal day under current practice" : "A normal day in the hospital",
          mode: "watch",
          caption: `This is the twin on an ordinary weekday${isCurrent ? ", staffed the way the hospital runs today as far as public data can tell" : ""}. Patients are colored by how urgent they are, staff by role. Click anyone, or any bed, to see their state and where every number behind them comes from.`,
          run: async () => {
            useUI.setState({ scenarioId: baseline.scenario, speed: 4, paused: false, watchId: baseline.rollout_id });
            await enter("watch");
            // a Tuesday mid-morning, or the nearest recorded moment to it
            transport.seekTick(288 + 120, true);
          },
        }
      : null,
    {
      title: "Pick a goal and let it search",
      mode: "optimize",
      caption: "This is where you tell the system what matters. Start from an example or mark any measure to maximize or minimize, put them in order, and press Find a plan. A search takes four to five minutes; earlier searches are listed at the bottom of the page and open straight away.",
      run: async () => {
        await enter("optimize");
      },
    },
    day
      ? {
          title: "The plan at work",
          mode: "watch",
          caption: `The same hospital and the same kind of week, now run by ${words(day.plan)}. Each staffing and capacity decision appears in the feed as it is made; the cards show the waits and costs that follow. No clinical decision is part of it.`,
          run: async () => {
            useUI.setState({ scenarioId: normal, speed: 12, paused: false, watchId: day.plan.rollout_id });
            await enter("watch");
          },
        }
      : null,
    day
      ? {
          title: "Same patients, two plans",
          mode: "compare",
          caption: `Side by side, facing exactly the same arrivals: A is current practice, B is ${words(day.plan)}. The table gives each side's totals and the difference. Rows that are close mean the two did not differ much on that measure.`,
          run: async () => {
            useUI.setState({ scenarioId: normal, speed: 12, paused: false, compareIds: [day.base.rollout_id, day.plan.rollout_id] });
            await enter("compare");
          },
        }
      : null,
    flu
      ? {
          title: "Now a flu surge",
          mode: "compare",
          caption: `The same comparison in a flu surge: A is current practice, B is ${words(flu.plan)}. A good plan should hold up when the week is not ordinary. The table shows how each side's waits and costs did.`,
          run: async () => {
            useUI.setState({ scenarioId: surge, speed: 12, paused: false, compareIds: [flu.base.rollout_id, flu.plan.rollout_id] });
            await enter("compare");
          },
        }
      : null,
    {
      title: "Every plan on one chart",
      mode: "tradeoff",
      caption: "Each mark is one plan, cost against wait, tested on fresh simulated patients. Marks that sit on top of each other did not differ. Click one for its details, or switch to Resources to see what one more provider, nurse, bay or scanner is worth.",
      run: async () => {
        useUI.setState({ scenarioId: normal });
        await enter("tradeoff");
      },
    },
  ];
  return steps.filter((x): x is TourStep => !!x);
}

let steps: TourStep[] = [];
export const tourSteps = () => steps;

async function go(index: number) {
  const step = steps[index];
  if (!step) return;
  useUI.setState({ tour: { index, busy: true }, selection: null });
  try {
    await step.run();
  } catch (e) {
    ui().toast(`This step could not be shown: ${String((e as Error)?.message ?? e)}`, "error");
  } finally {
    if (ui().tour?.index === index) useUI.setState({ tour: { index, busy: false } });
  }
}

// The tour belongs to the step it is showing: going somewhere else by hand ends it, so its card never lingers over
// a page it is not describing.
if (typeof window !== "undefined") {
  useUI.subscribe((s, prev) => {
    if (!s.tour || s.tour.busy || s.mode === prev.mode) return;
    if (steps[s.tour.index]?.mode !== s.mode) useUI.setState({ tour: null });
  });
}

export const tour = {
  /** Only ever started by the visitor pressing "Demo tour". */
  async start() {
    await loadLists().catch(() => undefined);
    steps = buildTour();
    await go(0);
  },
  async next() {
    const t = ui().tour;
    if (t && t.index + 1 < steps.length) await go(t.index + 1);
  },
  async back() {
    const t = ui().tour;
    if (t && t.index > 0) await go(t.index - 1);
  },
  /** Leave the app where it is, at a calm speed. */
  exit() {
    useUI.setState({ tour: null, speed: Math.min(ui().speed, 12) });
  },
  hasNext: () => (ui().tour?.index ?? 0) + 1 < steps.length,
  hasBack: () => (ui().tour?.index ?? 0) > 0,
};
