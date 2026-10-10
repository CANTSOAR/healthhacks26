import { Suspense } from "react";
import type { Metadata } from "next";
import { JourneyRoute } from "@/components/journey/JourneyRoute";

export const metadata: Metadata = { title: "Care journey · HospitalGym" };

// /journey                                   -> choose a published patient
// /journey?case_id=<id>[&template_id=<t>]    -> choose a journey template for that patient and start
// /journey?run_id=<run>&patient_id=<n>       -> open a simulated patient's journey (default template)
// /journey?journey_id=<jrn>                  -> play, resume or review a journey
export default function Page() {
  return (
    <Suspense fallback={null}>
      <JourneyRoute />
    </Suspense>
  );
}
