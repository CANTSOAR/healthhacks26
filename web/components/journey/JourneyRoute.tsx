"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorCard, LoadingCard } from "@/components/encounter/ui";
import type { ApiError } from "@/lib/encounter/api";
import { journeyApi } from "@/lib/journey/api";
import { JourneyPicker, JourneySetup } from "./JourneyPicker";
import { JourneyView } from "./JourneyView";

const starts = new Map<string, Promise<string>>(); // one journey per simulated patient per page load, even if the effect runs twice

function FromSimulation({ runId, patientId }: { runId: string; patientId: number }) {
  const router = useRouter();
  const [error, setError] = useState<ApiError | null>(null);
  useEffect(() => {
    let dead = false;
    const key = `${runId}:${patientId}`;
    let p = starts.get(key);
    if (!p) {
      p = journeyApi.start({ run_id: runId, patient_id: patientId }).then((j) => j.journey_id);
      starts.set(key, p);
      p.catch(() => starts.delete(key));
    }
    p.then((id) => !dead && router.replace(`/journey?journey_id=${encodeURIComponent(id)}`)).catch((e: ApiError) => !dead && setError(e));
    return () => {
      dead = true;
    };
  }, [runId, patientId, router]);
  if (error)
    return (
      <ErrorCard title={error.status === 404 ? "That simulation run is no longer live" : "The journey could not be opened from the simulation"} message={error.message}>
        <Link href="/" className="btn-primary">
          Back to the hospital
        </Link>
      </ErrorCard>
    );
  return <LoadingCard label="Opening this simulated patient's journey…" />;
}

export function JourneyRoute() {
  const q = useSearchParams();
  const journeyId = q.get("journey_id");
  const caseId = q.get("case_id");
  const runId = q.get("run_id");
  const pid = q.get("patient_id");
  if (journeyId) return <JourneyView key={journeyId} journeyId={journeyId} />;
  if (runId && pid && Number.isFinite(Number(pid))) return <FromSimulation runId={runId} patientId={Number(pid)} />;
  if (caseId) return <JourneySetup key={caseId} caseId={caseId} templateId={q.get("template_id") ?? undefined} />;
  return <JourneyPicker />;
}
