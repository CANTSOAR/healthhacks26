"use client";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CasePicker } from "./CasePicker";
import { EncounterView, selfStarted, type EncounterParams } from "./EncounterView";

function parse(q: URLSearchParams): EncounterParams | null {
  const encounterId = q.get("encounter_id") || undefined;
  const caseId = q.get("case_id") || undefined;
  const runId = q.get("run_id") || undefined;
  const pid = q.get("patient_id");
  const patientId = pid != null && pid !== "" && Number.isFinite(Number(pid)) ? Number(pid) : undefined;
  const v = Number(q.get("version"));
  if (encounterId) return { encounterId };
  if (runId && patientId != null) return { runId, patientId };
  if (caseId) return { caseId, version: Number.isFinite(v) && v > 0 ? v : undefined, preview: q.get("preview") === "1" || q.get("preview") === "true" };
  return null;
}

export function EncounterRoute() {
  const q = useSearchParams();
  const [params, setParams] = useState<EncounterParams | null | undefined>(undefined);
  const qs = q.toString();
  useEffect(() => {
    const p = parse(new URLSearchParams(qs));
    // the view rewrites the address to ?encounter_id=... after starting; that is the same session, not a new request
    if (p?.encounterId && selfStarted.id === p.encounterId) return;
    setParams(p);
  }, [qs]);
  if (params === undefined) return null;
  if (params === null) return <CasePicker />;
  return <EncounterView key={JSON.stringify(params)} params={params} />;
}
