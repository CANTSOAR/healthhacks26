"use client";
// The journey as a rail of stages: who each stage belongs to, and who actually played it (you, a sampled AI colleague, the simulation).
import { roleTone, TYPE_LABEL } from "@/lib/journey/api";
import type { Stage } from "@/lib/journey/types";
import { initials } from "@/lib/encounter/labels";

export function RoleAvatar({ staffRole, name, size = 30 }: { staffRole: string; name?: string | null; size?: number }) {
  const t = roleTone(staffRole);
  return (
    <span className="flex shrink-0 items-center justify-center rounded-full border border-white font-semibold shadow-pill" style={{ width: size, height: size, background: t.bg, color: t.fg, fontSize: size * 0.36 }} aria-hidden>
      {initials((name ?? "").replace(/^Dr\.\s*/, "")) || "?"}
    </span>
  );
}

function playedBy(s: Stage): { text: string; bg: string; fg: string } {
  if (s.status === "completed") {
    if (s.played_by === "human") return { text: "You played", bg: "#E3E9FF", fg: "#1F3FD1" };
    if (s.played_by === "sim") return { text: "Simulation", bg: "rgba(20,26,51,0.06)", fg: "#4A5275" };
    return { text: `Sampled · ${s.player ?? "AI"}`, bg: "rgba(20,26,51,0.06)", fg: "#4A5275" };
  }
  if (s.status === "active") return { text: "You, in progress", bg: "#2F55F5", fg: "#fff" };
  return s.blocked_by.length ? { text: "Waiting", bg: "rgba(20,26,51,0.04)", fg: "#8089A8" } : { text: "Up next", bg: "#FFF1D6", fg: "#8A5200" };
}

export function StageRail({ stages, selected, onSelect, complete }: { stages: Stage[]; selected: string; onSelect: (id: string) => void; complete: boolean }) {
  return (
    <nav className="scroll-thin flex items-stretch gap-2 overflow-x-auto pb-1" aria-label="Journey stages" data-testid="stage-rail">
      {stages.map((s, i) => {
        const on = selected === s.stage_id;
        const p = playedBy(s);
        return (
          <button
            key={s.stage_id}
            onClick={() => onSelect(s.stage_id)}
            className={`glass flex min-w-[210px] flex-1 items-center gap-2.5 px-3 py-2 text-left transition-shadow ${on ? "ring-2 ring-accent/60" : "hover:ring-1 hover:ring-accent/25"}`}
            data-testid="rail-stage"
            data-stage={s.stage_id}
            data-status={s.status}
            data-played-by={s.played_by ?? ""}
            aria-current={on ? "step" : undefined}
          >
            <span className="relative">
              <RoleAvatar staffRole={s.learner_role.staff_role} name={s.status === "pending" || s.played_by === "human" ? s.learner_role.label : s.player} size={34} />
              {s.status === "completed" && (
                <span className="absolute -bottom-0.5 -right-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-[#2FA36B] text-white">
                  <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                </span>
              )}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[10px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                {i + 1} · {TYPE_LABEL[s.interaction_type] ?? s.interaction_type}
              </span>
              <span className="block truncate text-[13px] font-semibold tracking-[-0.01em] text-ink">{s.title}</span>
              <span className="mt-0.5 flex items-center gap-1.5">
                <span className="truncate text-[11px] text-ink-2">{s.learner_role.label}</span>
              </span>
              <span className="chip mt-1 max-w-full truncate" style={{ background: p.bg, color: p.fg }}>
                {p.text}
              </span>
            </span>
          </button>
        );
      })}
      <button onClick={() => onSelect("outcome")} className={`glass flex min-w-[170px] flex-col justify-center px-3 py-2 text-left transition-shadow ${selected === "outcome" ? "ring-2 ring-accent/60" : "hover:ring-1 hover:ring-accent/25"}`} data-testid="rail-outcome">
        <span className="text-[10px] font-semibold uppercase tracking-[0.07em] text-ink-3">{stages.length + 1} · Synthesis</span>
        <span className="text-[13px] font-semibold tracking-[-0.01em] text-ink">Care plan and debrief</span>
        <span className="chip mt-1 self-start" style={complete ? { background: "#E3F4EA", color: "#1F7A4D" } : { background: "rgba(20,26,51,0.04)", color: "#8089A8" }}>
          {complete ? "Ready" : "Plan so far"}
        </span>
      </button>
    </nav>
  );
}
