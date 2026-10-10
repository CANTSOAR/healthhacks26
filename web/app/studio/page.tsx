import { Suspense } from "react";
import type { Metadata } from "next";
import { StudioRoute } from "@/components/encounter/studio/StudioRoute";

export const metadata: Metadata = { title: "Patient Studio · HospitalGym" };

export default function Page() {
  return (
    <Suspense fallback={null}>
      <StudioRoute />
    </Suspense>
  );
}
