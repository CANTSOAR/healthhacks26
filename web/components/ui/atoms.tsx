"use client";
import type { ReactNode } from "react";
import { useStore } from "zustand";
import { kindInfo, SOURCE_CHIP } from "@/lib/palette";
import { feeds } from "@/lib/session";

export function Chip({ children, bg, fg, title }: { children: ReactNode; bg: string; fg: string; title?: string }) {
  return (
    <span className="chip" style={{ background: bg, color: fg }} title={title}>
      {children}
    </span>
  );
}

/** measured / literature / assumed, surveyed / published / inferred, fixture */
export function SourceChip({ tag, title }: { tag: string; title?: string }) {
  const c = SOURCE_CHIP[tag] ?? SOURCE_CHIP.fixture;
  return (
    <Chip bg={c.bg} fg={c.fg} title={title}>
      {c.label ?? tag}
    </Chip>
  );
}

export function Marker({ shape, color, size = 10, ring = false }: { shape: string; color: string; size?: number; ring?: boolean }) {
  const s = size;
  const h = s / 2;
  let el: ReactNode;
  switch (shape) {
    case "square":
      el = <rect x={-h * 0.86} y={-h * 0.86} width={s * 0.86} height={s * 0.86} rx={1.5} />;
      break;
    case "diamond":
      el = <path d={`M0 ${-h * 1.12}L${h * 1.12} 0L0 ${h * 1.12}L${-h * 1.12} 0Z`} />;
      break;
    case "triangle":
      el = <path d={`M0 ${-h * 1.1}L${h * 1.12} ${h * 0.86}L${-h * 1.12} ${h * 0.86}Z`} />;
      break;
    case "cross":
      el = <path d={`M${-h} ${-h}L${h} ${h}M${-h} ${h}L${h} ${-h}`} fill="none" stroke={color} strokeWidth={s * 0.3} strokeLinecap="round" />;
      break;
    case "star": {
      const pts: string[] = [];
      for (let i = 0; i < 10; i++) {
        const r = i % 2 === 0 ? h * 1.3 : h * 0.55;
        const a = (Math.PI / 5) * i - Math.PI / 2;
        pts.push(`${(Math.cos(a) * r).toFixed(2)},${(Math.sin(a) * r).toFixed(2)}`);
      }
      el = <polygon points={pts.join(" ")} />;
      break;
    }
    default:
      el = <circle r={h} />;
  }
  return (
    <g fill={color} stroke={ring ? "#fff" : undefined} strokeWidth={ring ? 2 : undefined} paintOrder="stroke">
      {el}
    </g>
  );
}

/** Manager kind label: learned / tuned heuristic / rule-based / fixed / random / human. Shown wherever a manager is named. */
export function KindChip({ kind }: { kind: string }) {
  const k = kindInfo(kind);
  return (
    <span className="chip border border-line bg-white/80 text-ink-2" title={`Manager kind: ${k.label}`}>
      <svg width="10" height="10" viewBox="-6 -6 12 12" aria-hidden>
        <Marker shape={k.shape} color={k.color} size={8} />
      </svg>
      {k.label}
    </span>
  );
}

/** "simulated" beside numbers from the simulator; "fixture" when what is on screen is the bundled placeholder data. */
export function SimTag({ children }: { children?: ReactNode }) {
  const fixture = useStore(feeds.a, (s) => s.origin === "fixture");
  if (children) return <span className="sim-tag">{children}</span>;
  return fixture ? (
    <span className="sim-tag" style={{ background: "#FDEFD8", color: "#8A5A00" }} title="Bundled placeholder data, not a simulator run">
      fixture
    </span>
  ) : (
    <span className="sim-tag">simulated</span>
  );
}

export function Bar({ value, color = "#2F55F5", track = "rgba(20,26,51,0.07)" }: { value: number; color?: string; track?: string }) {
  const v = Math.max(0, Math.min(1, isFinite(value) ? value : 0));
  return (
    <span className="block h-1 w-full overflow-hidden rounded-full" style={{ background: track }}>
      <span className="block h-full rounded-full" style={{ width: `${v * 100}%`, background: color }} />
    </span>
  );
}

export function Icon({ d, size = 16, stroke = 1.8 }: { d: string; size?: number; stroke?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={d} />
    </svg>
  );
}
export const ICONS = {
  search: "M11 19a8 8 0 1 1 5.3-2l4.2 4.2M16.3 17",
  plus: "M12 5v14M5 12h14",
  minus: "M5 12h14",
  rotL: "M4 12a8 8 0 1 0 2.6-5.9M4 4v5h5",
  rotR: "M20 12a8 8 0 1 1-2.6-5.9M20 4v5h-5",
  home: "M4 11l8-7 8 7M6 10v9h12v-9",
  close: "M6 6l12 12M18 6L6 18",
  play: "M8 5l11 7-11 7z",
  pause: "M8 5v14M16 5v14",
  step: "M6 5l9 7-9 7zM18 5v14",
  chevron: "M9 6l6 6-6 6",
  link: "M14 5h5v5M19 5l-8 8M11 7H6v11h11v-5",
  up: "M6 15l6-6 6 6",
  down: "M6 9l6 6 6-6",
};
