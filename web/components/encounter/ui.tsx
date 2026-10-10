"use client";
// Small shared pieces for the Encounter and Patient Studio pages. Visual language comes from app/globals.css
// (.glass, .chip, .btn, .eyebrow) so these pages sit next to the hospital view without a seam.
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { assetUrl } from "@/lib/encounter/api";
import { initials, providerHelp, providerLabel, STATUS_TONE } from "@/lib/encounter/labels";
import type { LlmStatus } from "@/lib/encounter/types";

export function Tone({ bg, fg, children, title, className = "" }: { bg: string; fg: string; children: ReactNode; title?: string; className?: string }) {
  return (
    <span className={`chip ${className}`} style={{ background: bg, color: fg }} title={title}>
      {children}
    </span>
  );
}

export function StatusChip({ status }: { status: string }) {
  const t = STATUS_TONE[status] ?? { bg: "rgba(20,26,51,0.06)", fg: "#4A5275" };
  return (
    <Tone bg={t.bg} fg={t.fg}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: t.fg }} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Tone>
  );
}

/** The label every synthetic patient carries. */
export function SyntheticLabel({ compact = false, review = true }: { compact?: boolean; review?: boolean }) {
  return (
    <span
      className="chip"
      style={{ background: "#FFF1D6", color: "#8A5200" }}
      title="This patient is invented for teaching. No real person's data is used. Clinical content needs review by faculty before it is used with learners."
      data-testid="synthetic-label"
    >
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M12 9v4M12 17h.01M10.3 3.9L2.5 17.5A2 2 0 0 0 4.2 20.5h15.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      </svg>
      {compact ? "Synthetic patient" : review ? "Synthetic patient — for education; needs faculty review" : "Synthetic patient — for education"}
    </span>
  );
}

export function ProviderChip({ llm, fallback = false }: { llm?: LlmStatus | null; fallback?: boolean }) {
  const offline = !llm || !llm.live || llm.provider === "offline";
  return (
    <span className="inline-flex items-center gap-1" data-testid="provider-chip">
      <Tone bg={offline ? "rgba(20,26,51,0.06)" : "#E3F4EA"} fg={offline ? "#4A5275" : "#1F7A4D"} title={providerHelp(llm)}>
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: offline ? "#8089A8" : "#2FA36B" }} />
        {providerLabel(llm)}
      </Tone>
      {fallback && (
        <Tone bg="#FFF1D6" fg="#9A5B00" title="The language model did not answer for at least one turn, so the authored wording was used instead.">
          fallback
        </Tone>
      )}
    </span>
  );
}

/** Patient photo when the API has one; otherwise an initials disc (the API's own placeholder is the same idea). */
export function Avatar({ name, image, size = 40 }: { name?: string | null; image?: string | null; size?: number }) {
  const [broken, setBroken] = useState(false);
  const src = assetUrl(image);
  useEffect(() => setBroken(false), [src]);
  if (src && !broken) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={src} alt={name ? `${name}` : "Patient"} width={size} height={size} onError={() => setBroken(true)} className="shrink-0 rounded-full border border-white object-cover shadow-pill" style={{ width: size, height: size, background: "#E3E9FF" }} />
    );
  }
  return (
    <span className="flex shrink-0 items-center justify-center rounded-full border border-white font-semibold text-accent shadow-pill" style={{ width: size, height: size, background: "#E3E9FF", fontSize: size * 0.36 }} aria-hidden>
      {initials(name)}
    </span>
  );
}

export function Spinner({ size = 14 }: { size?: number }) {
  return <span className="inline-block animate-spin rounded-full border-2 border-accent/25 border-t-accent" style={{ width: size, height: size }} role="status" aria-label="Loading" />;
}

export function LoadingCard({ label }: { label: string }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center p-6">
      <div className="glass flex items-center gap-3 px-5 py-4 text-[13px] font-medium text-ink-2">
        <Spinner /> {label}
      </div>
    </div>
  );
}

export function ErrorCard({ title, message, children }: { title: string; message?: string; children?: ReactNode }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center p-6">
      <div className="glass max-w-lg p-6" role="alert">
        <div className="eyebrow" style={{ color: "#B4232C" }}>
          Something went wrong
        </div>
        <h1 className="mt-1 text-[18px] font-semibold tracking-[-0.01em] text-ink">{title}</h1>
        {message && <p className="mt-2 text-[13px] leading-relaxed text-ink-2">{message}</p>}
        <div className="mt-4 flex flex-wrap gap-2">{children}</div>
      </div>
    </div>
  );
}

export function InlineError({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border px-3 py-2 text-[12px] font-medium" style={{ background: "#FDE7E7", borderColor: "#F5C2C5", color: "#8E1B23" }} role="alert">
      {children}
    </div>
  );
}

/** Top navigation shared by the encounter picker and the studio. */
export function SiteNav({ current, right }: { current: "encounter" | "studio"; right?: ReactNode }) {
  const tab = (href: string, label: string, on: boolean) => (
    <Link href={href} className={`inline-flex h-7 items-center rounded-full px-3 text-[12px] font-semibold transition-colors ${on ? "bg-white text-accent-dark shadow-[0_1px_3px_rgba(47,65,140,0.18)]" : "text-ink-2 hover:text-accent-dark"}`}>
      {label}
    </Link>
  );
  return (
    <header className="sticky top-0 z-30 px-3 pt-3 sm:px-5">
      <div className="glass flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2 sm:px-4">
        <Link href="/" className="flex items-center gap-2 pr-1" title="Back to the hospital">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-white">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" aria-hidden>
              <path d="M12 5v14M5 12h14" />
            </svg>
          </span>
          <span className="text-[14px] font-semibold tracking-[-0.01em] text-ink">HospitalGym</span>
        </Link>
        <nav className="inline-flex items-center rounded-full bg-[#141a33]/[0.05] p-[3px]" aria-label="Sections">
          {tab("/", "Hospital", false)}
          {tab("/encounter", "Encounter", current === "encounter")}
          {tab("/studio", "Patient Studio", current === "studio")}
        </nav>
        <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>
      </div>
    </header>
  );
}

export function Modal({ title, onClose, children, wide = false }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-[#141a33]/30 p-0 backdrop-blur-[3px] sm:items-center sm:p-6" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className={`glass-solid rise flex max-h-[92vh] w-full flex-col overflow-hidden ${wide ? "sm:max-w-3xl" : "sm:max-w-xl"}`}>
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>
          <button className="btn !h-7 !w-7 !px-0" aria-label="Close" onClick={onClose}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
        <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

export const inputCls =
  "w-full rounded-lg border border-line bg-white/80 px-2.5 py-1.5 text-[13px] text-ink outline-none transition-colors placeholder:text-ink-4 hover:border-accent/30 focus:border-accent/60 focus:bg-white disabled:bg-[#141a33]/[0.03] disabled:text-ink-3";

export function Field({ label, hint, children, className = "" }: { label: string; hint?: string; children: ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-[11px] font-semibold text-ink-2">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] leading-snug text-ink-3">{hint}</span>}
    </label>
  );
}
