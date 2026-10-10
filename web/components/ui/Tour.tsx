"use client";
import { useEffect } from "react";
import { tour, tourSteps } from "@/lib/tour";
import { useUI } from "@/lib/ui";
import { Icon, ICONS } from "./atoms";

export function TourButton({ compact = false }: { compact?: boolean }) {
  const active = useUI((s) => !!s.tour);
  return (
    <button className={active ? "btn-primary" : "btn-quiet"} onClick={() => (active ? tour.exit() : void tour.start())} data-testid="tour-button" title="A guided walk through the demo, using only the managers and recordings that exist right now">
      <Icon d={ICONS.play} size={11} stroke={2.4} />
      {compact ? (
        "Tour"
      ) : (
        <>
          <span className="max-[1500px]:hidden">{active ? "End tour" : "Demo tour"}</span>
          <span className="min-[1501px]:hidden">{active ? "End" : "Tour"}</span>
        </>
      )}
    </button>
  );
}

/** Caption card for the guided demo. Arrow keys move between steps, Escape leaves. */
export function TourCard() {
  const t = useUI((s) => s.tour);
  useEffect(() => {
    if (!t) return;
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && /^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName)) return;
      if (e.key === "ArrowRight" || e.key === "PageDown") void tour.next();
      else if (e.key === "ArrowLeft" || e.key === "PageUp") void tour.back();
      else if (e.key === "Escape") tour.exit();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [t]);
  if (!t) return null;
  const steps = tourSteps();
  const step = steps[t.index];
  if (!step) return null;
  const skipped = steps.map((s, i) => ({ s, i })).filter((x) => x.s.skip);
  return (
    <div className="glass-solid rise pointer-events-auto px-4 pb-3 pt-3.5" data-testid="tour-card" role="dialog" aria-label="Demo tour">
      <div className="flex items-center gap-2">
        <span className="eyebrow">
          Demo tour · step {t.index + 1} of {steps.length}
        </span>
        <span className="ml-auto flex items-center gap-1">
          {steps.map((s, i) => (
            <span key={i} title={s.skip ? `${s.title}: skipped, ${s.skip}` : s.title} className="h-1.5 rounded-full" style={{ width: i === t.index ? 18 : 8, background: i === t.index ? "#2F55F5" : s.skip ? "transparent" : "rgba(20,26,51,0.16)", border: s.skip ? "1px dashed rgba(20,26,51,0.25)" : undefined }} />
          ))}
        </span>
        <button aria-label="End tour" className="-mr-1.5 flex h-6 w-6 items-center justify-center rounded-full text-ink-3 hover:bg-accent-soft hover:text-accent-dark" onClick={() => tour.exit()}>
          <Icon d={ICONS.close} size={12} stroke={2.4} />
        </button>
      </div>
      <div className="mt-1.5 text-[15px] font-semibold tracking-[-0.01em] text-ink">{step.title}</div>
      <div className="mt-1 text-[12px] leading-relaxed text-ink-2">{step.caption}</div>
      {skipped.length > 0 && (
        <div className="mt-2 text-[10.5px] leading-snug text-ink-3">
          Skipped for now: {skipped.map((x) => `step ${x.i + 1} (${x.s.skip})`).join("; ")}.
        </div>
      )}
      <div className="mt-2.5 flex items-center gap-2">
        <button className="btn-quiet !h-7" onClick={() => void tour.back()} disabled={!tour.hasBack() || t.busy} data-testid="tour-back">
          Back
        </button>
        <button className="btn-primary !h-7" onClick={() => (tour.hasNext() ? void tour.next() : tour.exit())} disabled={t.busy} data-testid="tour-next">
          {t.busy ? "Loading…" : tour.hasNext() ? "Next" : "Finish"}
        </button>
        <span className="ml-auto text-[10.5px] text-ink-3 max-[900px]:hidden">← → to move · Esc to leave</span>
      </div>
    </div>
  );
}
