"use client";
import { useCallback, useEffect, useRef } from "react";
import { useNarrow } from "@/lib/hooks";
import { enter } from "@/lib/nav";
import { loadLists, refreshStatus, showLayoutOnly, stopAll } from "@/lib/session";
import { useUI, type Mode } from "@/lib/ui";
import { CompareView } from "./modes/CompareView";
import { OpsView } from "./modes/OpsView";
import { TradeoffView } from "./modes/TradeoffView";
import { Toasts } from "./ui/Toasts";
import { TourCard } from "./ui/Tour";
import { TopBar } from "./ui/TopBar";

const MODES: Mode[] = ["play", "watch", "compare", "tradeoff"];

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
  const top = (
    <>
      <TopBar narrow={narrow} onMode={onMode} />
      <div className="pointer-events-none fixed left-1/2 top-[76px] z-[60] flex w-[min(92vw,460px)] -translate-x-1/2 flex-col gap-2 max-[900px]:top-[120px]">
        <TourCard />
        <Toasts />
      </div>
    </>
  );

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
