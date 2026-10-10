import Link from "next/link";

// Placeholder route. The studio workstream replaces this page; the hospital view links here with
// ?run_id=..&patient_id=.. (see contracts/api.md, POST /api/encounters).
export default async function Page({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const q = await searchParams;
  return (
    <main className="flex min-h-screen items-center justify-center bg-ground p-6">
      <div className="glass max-w-md p-6">
        <div className="eyebrow">Patient Studio</div>
        <h1 className="mt-1 text-[20px] font-semibold tracking-[-0.01em] text-ink">Not built yet</h1>
        <p className="mt-2 text-[13px] leading-relaxed text-ink-2">This page is a placeholder for the Patient Studio screen, which is built in a separate workstream.</p>
        {q.patient_id ? (
          <p className="tnum mt-2 text-[12px] text-ink-3">
            Requested: run {q.run_id ?? "–"}, patient {q.patient_id}
          </p>
        ) : null}
        <Link href="/" className="btn-primary mt-4">
          Back to the hospital
        </Link>
      </div>
    </main>
  );
}
