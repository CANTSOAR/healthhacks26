"use client";
// /encounter with no parameters: the published cases a learner can open.
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ApiError, encApi } from "@/lib/encounter/api";
import { genderWord } from "@/lib/encounter/labels";
import type { CaseSummary, LlmStatus } from "@/lib/encounter/types";
import { Avatar, ErrorCard, inputCls, LoadingCard, ProviderChip, SiteNav, SyntheticLabel } from "./ui";

const ORIGIN_GROUP: Record<string, { title: string; note: string }> = {
  authored: { title: "Emergency department cases", note: "Written for this project. Synthetic; awaiting faculty review." },
  from_template: { title: "Created in the Patient Studio", note: "Published by faculty from a condition template or a description." },
  from_sample_patient: { title: "Organizers' sample patients", note: "Loaded at run time from the organizers' private sample set; not stored in this repository." },
};

function CaseCard({ c }: { c: CaseSummary }) {
  const complaint = c.title;
  return (
    <Link href={`/encounter?case_id=${encodeURIComponent(c.case_id)}`} className="glass group flex flex-col p-4 transition-shadow hover:shadow-[0_1px_0_rgba(255,255,255,0.7)_inset,0_18px_40px_-14px_rgba(47,65,140,0.38)]" data-testid="case-card" data-case-id={c.case_id}>
      <div className="flex items-center gap-3">
        <Avatar name={c.profile.name} image={`/api/cases/${encodeURIComponent(c.case_id)}/image`} size={46} />
        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold tracking-[-0.01em] text-ink">{c.profile.name ?? "Patient"}</div>
          <div className="tnum truncate text-[12px] text-ink-3">
            {c.profile.age != null ? `${c.profile.age} y` : ""}
            {c.profile.gender ? ` · ${genderWord(c.profile.gender)}` : ""}
          </div>
        </div>
      </div>
      <p className="mt-3 line-clamp-2 min-h-[36px] text-[13px] font-medium leading-snug text-ink">{complaint}</p>
      <dl className="mt-2 space-y-0.5 text-[11.5px] text-ink-3">
        {c.learner_role && (
          <div className="flex gap-1.5">
            <dt className="shrink-0">You are</dt>
            <dd className="truncate font-semibold text-ink-2">the {c.learner_role.toLowerCase()}</dd>
          </div>
        )}
        {c.setting && (
          <div className="flex gap-1.5">
            <dt className="shrink-0">Setting</dt>
            <dd className="truncate text-ink-2">{c.setting}</dd>
          </div>
        )}
      </dl>
      <div className="mt-3 flex items-center gap-2">
        <span className="tnum text-[11px] text-ink-3">
          v{c.version} · {c.n_objectives} objective{c.n_objectives === 1 ? "" : "s"}
        </span>
        <span className="btn-primary ml-auto !h-7 !px-3 opacity-90 group-hover:opacity-100">Start</span>
      </div>
    </Link>
  );
}

export function CasePicker() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [llm, setLlm] = useState<LlmStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    let dead = false;
    encApi
      .cases("published")
      .then((c) => !dead && setCases(c))
      .catch((e: ApiError) => !dead && setError(e.message));
    encApi
      .status()
      .then((s) => !dead && setLlm(s.services?.llm ?? null))
      .catch(() => {});
    return () => {
      dead = true;
    };
  }, []);

  const groups = useMemo(() => {
    const needle = q.trim().toLowerCase();
    // cases generated for one simulated patient are opened from the hospital view, not from this list
    const list = (cases ?? []).filter((c) => c.origin?.kind !== "from_sim_patient").filter((c) => !needle || `${c.title} ${c.profile.name} ${c.learner_role} ${c.setting}`.toLowerCase().includes(needle));
    const order = ["from_template", "authored", "from_sample_patient"];
    const by = new Map<string, CaseSummary[]>();
    for (const c of list) {
      const k = c.origin?.kind === "authored" && !c.seed ? "from_template" : (c.origin?.kind ?? "authored");
      by.set(k, [...(by.get(k) ?? []), c]);
    }
    for (const v of by.values()) v.sort((a, b) => (b.updated ?? "").localeCompare(a.updated ?? ""));
    return [...by.entries()].sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]));
  }, [cases, q]);

  return (
    <div className="min-h-screen pb-10">
      <SiteNav current="encounter" right={<ProviderChip llm={llm} />} />
      <div className="mx-auto w-full max-w-[1180px] px-3 pt-5 sm:px-5">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-0 flex-1 basis-72">
            <div className="eyebrow">Encounter</div>
            <h1 className="text-[24px] font-semibold tracking-[-0.02em] text-ink">Choose a patient to see</h1>
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-ink-2">
              You take the clinician&apos;s role. The patient tells you only what the case allows and the chart fills in as you earn it. When you finish you get objective-by-objective feedback with the evidence quoted.
            </p>
          </div>
          <input className={`${inputCls} max-w-[240px]`} placeholder="Search cases…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search cases" />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <SyntheticLabel />
          <span className="text-[11.5px] text-ink-3">
            Faculty: create or edit patients in the{" "}
            <Link href="/studio" className="font-semibold text-accent-dark hover:underline">
              Patient Studio
            </Link>
            . Or open a patient from the{" "}
            <Link href="/" className="font-semibold text-accent-dark hover:underline">
              running hospital
            </Link>
            .
          </span>
        </div>

        {error ? (
          <ErrorCard title="The case list could not be loaded" message={error}>
            <button className="btn-primary" onClick={() => window.location.reload()}>
              Try again
            </button>
            <Link href="/" className="btn-quiet">
              Back to the hospital
            </Link>
          </ErrorCard>
        ) : !cases ? (
          <LoadingCard label="Loading published cases…" />
        ) : groups.length === 0 ? (
          <div className="glass mt-6 p-6 text-[13px] text-ink-2" data-testid="no-cases">
            {q ? "No published case matches that search." : "No case is published yet."}{" "}
            <Link href="/studio" className="font-semibold text-accent-dark hover:underline">
              Create one in the Patient Studio
            </Link>
            .
          </div>
        ) : (
          groups.map(([kind, list]) => (
            <section key={kind} className="mt-6" data-testid="case-group" data-kind={kind}>
              <div className="mb-2 flex flex-wrap items-baseline gap-x-3">
                <h2 className="text-[14px] font-semibold tracking-[-0.01em] text-ink">{ORIGIN_GROUP[kind]?.title ?? kind}</h2>
                <span className="text-[11.5px] text-ink-3">{ORIGIN_GROUP[kind]?.note}</span>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {list.map((c) => (
                  <CaseCard key={c.case_id} c={c} />
                ))}
              </div>
            </section>
          ))
        )}
      </div>
    </div>
  );
}
