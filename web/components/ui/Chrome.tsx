"use client";
import { useStore } from "zustand";
import type { Feed } from "@/lib/feed";
import { ACUITY, ROLE_COLOR, SKIN, STAFF_HEAD } from "@/lib/palette";
import { useUI } from "@/lib/ui";
import { Icon, ICONS } from "./atoms";

/** Zoom / rotate controls in a vertical pill. */
export function CameraPill() {
  const cam = useUI((s) => s.cam);
  const B = ({ label, d, onClick }: { label: string; d: string; onClick: () => void }) => (
    <button aria-label={label} title={label} onClick={onClick} className="flex h-9 w-9 items-center justify-center rounded-full text-ink-2 transition-colors hover:bg-accent-soft hover:text-accent-dark">
      <Icon d={d} size={16} stroke={2} />
    </button>
  );
  return (
    <div className="glass pointer-events-auto flex flex-col items-center gap-0.5 !rounded-full p-1" data-testid="camera-pill">
      <B label="Zoom in" d={ICONS.plus} onClick={() => cam("zoom", 0.72)} />
      <B label="Zoom out" d={ICONS.minus} onClick={() => cam("zoom", 1.38)} />
      <span className="my-0.5 h-px w-5 bg-line" />
      <B label="Rotate left" d={ICONS.rotL} onClick={() => cam("rotate", -Math.PI / 6)} />
      <B label="Rotate right" d={ICONS.rotR} onClick={() => cam("rotate", Math.PI / 6)} />
      <span className="my-0.5 h-px w-5 bg-line" />
      <B label="Tilt up" d={ICONS.up} onClick={() => cam("tilt", -0.12)} />
      <B label="Tilt down" d={ICONS.down} onClick={() => cam("tilt", 0.12)} />
      <span className="my-0.5 h-px w-5 bg-line" />
      <B label="Reset view" d={ICONS.home} onClick={() => cam("reset", 0)} />
    </div>
  );
}

function Person({ body, head }: { body: string; head: string }) {
  return (
    <svg width="9" height="15" viewBox="0 0 9 15" aria-hidden>
      <circle cx="4.5" cy="3" r="2.6" fill={head} />
      <rect x="1" y="6" width="7" height="9" rx="3.5" fill={body} />
    </svg>
  );
}

/** Colour key for people in the scene. */
export function Legend() {
  const staff: [string, string][] = [
    ["Physician", ROLE_COLOR.attending],
    ["Resident", ROLE_COLOR.resident],
    ["APP", ROLE_COLOR.app],
    ["Nurse", ROLE_COLOR.rn],
    ["Other staff", ROLE_COLOR.tech],
  ];
  return (
    <div className="glass pointer-events-auto grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1 px-3.5 py-2 text-[11px] font-medium text-ink-2" data-testid="legend">
      <span className="eyebrow">Patients</span>
      <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {[1, 2, 3, 4, 5].map((a) => (
          <span key={a} className="flex items-center gap-1 whitespace-nowrap">
            <Person body={ACUITY[a]} head={SKIN} />
            ESI {a}
          </span>
        ))}
        <span className="text-ink-3">acuity, 1 most urgent</span>
      </span>
      <span className="eyebrow">Staff</span>
      <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {staff.map(([l, c]) => (
          <span key={l} className="flex items-center gap-1 whitespace-nowrap">
            <Person body={c} head={STAFF_HEAD} />
            {l}
          </span>
        ))}
      </span>
    </div>
  );
}

/** Persistent disclaimer from layout.disclaimer, plus attribution when the site outline comes from OpenStreetMap. */
export function Disclaimer({ feed, className = "" }: { feed: Feed; className?: string }) {
  const layout = useStore(feed, (s) => s.layout);
  const origin = useStore(feed, (s) => s.origin);
  if (!layout) return null;
  const osm = (layout.sources ?? []).some((s) => /openstreetmap/i.test(s.title + s.url)) || (layout.site.buildings ?? []).some((b) => /^osm/i.test(b.id));
  return (
    <div className={`pointer-events-auto max-w-full text-center text-[10.5px] leading-snug text-ink-3 ${className}`} data-testid="disclaimer">
      <span className="font-semibold text-ink-2">{layout.name}.</span> {layout.disclaimer}
      {origin === "fixture" ? " Numbers on screen are bundled fixture data." : " All numbers are simulated."}
      {osm ? (
        <>
          {" "}
          Site outline{" "}
          <a className="underline decoration-ink-4 underline-offset-2 hover:text-accent" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
            © OpenStreetMap contributors
          </a>
          .
        </>
      ) : null}
    </div>
  );
}
