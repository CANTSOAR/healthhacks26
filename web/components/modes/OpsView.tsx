"use client";
import { useMemo } from "react";
import { useFeedState } from "@/lib/hooks";
import { feeds } from "@/lib/session";
import { useUI } from "@/lib/ui";
import HospitalScene from "../scene/HospitalScene";
import { CameraPill, Disclaimer, Legend } from "../ui/Chrome";
import { EntityList } from "../ui/EntityList";
import { Inspector } from "../ui/Inspector";
import { JourneyStepper } from "../ui/Journey";
import { KpiCards } from "../ui/Kpis";
import { Timeline } from "../ui/Timeline";
import { PlayPanel } from "./PlayPanel";
import { WatchPanel } from "./WatchPanel";

/** Play and Watch: one full-screen scene with panels floating over it. */
export function OpsView({ narrow, top }: { narrow: boolean; top: React.ReactNode }) {
  const f = useFeedState(feeds.a, 250);
  const mode = useUI((s) => s.mode);
  const selection = useUI((s) => s.selection);
  const drawer = useUI((s) => s.drawer);
  const set = useUI((s) => s.set);
  const Panel = mode === "play" ? PlayPanel : WatchPanel;

  const insets = useMemo(() => (narrow ? { l: 0, r: 0, t: 200, b: 96 } : { l: 372, r: 352, t: 64, b: 236 }), [narrow]);

  if (narrow) {
    const tabs: [NonNullable<typeof drawer>, string][] = [
      ["controls", mode === "play" ? "Controls" : "Decisions"],
      ["list", "Lists"],
      ["inspector", "Inspector"],
    ];
    return (
      <>
        <div className="fixed inset-0">
          <HospitalScene feed={feeds.a} insets={insets} />
        </div>
        <div className="pointer-events-none fixed inset-0 flex flex-col gap-2 p-2">
          {top}
          <KpiCards f={f} compact />
          <div className="flex min-h-0 flex-1 items-center justify-end">{!drawer && <CameraPill />}</div>
          {drawer && (
            <div className="solid flex max-h-[58vh] min-h-0 flex-col gap-2" data-testid="drawer">
              {drawer === "controls" && (
                <>
                  <Panel f={f} className="max-h-[36vh]" />
                  <Timeline f={f} />
                </>
              )}
              {drawer === "list" && <EntityList f={f} className="h-[50vh]" />}
              {drawer === "inspector" &&
                (selection ? (
                  <>
                    <Inspector f={f} className="max-h-[38vh] !bg-white/95" />
                    {selection.kind === "patient" && <JourneyStepper f={f} className="overflow-x-auto" />}
                  </>
                ) : (
                  <div className="glass pointer-events-auto px-4 py-4 text-[12px] text-ink-3">Tap a person, bed, room or machine in the scene to inspect it.</div>
                ))}
            </div>
          )}
          <div className="glass pointer-events-auto flex h-11 items-center gap-1 p-1" data-testid="drawer-tabs">
            {tabs.map(([id, label]) => (
              <button key={id} data-drawer={id} onClick={() => set({ drawer: drawer === id ? null : id })} className={`h-9 flex-1 rounded-xl text-[12px] font-semibold transition-colors ${drawer === id ? "bg-accent text-white" : "text-ink-2 hover:bg-accent-soft"}`}>
                {label}
              </button>
            ))}
          </div>
          <Disclaimer feed={feeds.a} className="line-clamp-2 px-1" />
        </div>
      </>
    );
  }

  return (
    <>
      <div className="fixed inset-0">
        <HospitalScene feed={feeds.a} insets={insets} />
      </div>
      <div className="pointer-events-none fixed inset-0 flex flex-col gap-3 p-3">
        {top}
        <div className="flex min-h-0 flex-1 gap-3">
          <div className="flex min-h-0 w-[348px] shrink-0 flex-col gap-3 min-[1360px]:w-[468px]">
            <KpiCards f={f} />
            <Panel f={f} className="w-[348px] max-h-full" />
            <div className="min-h-0 flex-1" />
            <JourneyStepper f={f} />
          </div>
          <div className="flex min-w-0 flex-1 flex-col items-center justify-end gap-2">
            <div className="flex min-h-0 w-full flex-1 items-center justify-end">
              <CameraPill />
            </div>
            {(f.snap || Object.keys(f.hourly).length > 0) && <Timeline f={f} className="max-w-[720px]" />}
            <Legend />
            <Disclaimer feed={feeds.a} className="max-w-[720px]" />
          </div>
          <div className="flex min-h-0 w-[340px] shrink-0 flex-col gap-3">
            {selection && <Inspector f={f} className="min-h-0 flex-[1.7]" />}
            <EntityList f={f} className={selection ? "min-h-0 flex-1" : "min-h-0 flex-1"} />
          </div>
        </div>
      </div>
    </>
  );
}
