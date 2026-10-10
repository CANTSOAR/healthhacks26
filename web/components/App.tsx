"use client";
import { useCallback, useEffect, useRef } from "react";
import { useNarrow } from "@/lib/hooks";
import { feeds, loadLists, openCompare, openWatch, refreshStatus, showLayoutOnly, stopAll } from "@/lib/session";
import { useUI, type Mode } from "@/lib/ui";
import { CompareView } from "./modes/CompareView";
import { OpsView } from "./modes/OpsView";
import { TradeoffView } from "./modes/TradeoffView";
import { TopBar } from "./ui/TopBar";

const MODES: Mode[] = ["play", "watch", "compare", "tradeoff"];

function pickPair(): [string, string] | null {
  const { rollouts, compareIds } = useUI.getState();
  const usable = rollouts.filter((r) => r.has_segments);
  if (!usable.length) return null;
  const a = usable.find((r) => r.rollout_id === compareIds[0]) ?? usable[0];
  // prefer a second manager on the same scenario and seed
  const b = usable.find((r) => r.rollout_id === compareIds[1]) ?? usable.find((r) => r.rollout_id !== a.rollout_id && r.scenario === a.scenario && r.seed === a.seed) ?? usable.find((r) => r.rollout_id !== a.rollout_id) ?? a;
  return [a.rollout_id, b.rollout_id];
}

/** Load whatever the mode needs into the feeds. */
async function enter(mode: Mode) {
  const s = useUI.getState();
  s.set({ mode, selection: null, hover: null, drawer: null });
  const url = new URL(window.location.href);
  url.searchParams.set("mode", mode);
  window.history.replaceState(null, "", url);
  // the server re-reads managers and rollouts from disk as training lands: refresh the lists on every mode change
  await loadLists().catch(() => undefined);
  if (mode === "watch") {
    const id = s.watchId ?? s.rollouts.find((r) => r.has_segments)?.rollout_id ?? s.rollouts[0]?.rollout_id ?? "fixture";
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

export default function App() {
  const narrow = useNarrow();
  const mode = useUI((s) => s.mode);
  const hospitalId = useUI((s) => s.hospitalId);
  const booted = useRef(false);

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    const q = new URLSearchParams(window.location.search);
    const m = q.get("mode") as Mode | null;
    const initial: Mode = m && MODES.includes(m) ? m : "watch";
    useUI.setState({ mode: initial });
    const w = q.get("rollout");
    if (w) useUI.setState({ watchId: w });
    const a = q.get("a");
    const b = q.get("b");
    if (a && b) useUI.setState({ compareIds: [a, b] });
    void (async () => {
      await refreshStatus();
      await loadLists();
      await enter(initial);
    })();
    const timer = setInterval(() => void refreshStatus(), 15000);
    return () => {
      clearInterval(timer);
      stopAll();
    };
  }, []);

  // switching hospital redraws the building when nothing is running (Play before a run starts)
  useEffect(() => {
    if (!booted.current) return;
    const s = useUI.getState();
    if (s.mode === "play" && (s.play.state === "idle" || s.play.state === "ended")) void showLayoutOnly();
  }, [hospitalId]);

  const onMode = useCallback((m: Mode) => void enter(m), []);
  const top = <TopBar narrow={narrow} onMode={onMode} />;

  if (mode === "compare") return <CompareView narrow={narrow} top={top} />;
  if (mode === "tradeoff")
    return (
      <TradeoffView
        narrow={narrow}
        top={top}
        onWatch={(id) => {
          useUI.setState({ watchId: id });
          void enter("watch");
        }}
        onCompare={(a, b) => {
          useUI.setState({ compareIds: [a, b] });
          void enter("compare");
        }}
      />
    );
  return <OpsView narrow={narrow} top={top} />;
}
