"use client";
import { useUI } from "@/lib/ui";
import { Icon, ICONS } from "./atoms";

const TONE = { info: "#2F55F5", warn: "#E0A21B", error: "#E5484D" } as const;

/** Short notices for things that just happened in the simulation: an injected event starting, a hand-over, an error. */
export function Toasts() {
  const toasts = useUI((s) => s.toasts);
  const dismiss = useUI((s) => s.dismissToast);
  if (!toasts.length) return null;
  return (
    <div className="flex flex-col gap-2" data-testid="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className="glass-solid rise pointer-events-auto flex items-start gap-2.5 px-3.5 py-2.5">
          <span className="mt-[5px] h-2 w-2 shrink-0 rounded-full" style={{ background: TONE[t.tone] }} />
          <span className="min-w-0 flex-1 text-[12px] font-medium leading-snug text-ink">{t.text}</span>
          <button aria-label="Dismiss" className="-mr-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-ink-3 hover:text-ink" onClick={() => dismiss(t.id)}>
            <Icon d={ICONS.close} size={11} stroke={2.4} />
          </button>
        </div>
      ))}
    </div>
  );
}
