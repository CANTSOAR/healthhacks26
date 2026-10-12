"use client";
import { useEffect, useState } from "react";
import { apiBase } from "@/lib/api";

// The hospital's own disclaimer (from /api/hospitals, i.e. the layout file) for pages that have no 3D scene (the
// landing page): they name the hospital model, so they carry the same notice as the hospital view.
const FALLBACK = "A model built from public information. Not affiliated with or endorsed by Robert Wood Johnson University Hospital. Patient flows, staffing and outcomes are simulated, not the hospital's operational data. Staff are fictional.";
let cached: string | null = null;

export function SiteDisclaimer({ className = "" }: { className?: string }) {
  const [text, setText] = useState(cached ?? FALLBACK);
  useEffect(() => {
    if (cached) return;
    let dead = false;
    fetch(`${apiBase()}/api/hospitals`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((list: { id: string; disclaimer?: string }[] | null) => {
        const d = (list?.find((h) => h.id === "rwjuh_nb") ?? list?.[0])?.disclaimer;
        if (d) {
          cached = d;
          if (!dead) setText(d);
        }
      })
      .catch(() => undefined);
    return () => {
      dead = true;
    };
  }, []);
  return (
    <footer className={`mx-auto w-full max-w-[1080px] px-4 text-center text-[10.5px] leading-snug text-ink-3 ${className}`} data-testid="site-disclaimer">
      <span className="font-semibold text-ink-2">HospitalGym.</span> {text} All numbers are simulated.
    </footer>
  );
}
