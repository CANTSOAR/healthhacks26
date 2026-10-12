"use client";
import { useCallback, useEffect, useRef } from "react";
import { useNarrow } from "@/lib/hooks";
import { enter } from "@/lib/nav";
import { loadLists, openCompare, openWatch, refreshStatus, runIsLive, savedRun, saveRun, showLayoutOnly, stopAll } from "@/lib/session";
import { useUI, type Mode } from "@/lib/ui";
import { CompareView } from "./modes/CompareView";
import { OpsView } from "./modes/OpsView";
import { HomeView } from "./modes/HomeView";
import { OptimizeView } from "./modes/OptimizeView";
import { TradeoffView } from "./modes/TradeoffView";
import { FixtureBanner } from "./ui/FixtureBanner";
import { Toasts } from "./ui/Toasts";
import { TourCard } from "./ui/Tour";
import { TopBar } from "./ui/TopBar";

const MODES: Mode[] = ["play", "watch", "compare", "tradeoff", "optimize"];

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
    // /?run_id=..&patient_id=.. lands in Play on that run with that patient selected
    const backRun = q.get("run_id");
    const backPatient = q.get("patient_id");
    if (backRun) {
      saveRun({ run_id: backRun, selection: backPatient != null && backPatient !== "" ? { kind: "patient", id: Number(backPatient) } : null });
      const u = new URL(window.location.href);
      u.searchParams.delete("run_id");
      u.searchParams.delete("patient_id");
      window.history.replaceState(null, "", u);
    }
    useUI.setState({ hasSavedRun: !!savedRun() });
    // the bare address is the landing page; every ?mode= deep link opens that mode
    const initial: Mode = backRun ? "play" : m && MODES.includes(m) ? m : "home";
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
    // poll the server: slowly while it answers, quickly while it does not; when it comes back, reload what is on screen
    let wasOnline: boolean | null = null;
    const timer = setInterval(() => {
      const before = useUI.getState().online;
      if (before === false || Date.now() % 15000 < 4000)
        void refreshStatus().then((r) => {
          const nowOnline = r.source === "live";
          if (wasOnline === false && nowOnline) {
            useUI.getState().toast("The API is back. Reloading live data.", "info");
            const s = useUI.getState();
            if (!(s.mode === "play" && runIsLive())) void enter(s.mode);
          }
          wasOnline = nowOnline;
        });
    }, 4000);
    return () => {
      clearInterval(timer);
      stopAll();
    };
  }, []);

  // switching hospital redraws the building when nothing is running (Play before a run starts)
  useEffect(() => {
    if (!booted.current) return;
    const s = useUI.getState();
    if (s.mode === "play" && (s.play.state === "idle" || s.play.state === "ended") && !runIsLive()) void showLayoutOnly();
  }, [hospitalId]);

  // In Watch and Compare the scenario menu chooses among recordings of that scenario.
  const scenarioId = useUI((s) => s.scenarioId);
  useEffect(() => {
    if (!booted.current) return;
    const s = useUI.getState();
    const of = s.rollouts.filter((r) => r.has_segments && r.scenario === scenarioId);
    if (s.mode === "watch") {
      const cur = s.rollouts.find((r) => r.rollout_id === s.watchId);
      if (!cur || cur.scenario === scenarioId) return;
      const next = of.find((r) => r.manager.id === cur.manager.id) ?? of[0];
      if (next) void openWatch(next.rollout_id);
      else s.toast("There is no recording of that scenario yet. Still showing the previous one.", "warn");
    } else if (s.mode === "compare" && s.compareLive === "off") {
      const [a, b] = s.compareIds.map((id) => s.rollouts.find((r) => r.rollout_id === id));
      if (!a || !b || (a.scenario === scenarioId && b.scenario === scenarioId)) return;
      const na = of.find((r) => r.manager.id === a.manager.id) ?? of[0];
      const nb = of.find((r) => r.manager.id === b.manager.id && r.rollout_id !== na?.rollout_id) ?? of.find((r) => r.rollout_id !== na?.rollout_id);
      if (na && nb) void openCompare(na.rollout_id, nb.rollout_id);
      else s.toast("There are not two recordings of that scenario yet. Still showing the previous pair.", "warn");
    }
  }, [scenarioId]);

  const onMode = useCallback((m: Mode) => void enter(m), []);
  const tourOn = useUI((s) => !!s.tour);
  // The tour card floats over the 3D modes. On the Optimize page, which is a scrolling document, it sits in the flow
  // above the content so it never covers a control. The landing page has no tour card.
  const inlineTour = mode === "optimize";
  const top = (
    <>
      <TopBar narrow={narrow} onMode={onMode} />
      <FixtureBanner />
      {inlineTour && tourOn && (
        <div className="pointer-events-auto mx-auto w-full max-w-[1240px]" data-testid="tour-inline">
          <TourCard />
        </div>
      )}
      <div className={`pointer-events-none fixed left-1/2 z-[60] flex w-[min(92vw,460px)] -translate-x-1/2 flex-col gap-2 ${mode === "compare" && !narrow ? "top-[196px]" : "top-[118px] max-[900px]:top-[120px]"}`} data-testid="toast-stack">
        {narrow && !inlineTour && mode !== "home" && <TourCard />}
        <Toasts />
      </div>
      {/* On a desktop the tour card is docked bottom-right, over the lower part of the side column, so it never covers
          a pane title, the scenario toggle or the building. */}
      {!narrow && !inlineTour && mode !== "home" && (
        <div className="pointer-events-none fixed bottom-3 right-3 z-[60] flex max-h-[62vh] w-[360px] flex-col justify-end" data-testid="tour-dock">
          <TourCard />
        </div>
      )}
    </>
  );

  if (mode === "home") return <HomeView narrow={narrow} top={top} onMode={onMode} />;
  if (mode === "optimize") return <OptimizeView narrow={narrow} top={top} />;
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
