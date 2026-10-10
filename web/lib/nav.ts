// Mode navigation: loads whatever a mode needs into the feeds. Used by the top bar and by the demo tour.
import { feeds, loadLists, openCompare, openWatch, showLayoutOnly } from "./session";
import { useUI, type Mode } from "./ui";

function pickPair(): [string, string] | null {
  const { rollouts, compareIds } = useUI.getState();
  const { scenarioId } = useUI.getState();
  const usable = rollouts.filter((r) => r.has_segments);
  if (!usable.length) return null;
  // start from the scenario chosen in the top bar when a rollout exists for it
  const a = usable.find((r) => r.rollout_id === compareIds[0]) ?? usable.find((r) => r.scenario === scenarioId) ?? usable[0];
  // prefer a second manager on the same scenario and seed
  const b = usable.find((r) => r.rollout_id === compareIds[1]) ?? usable.find((r) => r.rollout_id !== a.rollout_id && r.scenario === a.scenario && r.seed === a.seed) ?? usable.find((r) => r.rollout_id !== a.rollout_id) ?? a;
  return [a.rollout_id, b.rollout_id];
}

/** Load whatever the mode needs into the feeds. */
export async function enter(mode: Mode) {
  const s = useUI.getState();
  s.set({ mode, selection: null, hover: null, drawer: null });
  const url = new URL(window.location.href);
  url.searchParams.set("mode", mode);
  window.history.replaceState(null, "", url);
  // the server re-reads managers and rollouts from disk as training lands: refresh the lists on every mode change
  await loadLists().catch(() => undefined);
  if (mode === "watch") {
    const now = useUI.getState();
    const known = now.rollouts.some((r) => r.rollout_id === now.watchId) ? now.watchId : null;
    const id = known ?? now.rollouts.find((r) => r.has_segments && r.scenario === now.scenarioId)?.rollout_id ?? now.rollouts.find((r) => r.has_segments)?.rollout_id ?? now.rollouts[0]?.rollout_id ?? "fixture";
    await openWatch(id);
  } else if (mode === "compare") {
    const pair = pickPair() ?? ["fixture", "fixture_b"];
    await openCompare(pair[0], pair[1]);
  } else if (mode === "play") {
    s.setPlay({ state: "idle", note: null, posted: null, requested: {} });
    await showLayoutOnly();
  } else if (mode === "tradeoff") {
    if (!feeds.a.getState().layout) await showLayoutOnly();
  }
}

