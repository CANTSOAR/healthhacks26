"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { CaseEditor } from "./CaseEditor";
import { StudioList } from "./StudioList";

// /studio              -> all patients
// /studio?new=1        -> all patients with the "New patient" dialog open
// /studio?case=<id>    -> the editor for one patient
export function StudioRoute() {
  const q = useSearchParams();
  const router = useRouter();
  const caseId = q.get("case");
  if (caseId) return <CaseEditor key={caseId} caseId={caseId} onBack={() => router.push("/studio")} />;
  return <StudioList startNew={q.get("new") === "1"} onOpen={(id) => router.push(`/studio?case=${encodeURIComponent(id)}`)} />;
}
