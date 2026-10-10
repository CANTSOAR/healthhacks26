"use client";
// One case in the Patient Studio: edit, validate, preview, approve, publish, start an encounter.
import { SiteDisclaimer } from "../../ui/SiteDisclaimer";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, encApi } from "@/lib/encounter/api";
import { genderWord } from "@/lib/encounter/labels";
import type { CaseDoc, RubricSummary, ValidationReport } from "@/lib/encounter/types";
import { Avatar, ErrorCard, InlineError, LoadingCard, SiteNav, Spinner, StatusChip, SyntheticLabel, Tone } from "../ui";
import { flatten, IssueCtx, IssueList, issuesUnder, worst, type Issue } from "./fields";
import { ChartTab, FactsTab, JsonTab, ObjectivesTab, OverviewTab, SourcesTab } from "./tabs";

type TabKey = "overview" | "facts" | "chart" | "objectives" | "sources" | "json";
const TABS: { key: TabKey; label: string; paths: string[] }[] = [
  { key: "overview", label: "Patient and case", paths: ["/title", "/profile", "/prebrief", "/setting", "/learner_role", "/intended_learner", "/faculty_truth", "/rubric_id", "/unknown_response", "/origin", "/review"] },
  { key: "facts", label: "Facts", paths: ["/facts"] },
  { key: "chart", label: "Chart and documents", paths: ["/chart"] },
  { key: "objectives", label: "Objectives", paths: ["/objectives"] },
  { key: "sources", label: "Sources", paths: ["/sources"] },
  { key: "json", label: "Raw JSON", paths: [] },
];
const tabOf = (path: string): TabKey => TABS.find((t) => t.paths.some((p) => path === p || path.startsWith(p + "/")))?.key ?? "overview";

/** Only the author's content goes back to the server; ids, version and status are the server's. */
function payload(c: CaseDoc): Record<string, unknown> {
  const { case_id: _a, version: _b, status: _c, updated: _d, versions: _e, seed: _f, ...rest } = c as CaseDoc & Record<string, unknown>;
  void _a, _b, _c, _d, _e, _f;
  delete rest.validation;
  delete rest.notes;
  delete rest.created_from;
  delete rest.new_version_created;
  return rest;
}

function originWord(c: CaseDoc): string {
  const k = c.origin?.kind;
  if (k === "from_template") return `From the “${(c.origin.condition_template ?? "").replace(/_/g, " ")}” condition template`;
  if (k === "from_sim_patient") return `Generated from simulated patient ${c.origin.sim_patient_id ?? ""}`;
  if (k === "from_sample_patient") return "Organizers' sample patient (loaded from the private folder at run time)";
  return c.seed ? "Seed case authored for this project" : "Authored in the Studio";
}

function Step({ n, label, state, hint }: { n: number; label: string; state: "done" | "current" | "todo"; hint: string }) {
  const color = state === "done" ? "#2FA36B" : state === "current" ? "#2F55F5" : "#B4BAD1";
  return (
    <div className="flex min-w-0 items-center gap-2" title={hint} data-testid="lifecycle-step" data-state={state}>
      <span className="tnum flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white" style={{ background: color }}>
        {state === "done" ? "✓" : n}
      </span>
      <span className="min-w-0">
        <span className={`block text-[12px] font-semibold leading-tight ${state === "todo" ? "text-ink-3" : "text-ink"}`}>{label}</span>
        <span className="hidden text-[10.5px] leading-tight text-ink-3 xl:block">{hint}</span>
      </span>
    </div>
  );
}

export function CaseEditor({ caseId, onBack }: { caseId: string; onBack: () => void }) {
  const [saved, setSaved] = useState<CaseDoc | null>(null);
  const [draft, setDraft] = useState<CaseDoc | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [rubrics, setRubrics] = useState<RubricSummary[]>([]);
  const [tab, setTab] = useState<TabKey>("overview");
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [reportStale, setReportStale] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [ack, setAck] = useState<{ warnings: string[]; read: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [showAll, setShowAll] = useState(false);
  const loaded = useRef(false);

  useEffect(() => {
    let dead = false;
    loaded.current = false;
    setSaved(null);
    setDraft(null);
    setReport(null);
    encApi
      .caseFaculty(caseId)
      .then((c) => {
        if (dead) return;
        setSaved(c);
        setDraft(structuredClone(c));
        loaded.current = true;
        try {
          const k = `hg.studio.created.${caseId}`;
          const raw = window.sessionStorage.getItem(k);
          if (raw) {
            const j = JSON.parse(raw) as { notes?: string[]; validation?: ValidationReport };
            setNotes(j.notes ?? []);
            if (j.validation) setReport(j.validation);
            window.sessionStorage.removeItem(k);
          }
        } catch {
          /* ignore */
        }
      })
      .catch((e: ApiError) => !dead && setLoadError(e.message));
    encApi
      .rubrics()
      .then((r) => !dead && setRubrics(r))
      .catch(() => {});
    return () => {
      dead = true;
    };
  }, [caseId]);

  const dirty = useMemo(() => !!draft && !!saved && JSON.stringify(payload(draft)) !== JSON.stringify(payload(saved)), [draft, saved]);
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault();
    };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [dirty]);

  const up = useCallback((fn: (d: CaseDoc) => void) => {
    setDraft((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      fn(next);
      return next;
    });
    setReportStale(true);
    setNotice(null);
  }, []);

  const run = async (name: string, fn: () => Promise<void>) => {
    setBusy(name);
    setError(null);
    setNotice(null);
    try {
      await fn();
    } catch (e) {
      const a = e as ApiError;
      setError(a.message);
      if (a.report) {
        setReport(a.report);
        setReportStale(false);
        setShowAll(true);
      }
    } finally {
      setBusy(null);
    }
  };
  const adopt = (c: CaseDoc & { validation?: ValidationReport }) => {
    const { validation, ...rest } = c;
    const doc = { ...(rest as CaseDoc), versions: (rest as CaseDoc).versions ?? [...new Set([...(saved?.versions ?? []), rest.version])], seed: (rest as CaseDoc).seed ?? false };
    setSaved(doc);
    setDraft(structuredClone(doc));
    if (validation) {
      setReport(validation);
      setReportStale(false);
    }
  };
  /** Saves when there are unsaved edits. Returns the stored document. */
  const saveIfDirty = async (): Promise<CaseDoc> => {
    if (!draft || !saved) throw new ApiError(0, "The case is not loaded.");
    if (!dirty) return saved;
    const r = await encApi.updateCase(caseId, payload(draft));
    adopt(r);
    if (r.new_version_created) setNotice(`Version ${saved.version} is published and stays as it is. Your edits were saved as version ${r.version}, a new draft.`);
    return r;
  };
  const save = () =>
    run("save", async () => {
      const before = saved?.version;
      const r = await saveIfDirty();
      if (r.version === before) setNotice("Saved. The case is a draft until it is approved again.");
    });
  const validate = () =>
    run("validate", async () => {
      if (!draft) return;
      const v = await encApi.validateCase(caseId, payload(draft));
      setReport(v);
      setReportStale(false);
      setShowAll(true);
      const n = flatten(v);
      setNotice(v.ok ? (n.length ? `Valid, with ${n.length} warning${n.length === 1 ? "" : "s"} to review. It can be approved.` : "Valid. No errors, warnings or contradictions.") : null);
      if (!v.ok) setError(`${v.errors.length} error${v.errors.length === 1 ? "" : "s"} and ${v.consistency.filter((x) => x.level !== "warning").length} contradiction(s) must be fixed before approval. They are shown next to the fields.`);
    });
  // Approval is two steps when the case has attention-level warnings (a thin case, say): the server refuses the first
  // request and lists them; the reviewer ticks that they have read them; the second request records that.
  const approve = (acknowledged = false) =>
    run("approve", async () => {
      await saveIfDirty();
      try {
        const c = await encApi.approveCase(caseId, acknowledged);
        setAck(null);
        adopt(c);
        setNotice(acknowledged ? "Approved, with the warnings acknowledged. Publish it to make it available to learners." : "Approved. Review is recorded; publish it to make it available to learners.");
      } catch (e) {
        const d = (e as { status?: number; detail?: { needs_acknowledgement?: boolean; warnings?: unknown[] } }) ?? {};
        if (d.status === 409 && d.detail?.needs_acknowledgement) {
          const list = (d.detail.warnings ?? []).map((w) => (typeof w === "string" ? w : String((w as { message?: string }).message ?? JSON.stringify(w))));
          setAck({ warnings: list, read: false });
          return;
        }
        throw e;
      }
    });
  const publish = () =>
    run("publish", async () => {
      const c = await encApi.publishCase(caseId);
      adopt(c);
      setNotice(`Published as version ${c.version}. This version can no longer be changed; an edit will start version ${c.version + 1} as a draft.`);
    });
  const preview = () =>
    run("preview", async () => {
      await saveIfDirty();
      window.open(`/encounter?case_id=${encodeURIComponent(caseId)}&preview=1`, "_blank");
    });

  const issues: Issue[] = useMemo(() => flatten(report), [report]);

  if (loadError)
    return (
      <>
        <SiteNav current="studio" />
        <ErrorCard title="This case could not be opened" message={loadError}>
          <button className="btn-primary" onClick={onBack}>
            Back to all patients
          </button>
        </ErrorCard>
      </>
    );
  if (!draft || !saved)
    return (
      <>
        <SiteNav current="studio" />
        <LoadingCard label="Opening the case…" />
      </>
    );

  const status = saved.status;
  const blocking = issues.filter((i) => i.level !== "warning").length;
  const warnings = issues.length - blocking;
  const isPublished = status === "published";
  const versions = saved.versions ?? [saved.version];

  return (
    <IssueCtx.Provider value={issues}>
      <div className="min-h-screen pb-16" data-testid="case-editor" data-case-id={caseId} data-status={status} data-version={saved.version} data-dirty={dirty}>
        <SiteNav current="studio" />
        <div className="mx-auto w-full max-w-[1240px] px-3 pt-4 sm:px-5">
          {/* identity + lifecycle */}
          <div className="glass p-4">
            <div className="flex flex-wrap items-center gap-3">
              <button className="btn-quiet !h-7 !px-2.5" onClick={onBack} data-testid="back-to-list">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M19 12H5M11 6l-6 6 6 6" />
                </svg>
                All patients
              </button>
              <Avatar name={draft.profile.name} image={`/api/cases/${encodeURIComponent(caseId)}/image`} size={40} />
              <div className="min-w-0 flex-1 basis-56">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="truncate text-[18px] font-semibold tracking-[-0.015em] text-ink" data-testid="editor-title">
                    {draft.profile.name || "Unnamed patient"}
                  </h1>
                  <span className="tnum text-[12.5px] text-ink-2">
                    {draft.profile.age ? `${draft.profile.age} y` : ""}
                    {draft.profile.gender ? ` · ${genderWord(draft.profile.gender)}` : ""}
                  </span>
                  <StatusChip status={status} />
                  <Tone bg="rgba(20,26,51,0.06)" fg="#4A5275" title={versions.length > 1 ? `Versions: ${versions.join(", ")}` : "First version"}>
                    <span data-testid="version-chip">v{saved.version}</span>
                    {versions.length > 1 ? ` of ${versions.length}` : ""}
                  </Tone>
                  {dirty && (
                    <Tone bg="#FFF1D6" fg="#9A5B00">
                      <span data-testid="dirty-chip">Unsaved changes</span>
                    </Tone>
                  )}
                </div>
                <div className="mt-0.5 truncate text-[12px] text-ink-3">
                  {draft.title} · {originWord(saved)}
                </div>
              </div>
              <SyntheticLabel />
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border border-line bg-white/55 px-3 py-2.5">
              <Step n={1} label="Draft" state={status === "draft" ? "current" : "done"} hint="Edit freely; any save returns to draft" />
              <span className="hidden h-px w-6 bg-ink-4 sm:block" />
              <Step n={2} label="Approved" state={status === "approved" ? "current" : status === "published" ? "done" : "todo"} hint="Must validate with no errors" />
              <span className="hidden h-px w-6 bg-ink-4 sm:block" />
              <Step n={3} label="Published" state={status === "published" ? "current" : "todo"} hint="Immutable; learners can start it" />
              <div className="ml-auto flex flex-wrap items-center gap-1.5">
                <button className="btn-quiet" onClick={save} disabled={!dirty || !!busy} data-testid="btn-save">
                  {busy === "save" ? <Spinner size={12} /> : null}
                  {isPublished ? `Save as draft v${Math.max(...versions) + 1}` : "Save draft"}
                </button>
                <button className="btn-quiet" onClick={validate} disabled={!!busy} data-testid="btn-validate">
                  {busy === "validate" ? <Spinner size={12} /> : null}
                  Validate
                </button>
                <button className="btn-quiet" onClick={preview} disabled={!!busy} title="Opens a test encounter with the latest saved version in a new tab. It is marked as a preview and is never offered to learners." data-testid="btn-preview">
                  Preview
                </button>
                <button className={status === "draft" ? "btn-primary" : "btn-quiet"} onClick={() => void approve(false)} disabled={!!busy || (status !== "draft" && !dirty)} title={status === "draft" || dirty ? "Validates, then records the review" : "Already approved"} data-testid="btn-approve">
                  {busy === "approve" ? <Spinner size={12} /> : null}
                  Approve
                </button>
                <button className={status === "approved" && !dirty ? "btn-primary" : "btn-quiet"} onClick={publish} disabled={!!busy || status !== "approved" || dirty} title={status === "approved" ? (dirty ? "Save and approve your edits first" : "Makes this version available to learners; it can no longer be changed") : status === "published" ? "This version is already published" : "Only an approved version can be published"} data-testid="btn-publish">
                  {busy === "publish" ? <Spinner size={12} /> : null}
                  Publish
                </button>
              </div>
            </div>

            {isPublished && !dirty && (
              <div className="mt-3 flex flex-wrap items-center gap-3 rounded-xl border border-[#BFE5CF] bg-[#F1FAF5] px-4 py-3" data-testid="published-banner">
                <div className="min-w-0 flex-1 basis-64">
                  <div className="text-[13.5px] font-semibold text-[#1F7A4D]">Version {saved.version} is published and available to learners.</div>
                  <div className="text-[12px] leading-snug text-ink-2">A published version is immutable. If you edit and save, version {Math.max(...versions) + 1} starts as a new draft and this one stays live until that draft is approved and published.</div>
                </div>
                <Link href={`/encounter?case_id=${encodeURIComponent(caseId)}`} className="btn-primary !h-10 !px-5 !text-[13.5px]" data-testid="start-encounter">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M8 5l11 7-11 7z" />
                  </svg>
                  Start encounter with this patient
                </Link>
              </div>
            )}
            {isPublished && dirty && (
              <div className="mt-3 rounded-xl border border-[#EBCB85] bg-[#FFF8E6] px-4 py-2.5 text-[12.5px] leading-snug text-[#7A4A00]" data-testid="new-version-warning">
                You are editing a published version. It will not change: saving creates <b>version {Math.max(...versions) + 1}</b> as a draft, and version {saved.version} stays available to learners.
              </div>
            )}
            {!isPublished && versions.length > 1 && (
              <div className="mt-3 text-[12px] text-ink-3">
                Earlier published version{versions.length > 2 ? "s" : ""} of this patient ({versions.filter((v) => v !== saved.version).map((v) => `v${v}`).join(", ")}) stay available to learners until this one is published.
              </div>
            )}

            {ack && (
              <div className="mt-3 rounded-xl border border-[#E0A21B]/40 bg-[#FFF6DF] px-4 py-3" data-testid="ack-warnings" role="alertdialog" aria-label="Warnings to acknowledge before approval">
                <div className="text-[12.5px] font-semibold text-[#7A4E00]">Before this case is approved, read these warnings</div>
                <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[12px] leading-snug text-[#7A4E00]">
                  {ack.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
                <label className="mt-2 flex items-center gap-2 text-[12px] font-medium text-ink">
                  <input type="checkbox" checked={ack.read} onChange={(e) => setAck({ ...ack, read: e.target.checked })} data-testid="ack-read" />
                  I have read these and want to approve the case as it is
                </label>
                <div className="mt-2 flex gap-2">
                  <button className="btn-primary !h-7" disabled={!ack.read || !!busy} onClick={() => void approve(true)} data-testid="ack-approve">
                    Approve with warnings acknowledged
                  </button>
                  <button className="btn-quiet !h-7" onClick={() => setAck(null)}>
                    Go back and edit
                  </button>
                </div>
              </div>
            )}
            {notes.length > 0 && (
              <div className="mt-3 rounded-xl border border-accent/20 bg-accent-soft/60 px-4 py-2.5" data-testid="creation-notes">
                <div className="eyebrow" style={{ color: "#1F3FD1" }}>
                  How this draft was made
                </div>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[12.5px] leading-snug text-ink">
                  {notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              </div>
            )}
            {error && (
              <div className="mt-3" data-testid="editor-error">
                <InlineError>{error}</InlineError>
              </div>
            )}
            {notice && (
              <div className="mt-3 rounded-xl border border-[#BFE5CF] bg-[#F1FAF5] px-3 py-2 text-[12.5px] font-medium text-[#1F7A4D]" data-testid="editor-notice" role="status">
                {notice}
              </div>
            )}

            {report && (
              <div className="mt-3 rounded-xl border border-line bg-white/60 px-3 py-2.5" data-testid="validation-summary" data-ok={String(report.ok)}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[12.5px] font-semibold text-ink">Validation</span>
                  <Tone bg={report.ok ? "#E3F4EA" : "#FDE7E7"} fg={report.ok ? "#1F7A4D" : "#B4232C"}>
                    {report.ok ? "Can be approved" : `${blocking} to fix`}
                  </Tone>
                  {warnings > 0 && (
                    <Tone bg="#FFF4DC" fg="#7A4A00">
                      {warnings} warning{warnings === 1 ? "" : "s"}
                    </Tone>
                  )}
                  {reportStale && <span className="text-[11.5px] text-ink-3">Edited since this check. Validate again to refresh.</span>}
                  {issues.length > 0 && (
                    <button className="btn ml-auto !h-6 !px-2 text-[11.5px]" onClick={() => setShowAll((v) => !v)}>
                      {showAll ? "Hide list" : "Show all findings"}
                    </button>
                  )}
                </div>
                {showAll && issues.length > 0 && (
                  <ul className="mt-2 max-h-56 space-y-1 overflow-y-auto pr-1 scroll-thin">
                    {[...issues]
                      .sort((a, b) => (a.level === "warning" ? 1 : 0) - (b.level === "warning" ? 1 : 0))
                      .map((i, k) => (
                        <li key={k} className="flex items-start gap-2">
                          <button className="mt-0.5 shrink-0 rounded bg-[#141a33]/[0.06] px-1.5 py-0.5 text-[10.5px] font-semibold text-accent-dark hover:bg-accent-soft" onClick={() => setTab(tabOf(i.path))} title={`Go to ${i.path}`} data-testid="issue-jump">
                            {TABS.find((t) => t.key === tabOf(i.path))?.label}
                          </button>
                          <div className="min-w-0 flex-1 [&>ul]:mt-0">
                            <IssueList items={[i]} />
                          </div>
                        </li>
                      ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          {/* tabs */}
          {/* on a phone the six tabs wrap onto two rows instead of running off the right edge */}
          <div className="sticky top-[70px] z-20 mt-3 pb-1">
            <div className="seg max-w-full flex-wrap shadow-pill !bg-white/95 backdrop-blur max-sm:!rounded-2xl" role="tablist" data-testid="editor-tabs">
              {TABS.map((t) => {
                const w = worst(t.paths.flatMap((p) => issuesUnder(issues, p)));
                const count = t.key === "facts" ? draft.facts.length : t.key === "objectives" ? draft.objectives.length : t.key === "chart" ? (draft.chart.artifacts?.length ?? 0) : t.key === "sources" ? draft.sources.length : null;
                return (
                  <button key={t.key} role="tab" aria-selected={tab === t.key} data-on={tab === t.key} onClick={() => setTab(t.key)} data-testid={`tab-${t.key}`}>
                    <span className="inline-flex items-center gap-1.5">
                      {t.label}
                      {count != null && <span className="tnum text-[10.5px] font-medium text-ink-3">{count}</span>}
                      {w && <span className="h-1.5 w-1.5 rounded-full" style={{ background: w === "error" ? "#D8434C" : "#E0A100" }} />}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-3">
            {tab === "overview" && <OverviewTab c={draft} up={up} rubrics={rubrics} />}
            {tab === "facts" && <FactsTab c={draft} up={up} />}
            {tab === "chart" && <ChartTab c={draft} up={up} />}
            {tab === "objectives" && <ObjectivesTab c={draft} up={up} rubrics={rubrics} />}
            {tab === "sources" && <SourcesTab c={draft} up={up} />}
            {tab === "json" && (
              <JsonTab
                c={draft}
                onReplace={(d) => {
                  setDraft(d);
                  setReportStale(true);
                }}
              />
            )}
          </div>
        </div>
        <SiteDisclaimer className="mt-8" />
      </div>
    </IssueCtx.Provider>
  );
}
