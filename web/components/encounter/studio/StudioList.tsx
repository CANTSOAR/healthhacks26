"use client";
// Patient Studio home: every case with its status, versions and origin, and three ways to start a new patient.
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ApiError, encApi } from "@/lib/encounter/api";
import { genderWord } from "@/lib/encounter/labels";
import type { CaseSummary, CreatedCase, LlmStatus, TemplateSummary } from "@/lib/encounter/types";
import { Avatar, ErrorCard, Field, InlineError, inputCls, LoadingCard, Modal, ProviderChip, SiteNav, Spinner, StatusChip, SyntheticLabel, Tone } from "../ui";

const ORIGINS: { key: string; label: string }[] = [
  { key: "ours", label: "Our cases" },
  { key: "studio", label: "Made in the Studio" },
  { key: "sample", label: "Organizer samples" },
  { key: "sim", label: "From the simulation" },
  { key: "all", label: "All" },
];
function originKey(c: CaseSummary): string {
  const k = c.origin?.kind;
  if (k === "from_sample_patient") return "sample";
  if (k === "from_sim_patient") return "sim";
  if (c.seed) return "seed";
  return "studio";
}
function originLabel(c: CaseSummary): string {
  const k = originKey(c);
  if (k === "sample") return "Organizer sample";
  if (k === "sim") return `Simulated patient ${c.origin.sim_patient_id ?? ""}`;
  if (k === "seed") return "Seed case";
  if (c.origin?.kind === "from_template") return `Template: ${(c.origin.condition_template ?? "").replace(/_/g, " ")}`;
  return "Authored";
}

const DEFAULT_SECTIONS = [
  { section_id: "triage", title: "Triage note", release: "initial" },
  { section_id: "vitals", title: "Vital signs", release: "initial" },
  { section_id: "hpi", title: "History of present illness", release: "on_fact" },
  { section_id: "pmh", title: "Past medical history", release: "on_fact" },
  { section_id: "medications", title: "Medications", release: "on_fact" },
  { section_id: "allergies", title: "Allergies", release: "on_fact" },
  { section_id: "family", title: "Family history", release: "on_fact" },
  { section_id: "social", title: "Social history", release: "on_fact" },
  { section_id: "ros", title: "Review of systems", release: "on_fact" },
  { section_id: "exam", title: "Physical examination", release: "on_request" },
  { section_id: "imaging", title: "ECG and imaging", release: "on_request" },
  { section_id: "labs", title: "Laboratory results", release: "on_request" },
  { section_id: "records", title: "Previous records", release: "on_request" },
];

type Path = "template" | "description" | "form";

function NewPatient({ onClose, onCreated }: { onClose: () => void; onCreated: (c: CreatedCase) => void }) {
  const [path, setPath] = useState<Path>("template");
  const [templates, setTemplates] = useState<TemplateSummary[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // template
  const [tpl, setTpl] = useState("");
  const [band, setBand] = useState("moderate");
  const [tName, setTName] = useState("");
  const [tAge, setTAge] = useState("");
  const [tSex, setTSex] = useState("");
  // description
  const [desc, setDesc] = useState("");
  // form
  const [f, setF] = useState({ name: "", age: "", gender: "female", complaint: "", answer: "", setting: "Emergency department treatment bay", role: "Emergency medicine resident", background: "", personality: "", triage: "", hr: "", bp: "" });

  useEffect(() => {
    encApi
      .templates()
      .then((t) => {
        setTemplates(t);
        if (t[0]) setTpl(t[0].id);
      })
      .catch(() => setTemplates([]));
  }, []);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      let body: Record<string, unknown>;
      if (path === "template") {
        const overrides: Record<string, unknown> = { severity: band, seed: Math.floor(Math.random() * 1e6) + 1 };
        if (tAge) overrides.age = Number(tAge);
        if (tSex) overrides.sex = tSex;
        if (tName.trim()) overrides.profile = { name: tName.trim() };
        body = { from_template: tpl, overrides };
      } else if (path === "description") {
        if (desc.trim().length < 12) throw new ApiError(422, "Describe the patient in a sentence or two first.");
        body = { from_description: desc.trim() };
      } else {
        if (!f.name.trim() || !f.age || !f.complaint.trim()) throw new ApiError(422, "Name, age and presenting complaint are needed to start a draft.");
        const age = Number(f.age);
        const facts: Record<string, unknown>[] = [
          { fact_id: "f.chief_complaint.main", category: "chief_complaint", statement: f.complaint.trim(), patient_knows: true, patient_answer: f.answer.trim() || undefined, topics: ["chief_complaint"], disclosure: { rule: "volunteered" }, critical: true, chart_section: "hpi", polarity: "positive" },
        ];
        if (f.hr) facts.push({ fact_id: "f.vitals.heart_rate", category: "vitals", label: "Heart rate", statement: `Heart rate ${f.hr} beats/min`, value: Number(f.hr), unit: "beats/min", patient_knows: false, disclosure: { rule: "chart_initial" }, chart_section: "vitals" });
        if (f.bp) facts.push({ fact_id: "f.vitals.blood_pressure", category: "vitals", label: "Blood pressure", statement: `Blood pressure ${f.bp} mmHg`, value: f.bp, unit: "mmHg", patient_knows: false, disclosure: { rule: "chart_initial" }, chart_section: "vitals" });
        const triage = f.triage.trim() || `${age}-year-old ${f.gender === "male" ? "man" : f.gender === "female" ? "woman" : "patient"}. ${f.complaint.trim()}`;
        body = {
          title: `${f.complaint.trim().replace(/\.$/, "")} in a ${age}-year-old ${f.gender === "male" ? "man" : f.gender === "female" ? "woman" : "patient"}`,
          setting: f.setting,
          learner_role: f.role,
          intended_learner: "Health professions students",
          prebrief: `You are the ${f.role.toLowerCase()}. ${f.name.trim()}, ${age}, has come in with: ${f.complaint.trim().replace(/\.$/, "").toLowerCase()}. Take a focused history, request the examination and tests you need, and decide on a disposition.`,
          profile: { name: f.name.trim(), age, gender: f.gender, background: f.background.trim() || undefined, personality: f.personality.trim() || undefined },
          facts,
          chart: { sections: DEFAULT_SECTIONS, artifacts: [{ artifact_id: "art.triage_note", kind: "document", title: "Triage note", section_id: "triage", release: { rule: "initial" }, synthetic: true, content: triage }] },
          objectives: [{ objective_id: "obj.presenting_complaint", criterion: "Establishes the presenting complaint with an open question", kind: "elicit_fact", linked_fact_ids: ["f.chief_complaint.main"], critical: true }],
          rubric_id: "default",
          sources: [],
        };
      }
      const created = await encApi.createCase(body);
      onCreated(created);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  const chosen = templates?.find((t) => t.id === tpl);
  return (
    <Modal title="New patient" onClose={busy ? () => {} : onClose} wide>
      <div data-testid="new-patient">
        <div className="seg mb-4 w-full" role="tablist">
          <button className="flex-1" data-on={path === "template"} onClick={() => setPath("template")} data-testid="new-path-template">
            From a condition template
          </button>
          <button className="flex-1" data-on={path === "description"} onClick={() => setPath("description")} data-testid="new-path-description">
            From a description
          </button>
          <button className="flex-1" data-on={path === "form"} onClick={() => setPath("form")} data-testid="new-path-form">
            Blank form
          </button>
        </div>

        {path === "template" && (
          <div className="space-y-3">
            <p className="text-[12.5px] leading-relaxed text-ink-2">Start from a complete synthetic patient for a condition: facts, disclosure rules, chart documents and objectives are filled in for you to edit. The same templates produce the patients in the running hospital.</p>
            {!templates ? (
              <div className="flex items-center gap-2 py-4 text-[12.5px] text-ink-2">
                <Spinner /> Loading templates…
              </div>
            ) : templates.length === 0 ? (
              <InlineError>No condition templates are available from the server.</InlineError>
            ) : (
              <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Condition template">
                {templates.map((t) => (
                  <button key={t.id} role="radio" aria-checked={tpl === t.id} onClick={() => setTpl(t.id)} className={`rounded-xl border p-2.5 text-left transition-colors ${tpl === t.id ? "border-accent bg-accent-soft" : "border-line bg-white/70 hover:border-accent/30"}`} data-testid="template-card" data-template-id={t.id}>
                    <span className={`block text-[12.5px] font-semibold ${tpl === t.id ? "text-accent-dark" : "text-ink"}`}>{t.label}</span>
                    <span className="mt-0.5 line-clamp-2 block text-[11px] leading-snug text-ink-3">{t.description}</span>
                    <span className="tnum mt-1 block text-[10.5px] text-ink-3">
                      {t.n_facts} facts · {t.n_objectives} objectives{t.typical_concealments?.length ? ` · ${t.typical_concealments.length} guarded` : ""}
                    </span>
                  </button>
                ))}
              </div>
            )}
            <div className="grid gap-3 sm:grid-cols-4">
              <Field label="Severity">
                <select className={`${inputCls} cursor-pointer`} value={band} onChange={(e) => setBand(e.target.value)} data-testid="tpl-severity">
                  {(chosen?.bands ?? ["mild", "moderate", "severe"]).map((b) => (
                    <option key={b} value={b}>
                      {b.charAt(0).toUpperCase() + b.slice(1)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Name (optional)">
                <input className={inputCls} value={tName} onChange={(e) => setTName(e.target.value)} placeholder="Generated if empty" data-testid="tpl-name" />
              </Field>
              <Field label="Age (optional)">
                <input className={`${inputCls} tnum`} type="number" min={18} max={100} value={tAge} onChange={(e) => setTAge(e.target.value)} placeholder="18 or over" data-testid="tpl-age" />
              </Field>
              <Field label="Sex (optional)">
                <select className={`${inputCls} cursor-pointer`} value={tSex} onChange={(e) => setTSex(e.target.value)} data-testid="tpl-sex">
                  <option value="">Either</option>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                </select>
              </Field>
            </div>
          </div>
        )}

        {path === "description" && (
          <div className="space-y-3">
            <p className="text-[12.5px] leading-relaxed text-ink-2">Describe the patient in your own words. The closest condition template is chosen and the name, age and anything the patient is hiding are taken from your text. Clinical findings come from the template, not from the description, so review every fact.</p>
            <Field label="Description">
              <textarea className={`${inputCls} min-h-[120px]`} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="e.g. A 34-year-old teacher named Maya Okafor with two days of fever and burning when she passes urine. She is hiding that she took her sister's leftover antibiotics." data-testid="desc-text" />
            </Field>
          </div>
        )}

        {path === "form" && (
          <div className="space-y-3">
            <p className="text-[12.5px] leading-relaxed text-ink-2">Start with the essentials and add the rest in the editor: more facts, chart documents, objectives and sources.</p>
            <div className="grid gap-3 sm:grid-cols-4">
              <Field label="Patient name" className="sm:col-span-2">
                <input className={inputCls} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="form-name" />
              </Field>
              <Field label="Age">
                <input className={`${inputCls} tnum`} type="number" min={0} max={120} value={f.age} onChange={(e) => setF({ ...f, age: e.target.value })} data-testid="form-age" />
              </Field>
              <Field label="Gender">
                <select className={`${inputCls} cursor-pointer`} value={f.gender} onChange={(e) => setF({ ...f, gender: e.target.value })} data-testid="form-gender">
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                  <option value="nonbinary">Non-binary</option>
                </select>
              </Field>
              <Field label="Presenting complaint (clinical wording)" className="sm:col-span-4">
                <input className={inputCls} value={f.complaint} onChange={(e) => setF({ ...f, complaint: e.target.value })} placeholder="e.g. Sudden severe headache for three hours" data-testid="form-complaint" />
              </Field>
              <Field label="How the patient says it" className="sm:col-span-4" hint="First person. Drafted from the clinical wording if left empty.">
                <input className={inputCls} value={f.answer} onChange={(e) => setF({ ...f, answer: e.target.value })} placeholder="e.g. I've got the worst headache of my life. It came on out of nowhere." data-testid="form-answer" />
              </Field>
              <Field label="Setting" className="sm:col-span-2">
                <input className={inputCls} value={f.setting} onChange={(e) => setF({ ...f, setting: e.target.value })} />
              </Field>
              <Field label="Learner role" className="sm:col-span-2">
                <input className={inputCls} value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} />
              </Field>
              <Field label="Heart rate (optional)">
                <input className={`${inputCls} tnum`} type="number" value={f.hr} onChange={(e) => setF({ ...f, hr: e.target.value })} placeholder="beats/min" data-testid="form-hr" />
              </Field>
              <Field label="Blood pressure (optional)">
                <input className={`${inputCls} tnum`} value={f.bp} onChange={(e) => setF({ ...f, bp: e.target.value })} placeholder="120/80" data-testid="form-bp" />
              </Field>
              <Field label="Personality (optional)" className="sm:col-span-2">
                <input className={inputCls} value={f.personality} onChange={(e) => setF({ ...f, personality: e.target.value })} placeholder="e.g. Anxious, talks fast" />
              </Field>
              <Field label="Background (optional)" className="sm:col-span-4">
                <input className={inputCls} value={f.background} onChange={(e) => setF({ ...f, background: e.target.value })} placeholder="Work, home, who they live with" />
              </Field>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-3">
            <InlineError>{error}</InlineError>
          </div>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="min-w-0 flex-1 basis-56 text-[11.5px] leading-snug text-ink-3">Creates a <b className="font-semibold text-ink-2">draft</b>. Nothing reaches learners until you approve and publish it.</span>
          <button className="btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn-primary" onClick={create} disabled={busy || (path === "template" && !tpl)} data-testid="new-create">
            {busy ? (
              <>
                <Spinner size={12} /> Creating…
              </>
            ) : (
              "Create draft"
            )}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export function StudioList({ onOpen, startNew }: { onOpen: (caseId: string) => void; startNew?: boolean }) {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [llm, setLlm] = useState<LlmStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [origin, setOrigin] = useState("ours");
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(!!startNew);

  useEffect(() => {
    let dead = false;
    encApi
      .cases()
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

  const counts = useMemo(() => {
    const c: Record<string, number> = { ours: 0, studio: 0, sample: 0, sim: 0, all: 0 };
    (cases ?? []).forEach((x) => {
      const k = originKey(x);
      c.all++;
      if (k === "seed" || k === "studio") c.ours++;
      if (k === "studio") c.studio++;
      if (k === "sample") c.sample++;
      if (k === "sim") c.sim++;
    });
    return c;
  }, [cases]);
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (cases ?? [])
      .filter((c) => {
        const k = originKey(c);
        const inOrigin = origin === "all" || (origin === "ours" ? k === "seed" || k === "studio" : k === origin);
        return inOrigin && (!status || c.status === status) && (!needle || `${c.title} ${c.profile.name} ${c.case_id}`.toLowerCase().includes(needle));
      })
      .sort((a, b) => (b.updated ?? "").localeCompare(a.updated ?? ""));
  }, [cases, q, status, origin]);

  return (
    <div className="min-h-screen pb-12" data-testid="studio-list">
      <SiteNav current="studio" right={<ProviderChip llm={llm} />} />
      <div className="mx-auto w-full max-w-[1180px] px-3 pt-5 sm:px-5">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-0 flex-1 basis-72">
            <div className="eyebrow">Patient Studio · faculty</div>
            <h1 className="text-[24px] font-semibold tracking-[-0.02em] text-ink">Patients</h1>
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-ink-2">Create a patient, decide what they will say and when, attach the chart, set the objectives, then validate, approve and publish. No code and no JSON editing is needed; a published patient can be interviewed straight away.</p>
          </div>
          <button className="btn-primary !h-10 !px-5 !text-[13.5px]" onClick={() => setCreating(true)} data-testid="new-patient-btn">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" aria-hidden>
              <path d="M12 5v14M5 12h14" />
            </svg>
            New patient
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <div className="seg" role="tablist" aria-label="Status">
            {["", "draft", "approved", "published"].map((s) => (
              <button key={s} data-on={status === s} onClick={() => setStatus(s)} data-testid={`status-${s || "all"}`}>
                {s ? s.charAt(0).toUpperCase() + s.slice(1) : "Any status"}
              </button>
            ))}
          </div>
          <select className="select" value={origin} onChange={(e) => setOrigin(e.target.value)} aria-label="Origin" data-testid="origin-filter">
            {ORIGINS.filter((o) => o.key === "all" || o.key === "ours" || counts[o.key] > 0).map((o) => (
              <option key={o.key} value={o.key}>
                {o.label} ({counts[o.key]})
              </option>
            ))}
          </select>
          <input className={`${inputCls} max-w-[220px]`} placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search patients" />
          <span className="ml-auto">
            <SyntheticLabel />
          </span>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-line bg-white/50 px-3 py-2 text-[11.5px] text-ink-2">
          <span className="font-semibold text-ink">Lifecycle</span>
          <span>
            <StatusChip status="draft" /> edit freely
          </span>
          <span aria-hidden>→</span>
          <span>
            <StatusChip status="approved" /> validated and reviewed
          </span>
          <span aria-hidden>→</span>
          <span>
            <StatusChip status="published" /> available to learners, immutable; editing starts a new draft version
          </span>
        </div>

        {error ? (
          <ErrorCard title="The patient list could not be loaded" message={error}>
            <button className="btn-primary" onClick={() => window.location.reload()}>
              Try again
            </button>
          </ErrorCard>
        ) : !cases ? (
          <LoadingCard label="Loading patients…" />
        ) : (
          <div className="glass mt-3 overflow-hidden">
            <div className="hidden grid-cols-[1.5fr_1.6fr_110px_150px_150px] gap-3 border-b border-line bg-white/40 px-4 py-2 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-3 md:grid">
              <span>Patient</span>
              <span>Case</span>
              <span>Status</span>
              <span>Origin</span>
              <span className="text-right">Actions</span>
            </div>
            {rows.map((c) => (
              <div key={c.case_id} className="grid grid-cols-1 items-center gap-x-3 gap-y-2 border-b border-line px-4 py-3 last:border-b-0 hover:bg-white/50 md:grid-cols-[1.5fr_1.6fr_110px_150px_150px]" data-testid="studio-row" data-case-id={c.case_id} data-status={c.status}>
                <button className="flex min-w-0 items-center gap-3 text-left" onClick={() => onOpen(c.case_id)}>
                  <Avatar name={c.profile.name} image={`/api/cases/${encodeURIComponent(c.case_id)}/image`} size={36} />
                  <span className="min-w-0">
                    <span className="block truncate text-[13.5px] font-semibold text-ink">{c.profile.name ?? "Unnamed"}</span>
                    <span className="tnum block truncate text-[11.5px] text-ink-3">
                      {c.profile.age != null ? `${c.profile.age} y` : ""}
                      {c.profile.gender ? ` · ${genderWord(c.profile.gender)}` : ""}
                    </span>
                  </span>
                </button>
                <div className="min-w-0">
                  <div className="truncate text-[12.5px] text-ink">{c.title}</div>
                  <div className="tnum truncate text-[11px] text-ink-3">
                    {c.n_facts} facts · {c.n_objectives} objectives{c.updated ? ` · updated ${new Date(c.updated).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}` : ""}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <StatusChip status={c.status} />
                  <span className="tnum text-[11px] font-medium text-ink-3" title={c.versions.length > 1 ? `Versions: ${c.versions.join(", ")}` : undefined}>
                    v{c.version}
                    {c.versions.length > 1 ? ` of ${c.versions.length}` : ""}
                  </span>
                </div>
                <div>
                  <Tone bg="rgba(20,26,51,0.06)" fg="#4A5275">
                    {originLabel(c)}
                  </Tone>
                </div>
                <div className="flex items-center gap-1.5 md:justify-end">
                  <button className="btn-quiet !h-7" onClick={() => onOpen(c.case_id)} data-testid="row-open">
                    {c.status === "published" ? "Open" : "Edit"}
                  </button>
                  {(c.status === "published" || c.versions.length > 1) && (
                    <Link href={`/encounter?case_id=${encodeURIComponent(c.case_id)}`} className="btn-primary !h-7" title="Start an encounter with the published version">
                      Start
                    </Link>
                  )}
                </div>
              </div>
            ))}
            {rows.length === 0 && (
              <div className="px-4 py-10 text-center text-[13px] text-ink-3" data-testid="studio-empty">
                No patient matches these filters.{" "}
                <button className="font-semibold text-accent-dark hover:underline" onClick={() => setCreating(true)}>
                  Create one
                </button>
                .
              </div>
            )}
          </div>
        )}
      </div>
      {creating && (
        <NewPatient
          onClose={() => setCreating(false)}
          onCreated={(c) => {
            try {
              window.sessionStorage.setItem(`hg.studio.created.${c.case_id}`, JSON.stringify({ notes: c.notes, validation: c.validation }));
            } catch {
              /* ignore */
            }
            onOpen(c.case_id);
          }}
        />
      )}
    </div>
  );
}
