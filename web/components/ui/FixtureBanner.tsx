"use client";
import { useStore } from "zustand";
import { apiBase } from "@/lib/api";
import { feeds, refreshStatus } from "@/lib/session";
import { useUI } from "@/lib/ui";

/** Loud, persistent notice whenever the API cannot be reached. It goes away by itself when the API answers again. */
export function FixtureBanner() {
  const online = useUI((s) => s.online);
  const origin = useStore(feeds.a, (s) => s.origin);
  const listsSource = useUI((s) => s.listsSource);
  if (online !== false) return null;
  const fixture = origin === "fixture" || listsSource === "fixture";
  return (
    <div className="pointer-events-auto flex flex-wrap items-center justify-center gap-x-3 gap-y-1 rounded-xl border border-[#E0A21B]/40 bg-[#FFF4D6] px-3 py-1.5 text-[12px] font-semibold text-[#7A4E00] shadow-card" role="alert" data-testid="fixture-banner-global">
      <span className="h-2 w-2 rounded-full bg-[#E0A21B]" />
      {fixture ? "API unreachable. Showing bundled sample data, not a simulator run." : "API unreachable. What is on screen was loaded earlier; anything new will be bundled sample data."}
      <span className="font-medium text-[#8A5A00]">{apiBase()} · retrying every few seconds</span>
      <button className="rounded-full border border-[#E0A21B]/50 bg-white/70 px-2 py-[1px] text-[11px] font-semibold hover:bg-white" onClick={() => void refreshStatus()}>
        Retry now
      </button>
    </div>
  );
}
