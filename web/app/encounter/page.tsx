import { Suspense } from "react";
import type { Metadata } from "next";
import { EncounterRoute } from "@/components/encounter/EncounterRoute";

export const metadata: Metadata = { title: "Encounter · HospitalGym" };

// /encounter                              -> list of published cases
// /encounter?case_id=<id>                 -> start an encounter with a published case
// /encounter?case_id=<id>&preview=1       -> faculty preview of the latest (unpublished) version
// /encounter?run_id=<run>&patient_id=<n>  -> take over a simulated patient's clinician encounter
// /encounter?encounter_id=<enc>           -> resume or review a session
export default function Page() {
  return (
    <Suspense fallback={null}>
      <EncounterRoute />
    </Suspense>
  );
}
