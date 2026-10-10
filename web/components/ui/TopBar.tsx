"use client";
import { useCallback, useMemo, useState } from "react";
import { useStore } from "zustand";
import { apiBase } from "@/lib/api";
import { DOW_LONG, hhmm, patientId, titleCase } from "@/lib/format";
import { useClickAway, useFeedState } from "@/lib/hooks";
import { feeds, refreshStatus, transport } from "@/lib/session";
import { speedLabel, SPEEDS, useUI, type Mode } from "@/lib/ui";
import type { Selection } from "@/lib/types";
import { Icon, ICONS } from "./atoms";
import { TourButton } from "./Tour";

const MODES: { id: Mode; label: string }[] = [
  { id: "play", label: "Play" },
  { id: "watch", label: "Watch" },
  { id: "compare", label: "Compare" },
  { id: "tradeoff", label: "Trade-off" },
];

export function Logo() {
  return (
    <div className="flex items-center gap-2 pl-1">
      <span className="flex h-7 w-7 items-center justify-center rounded-[9px] bg-accent text-white shadow-pill">
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden>
          <path d="M7 2v10M2 7h10" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
        </svg>
      </span>
      <span className="text-[15px] font-semibold tracking-[-0.01em] text-ink">HospitalGym</span>
    </div>
  );
}

export function ModeTabs({ onMode }: { onMode: (m: Mode) => void }) {
  const mode = useUI((s) => s.mode);
  return (
    <div className="seg" role="tablist" aria-label="Mode">
      {MODES.map((m) => (
        <button key={m.id} role="tab" aria-selected={mode === m.id} data-on={mode === m.id} data-mode={m.id} onClick={() => onMode(m.id)}>
          {m.label}
        </button>
      ))}
    </div>
  );
}

export function Clock({ compact = false }: { compact?: boolean }) {
  const snap = useStore(feeds.a, (s) => s.snap);
  if (!snap)
    return (
      <div className="tnum px-1 text-[12px] font-medium text-ink-3" data-testid="clock">
        — : —
      </div>
    );
  const c = snap.clock;
  return (
    <div className="flex items-baseline gap-2 whitespace-nowrap px-1" data-testid="clock" title="Simulated time. One tick is five simulated minutes.">
      {!compact && <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-3">Day {c.day + 1}</span>}
      <span className="text-[12px] font-medium text-ink-2">{compact ? `D${c.day + 1} ${DOW_LONG[c.dow]?.slice(0, 3)}` : DOW_LONG[c.dow]}</span>
      <span className="tnum text-[17px] font-semibold tracking-[-0.01em] text-ink">{hhmm(c.minute_of_day)}</span>
    </div>
  );
}

export function SpeedControl({ compact = false }: { compact?: boolean }) {
  const speed = useUI((s) => s.speed);
  const paused = useUI((s) => s.paused);
  const set = useUI((s) => s.set);
  return (
    <div className="seg" aria-label="Simulation speed" title="Speed in ticks per second (one tick = five simulated minutes)">
      <button data-on={paused} aria-label={paused ? "Resume" : "Pause"} onClick={() => set({ paused: !paused })} className="!px-2">
        <Icon d={paused ? ICONS.play : ICONS.pause} size={13} stroke={2.4} />
      </button>
      {paused && !compact && (
        <button aria-label="Step one tick" onClick={() => transport.step()} className="!px-2" title="Advance one tick">
          <Icon d={ICONS.step} size={13} stroke={2.2} />
        </button>
      )}
      {compact ? (
        <button data-on={!paused} onClick={() => set({ speed: SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length], paused: false })} className="tnum !px-2.5" aria-label="Change speed" title="Tap to change speed">
          {speedLabel(speed)}
        </button>
      ) : (
        SPEEDS.map((v) => (
          <button key={v} data-on={!paused && speed === v} onClick={() => set({ speed: v, paused: false })} className="tnum !px-2.5">
            {speedLabel(v)}
          </button>
        ))
      )}
    </div>
  );
}

export function StatusIndicator() {
  const online = useUI((s) => s.online);
  const status = useUI((s) => s.status);
  const origin = useStore(feeds.a, (s) => s.origin);
  const [open, setOpen] = useState(false);
  const ref = useClickAway<HTMLDivElement>(useCallback(() => setOpen(false), []));
  const label = online == null ? "Checking…" : online ? "Live" : "Offline · fixture";
  const color = online == null ? "#B4BAD1" : online ? "#1BAF7A" : "#E0A21B";
  const sv = status?.services;
  const rows: [string, boolean, string][] = [
    ["Simulator", !!online && !!sv?.sim.live, online ? (sv?.sim.live ? "live" : "not running") : "unreachable · fixture replay"],
    ["Language model", !!online && !!sv?.llm.live, online ? `${sv?.llm.provider ?? "offline"}${sv?.llm.model ? ` · ${sv.llm.model}` : ""}` : "offline rules"],
    ["Voice", !!online && !!sv?.voice.live, online ? (sv?.voice.provider ?? "browser") : "browser speech"],
    ["Data service", !!online && !!sv?.data.live, online ? (sv?.data.provider ?? "public_extracts") : "public extracts"],
  ];
  return (
    <div className="relative" ref={ref}>
      <button
        className="flex h-8 items-center gap-2 whitespace-nowrap rounded-full border border-line bg-white/70 px-3 text-[12px] font-semibold text-ink-2 hover:border-accent/30"
        onClick={() => {
          setOpen((o) => !o);
          void refreshStatus();
        }}
        data-testid="status"
        aria-expanded={open}
      >
        <span className="h-2 w-2 rounded-full" style={{ background: color, boxShadow: `0 0 0 3px ${color}33` }} />
        <span className="max-[1180px]:hidden">{label}</span>
      </button>
      {open && (
        <div className="glass-solid rise absolute right-0 top-10 z-50 w-[290px] p-3" data-testid="status-pop">
          <div className="eyebrow mb-2">Services</div>
          <div className="space-y-1.5">
            {rows.map(([name, live, note]) => (
              <div key={name} className="flex items-center gap-2 text-[12px]">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: live ? "#1BAF7A" : "#B4BAD1" }} />
                <span className="font-semibold text-ink">{name}</span>
                <span className="ml-auto truncate text-ink-3">{live ? note : note || "offline"}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 border-t border-line pt-2 text-[11px] leading-relaxed text-ink-3">
            <div>
              Server <span className="font-medium text-ink-2">{apiBase()}</span> {online ? "is answering." : "is not answering."}
            </div>
            {!online && <div>Showing bundled fixture data: placeholder numbers, not simulator output.</div>}
            {origin !== "none" && (
              <div>
                Scene data: <span className="font-medium text-ink-2">{origin === "live" ? "live simulation" : origin === "replay" ? "recorded rollout from the server" : "bundled fixture"}</span>
              </div>
            )}
            {status?.version && online ? <div>Version {status.version}{status.device ? ` · ${status.device}` : ""}</div> : null}
          </div>
        </div>
      )}
    </div>
  );
}

export function SearchBox() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const f = useFeedState(feeds.a, 500);
  const select = useUI((s) => s.select);
  const ref = useClickAway<HTMLDivElement>(useCallback(() => setOpen(false), []));
  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    const out: { sel: Selection; title: string; sub: string }[] = [];
    const push = (kind: Selection["kind"], id: string | number, title: string, sub: string) => out.length < 9 && out.push({ sel: { kind, id, feed: "a" }, title, sub });
    for (const r of f.layout?.rooms ?? []) if (r.label.toLowerCase().includes(s) || r.id.toLowerCase().includes(s)) push("room", r.id, r.label, titleCase(r.type));
    for (const e of f.layout?.equipment ?? []) if ((e.label ?? e.id).toLowerCase().includes(s) || e.id.toLowerCase().includes(s)) push("equipment", e.id, e.label ?? e.id, "Equipment");
    const snap = f.snap;
    if (snap) {
      snap.staff.id.forEach((id, i) => {
        if (id.toLowerCase().includes(s) || (snap.staff.name?.[i] ?? "").toLowerCase().includes(s)) push("staff", id, id, titleCase(f.header?.enums.staff_role[snap.staff.role[i]] ?? "staff"));
      });
      const digits = s.replace(/[^0-9]/g, "");
      if (digits || s.startsWith("p"))
        for (const id of snap.patients.id) if (!digits || String(id).includes(String(Number(digits))) || patientId(id).toLowerCase().includes(s)) push("patient", id, patientId(id), "Patient");
      for (const a of snap.ambulances ?? []) if (a.id.toLowerCase().includes(s)) push("ambulance", a.id, a.id, "Ambulance");
    }
    return out;
  }, [q, f.layout, f.snap, f.header]);
  return (
    <div className="relative min-w-[132px] flex-1" ref={ref} style={{ maxWidth: 300 }}>
      <div className="flex h-8 items-center gap-2 rounded-full border border-line bg-white/60 px-3 text-ink-3 focus-within:border-accent/50 focus-within:bg-white">
        <Icon d={ICONS.search} size={14} />
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && results[0]) {
              select(results[0].sel);
              setOpen(false);
            }
            if (e.key === "Escape") setOpen(false);
          }}
          placeholder="Search beds, staff, patients…"
          aria-label="Search entities"
          data-testid="search"
          className="w-full min-w-0 bg-transparent text-[12px] font-medium text-ink outline-none placeholder:text-ink-3"
        />
      </div>
      {open && q.trim() && (
        <div className="glass-solid rise absolute left-0 top-10 z-50 w-full min-w-[240px] p-1.5">
          {results.length === 0 && <div className="px-2 py-2 text-[12px] text-ink-3">Nothing matches “{q}”.</div>}
          {results.map((r) => (
            <button
              key={`${r.sel.kind}:${r.sel.id}`}
              className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-[12px] hover:bg-accent-soft"
              onClick={() => {
                select(r.sel);
                setOpen(false);
                setQ("");
              }}
            >
              <span className="font-semibold text-ink">{r.title}</span>
              <span className="text-ink-3">{r.sub}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Switchers() {
  const scenarios = useUI((s) => s.scenarios);
  const hospitals = useUI((s) => s.hospitals);
  const scenarioId = useUI((s) => s.scenarioId);
  const hospitalId = useUI((s) => s.hospitalId);
  const set = useUI((s) => s.set);
  return (
    <>
      <select className="select max-w-[150px]" value={scenarioId} onChange={(e) => set({ scenarioId: e.target.value })} aria-label="Scenario" data-testid="scenario">
        {scenarios.map((s) => (
          <option key={s.id} value={s.id}>
            {s.label}
          </option>
        ))}
      </select>
      <select className="select max-w-[170px] max-[1599px]:hidden" value={hospitalId} onChange={(e) => set({ hospitalId: e.target.value })} aria-label="Hospital" data-testid="hospital">
        {hospitals.map((h) => (
          <option key={h.id} value={h.id}>
            {h.name.replace(/\s*\(.*\)$/, "").replace("Robert Wood Johnson University Hospital", "RWJUH")}
          </option>
        ))}
      </select>
    </>
  );
}

export function TopBar({ narrow, onMode }: { narrow: boolean; onMode: (m: Mode) => void }) {
  const clockless = useUI((s) => s.mode === "tradeoff");
  if (narrow)
    return (
      <div className="pointer-events-auto flex flex-col gap-2">
        <div className="glass flex h-12 items-center gap-2 px-2.5">
          <Logo />
          <div className="ml-auto">{!clockless && <Clock compact />}</div>
          <TourButton compact />
          <StatusIndicator />
        </div>
        <div className="flex items-center gap-2">
          <div className="glass flex h-10 min-w-0 flex-1 items-center overflow-x-auto px-1 [&_button]:!px-2.5">
            <ModeTabs onMode={onMode} />
          </div>
          {!clockless && (
            <div className="glass flex h-10 shrink-0 items-center px-1">
              <SpeedControl compact />
            </div>
          )}
        </div>
      </div>
    );
  return (
    <div className="glass pointer-events-auto relative z-40 flex h-[52px] items-center gap-3 px-3">
      <Logo />
      <ModeTabs onMode={onMode} />
      <SearchBox />
      <div className="ml-auto flex items-center gap-2">
        <div className="flex items-center gap-2 max-[1280px]:hidden">
          <Switchers />
        </div>
        <span className="mx-1 h-5 w-px bg-line" />
        {!clockless && <Clock />}
        {!clockless && <SpeedControl />}
        <TourButton />
        <StatusIndicator />
      </div>
    </div>
  );
}
