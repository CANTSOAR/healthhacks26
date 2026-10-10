"use client";
// /journey with no journey yet: choose a patient, then a journey template for that patient.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Avatar, ErrorCard, InlineError, LoadingCard, SiteNav, Spinner, SyntheticLabel, Tone } from "@/components/encounter/ui";
import { ApiError, encApi } from "@/lib/encounter/api";
import type { CaseSummary, StudentCaseView } from "@/lib/encounter/types";
import { journeyApi, roleTone, TYPE_LABEL } from "@/lib/journey/api";
import type { TemplateSummary } from "@/lib/journey/types";
import { RoleAvatar } from "./StageRail";

const here = (
  <span className="chip" style={{ background: "#2F55F5", color: "#fff" }}>
    Care journey
  </span>
);

function Intro() {
  return (
    <div className="max-w-3xl">
      <div className="eyebrow">Care journey</div>
      <h1 className="text-[24px] font-semibold tracking-[-0.02em] text-ink">One patient, several professions, one record</h1>
      <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
        The same patient is seen in a chain of connected interactions. Take any role; a sampled AI colleague fills the stages you do not play. Every role reads and writes one shared record, and each entry shows who added it, in which stage, and where it came from. The last stage is an SBAR handoff, checked against what the team
        actually learned.
      </p>
    </div>
  );
}

export function JourneyPicker() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let dead = false;
    encApi
      .cases("published")
      .then((c) => !dead && setCases(c))
      .catch((e: ApiError) => !dead && setError(e.message));
    return () => {
      dead = true;
    };
  }, []);
  const list = useMemo(() => (cases ?? []).filter((c) => c.origin?.kind !== "from_sim_patient"), [cases]);
  return (
    <div className="min-h-screen pb-10" data-testid="journey-picker">
      <SiteNav current={"journey" as never} right={here} />
      <div className="mx-auto w-full max-w-[1180px] px-3 pt-5 sm:px-5">
        <Intro />
        <div className="mt-3">
          <SyntheticLabel />
        </div>
        {error ? (
          <ErrorCard title="The case list could not be loaded" message={error}>
            <button className="btn-primary" onClick={() => window.location.reload()}>
              Try again
            </button>
          </ErrorCard>
        ) : !cases ? (
          <LoadingCard label="Loading published patients…" />
        ) : (
          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((c) => (
              <Link key={c.case_id} href={`/journey?case_id=${encodeURIComponent(c.case_id)}`} className="glass block p-4 transition-shadow hover:ring-1 hover:ring-accent/30" data-testid="journey-case" data-case={c.case_id}>
                <div className="flex items-center gap-3">
                  <Avatar name={c.profile.name} image={`/api/cases/${c.case_id}/image`} size={44} />
                  <div className="min-w-0">
                    <div className="truncate text-[14px] font-semibold text-ink">{c.profile.name}</div>
                    <div className="truncate text-[11.5px] text-ink-3">
                      {c.profile.age ? `${c.profile.age} y` : ""} {c.profile.gender ?? ""}
                    </div>
                  </div>
                </div>
                <div className="mt-2 text-[12.5px] leading-snug text-ink-2">{c.title}</div>
                <div className="mt-2 text-[11.5px] font-semibold text-accent-dark">Start a journey →</div>
              </Link>
            ))}
            {!list.length && (
              <div className="glass p-5 text-[13px] text-ink-2">
                No patient is published yet.{" "}
                <Link href="/studio" className="font-semibold text-accent-dark hover:underline">
                  Create one in the Patient Studio
                </Link>
                ; it gets a journey as soon as it is published.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function JourneySetup({ caseId, templateId }: { caseId: string; templateId?: string }) {
  const router = useRouter();
  const [kase, setKase] = useState<StudentCaseView | null>(null);
  const [templates, setTemplates] = useState<TemplateSummary[] | null>(null);
  const [chosen, setChosen] = useState<string | null>(templateId ?? null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  useEffect(() => {
    let dead = false;
    Promise.all([encApi.caseStudent(caseId), journeyApi.templates(caseId)])
      .then(([c, t]) => {
        if (dead) return;
        setKase(c);
        setTemplates(t);
        setChosen((cur) => (cur && t.some((x) => x.journey_id === cur) ? cur : (t.find((x) => x.default)?.journey_id ?? t[0]?.journey_id ?? null)));
      })
      .catch((e: ApiError) => !dead && setError({ status: e.status, message: e.message }));
    return () => {
      dead = true;
    };
  }, [caseId]);
  async function start() {
    if (!chosen) return;
    setBusy(true);
    setStartError(null);
    try {
      const j = await journeyApi.start({ case_id: caseId, template_id: chosen });
      router.replace(`/journey?journey_id=${encodeURIComponent(j.journey_id)}`);
    } catch (e) {
      setStartError((e as ApiError).message + ((e as ApiError).status === 409 ? " Only published patients can start a journey." : ""));
      setBusy(false);
    }
  }
  if (error)
    return (
      <ErrorCard title={error.status === 404 ? "That patient was not found" : "The journey could not be set up"} message={error.message}>
        <Link href="/journey" className="btn-primary">
          Choose a patient
        </Link>
      </ErrorCard>
    );
  if (!kase || !templates) return <LoadingCard label="Loading the patient and the journey templates…" />;
  return (
    <div className="min-h-screen pb-10" data-testid="journey-setup">
      <SiteNav current={"journey" as never} right={here} />
      <div className="mx-auto w-full max-w-[1180px] px-3 pt-5 sm:px-5">
        <Intro />
        <div className="glass mt-4 flex flex-wrap items-center gap-3 p-4">
          <Avatar name={kase.patient.name} image={kase.patient.image} size={52} />
          <div className="min-w-0 flex-1 basis-60">
            <div className="text-[17px] font-semibold tracking-[-0.01em] text-ink" data-testid="setup-patient">
              {kase.patient.name}
            </div>
            <div className="text-[12.5px] text-ink-2">{kase.case.title}</div>
          </div>
          <SyntheticLabel review={kase.case.needs_faculty_review !== false} />
          <Link href="/journey" className="btn-quiet">
            Another patient
          </Link>
        </div>
        <h2 className="mb-2 mt-5 text-[14px] font-semibold text-ink">Choose a journey</h2>
        <div className="grid gap-3 lg:grid-cols-2">
          {templates.map((t) => {
            const on = chosen === t.journey_id;
            return (
              <button key={t.journey_id} onClick={() => setChosen(t.journey_id)} className={`glass p-4 text-left transition-shadow ${on ? "ring-2 ring-accent/60" : "hover:ring-1 hover:ring-accent/25"}`} data-testid="journey-template" data-template={t.journey_id} data-on={on}>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-[15px] font-semibold tracking-[-0.01em] text-ink">{t.title}</div>
                  <Tone bg={t.any_case ? "rgba(20,26,51,0.06)" : "#E3E9FF"} fg={t.any_case ? "#4A5275" : "#1F3FD1"}>
                    {t.any_case ? "Works with any patient" : "Written for this patient"}
                  </Tone>
                </div>
                <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">{t.description}</p>
                <ol className="mt-3 grid gap-1.5">
                  {t.stages.map((s, i) => (
                    <li key={s.stage_id} className="flex items-center gap-2 text-[12px] text-ink">
                      <RoleAvatar staffRole={s.learner_role.staff_role} name={s.learner_role.label} size={24} />
                      <span className="font-semibold">
                        {i + 1}. {s.title}
                      </span>
                      <span className="chip" style={{ background: roleTone(s.learner_role.staff_role).bg, color: roleTone(s.learner_role.staff_role).fg }}>
                        {s.learner_role.label}
                      </span>
                      <span className="truncate text-[11px] text-ink-3">{TYPE_LABEL[s.interaction_type] ?? s.interaction_type}</span>
                    </li>
                  ))}
                </ol>
              </button>
            );
          })}
        </div>
        {startError && (
          <div className="mt-3">
            <InlineError>{startError}</InlineError>
          </div>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button className="btn-primary !h-10 !px-5 !text-[13px]" disabled={!chosen || busy} onClick={start} data-testid="journey-start">
            {busy && <Spinner size={12} />} Start the journey
          </button>
          <span className="text-[12px] text-ink-3">You choose stage by stage which role to play; the sampler resolves any stage you skip.</span>
        </div>
      </div>
    </div>
  );
}
