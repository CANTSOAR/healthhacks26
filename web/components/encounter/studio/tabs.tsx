"use client";
// The editor's tabs: every part of a case (contracts/case.schema.json) as forms, plus a raw-JSON escape hatch.
import { useMemo, useState } from "react";
import { requestLabel, RULE_HELP, RULE_LABEL, RULE_TONE } from "@/lib/encounter/labels";
import type { ArtifactDef, CaseDoc, Fact, LabRow, Objective, RubricSummary } from "@/lib/encounter/types";
import { InlineError, inputCls, Tone } from "../ui";
import { Area, Check, Csv, F, IdPicker, IssueDot, Issues, Lines, Num, Panel, RemoveBtn, Select, slug, Text } from "./fields";

export type Up = (fn: (d: CaseDoc) => void) => void;
interface TabProps {
  c: CaseDoc;
  up: Up;
}
const CAT_WORD: Record<string, string> = { chief_complaint: "Chief complaint", hpi: "History (HPI)", pmh: "Past history", medications: "Medications", allergies: "Allergies", social: "Social", family: "Family", ros: "Review of systems", exam: "Examination", vitals: "Vital signs", lab: "Laboratory", imaging: "ECG / imaging", diagnosis: "Diagnosis", risk: "Risk", identity: "Identity", concealed: "Concealed" };
const catWord = (x: string) => CAT_WORD[x] ?? x.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const opts = (xs: string[], label?: (x: string) => string) => xs.map((x) => ({ value: x, label: label ? label(x) : x.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) }));

const CATEGORIES = ["chief_complaint", "hpi", "pmh", "medications", "allergies", "social", "family", "ros", "exam", "vitals", "lab", "imaging", "diagnosis", "risk", "identity", "concealed"];
const RULES = ["volunteered", "if_asked", "after_rapport", "denied_until_confronted", "chart_initial", "on_request"];
const ARTIFACT_KINDS = ["lab_report", "ecg", "xray", "ct", "prior_note", "medication_list", "document", "image"];
const KIND_WORD: Record<string, string> = { lab_report: "Lab report", ecg: "ECG report", xray: "X-ray report", ct: "CT report", prior_note: "Previous note", medication_list: "Medication list", document: "Document", image: "Image" };
const OBJ_KINDS = ["elicit_fact", "action", "communication", "sequencing", "reasoning", "safety"];
const SOURCE_ROLES = ["evidence_for_fact", "objective_rationale", "teaching_artifact", "organizer_sample", "template"];
const COMMON_REQUESTS = ["exam:general", "exam:cardiac", "exam:lungs", "exam:abdomen", "exam:neuro", "exam:msk", "exam:skin", "exam:mental_status", "order:ecg", "order:troponin", "order:cbc", "order:bmp", "order:lft", "order:lipase", "order:urinalysis", "order:pregnancy_test", "order:tox_screen", "order:ethanol", "order:lactate", "order:chest_xray", "order:xray", "order:ct_head", "order:ct_abdomen", "order:ultrasound", "order:prior_records", "order:medication_list"];

function useRefs(c: CaseDoc) {
  return useMemo(() => {
    const facts = c.facts.map((f) => ({ id: f.fact_id, label: `${f.statement || "(no statement)"}` }));
    const artifacts = (c.chart.artifacts ?? []).map((a) => ({ id: a.artifact_id, label: `${KIND_WORD[a.kind] ?? a.kind}: ${a.title}` }));
    const sections = c.chart.sections.map((s) => ({ value: s.section_id, label: s.title || s.section_id }));
    const requests = [...new Set([...c.facts.map((f) => f.disclosure?.request), ...(c.chart.artifacts ?? []).map((a) => a.release?.request), ...COMMON_REQUESTS].filter(Boolean) as string[])];
    return { facts, artifacts, sections, requests };
  }, [c]);
}

function RequestList({ id, requests }: { id: string; requests: string[] }) {
  return (
    <datalist id={id}>
      {requests.map((r) => (
        <option key={r} value={r}>
          {requestLabel(r)}
        </option>
      ))}
    </datalist>
  );
}

// ---------------------------------------------------------------- overview
export function OverviewTab({ c, up, rubrics }: TabProps & { rubrics: RubricSummary[] }) {
  const ft = c.faculty_truth ?? {};
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Case" note="What the learner is told before the encounter starts.">
        <div className="grid gap-3 sm:grid-cols-2">
          <F label="Title" path="/title" className="sm:col-span-2">
            <Text value={c.title} onChange={(v) => up((d) => void (d.title = v))} path="/title" testid="f-title" />
          </F>
          <F label="Setting" path="/setting">
            <Text value={c.setting} onChange={(v) => up((d) => void (d.setting = v))} placeholder="Emergency department treatment bay" />
          </F>
          <F label="Learner role" path="/learner_role">
            <Text value={c.learner_role} onChange={(v) => up((d) => void (d.learner_role = v))} placeholder="Emergency medicine resident" />
          </F>
          <F label="Intended learner" path="/intended_learner" className="sm:col-span-2">
            <Text value={c.intended_learner} onChange={(v) => up((d) => void (d.intended_learner = v))} />
          </F>
          <F label="Pre-brief (learner sees this)" path="/prebrief" className="sm:col-span-2">
            <Area rows={3} value={c.prebrief} onChange={(v) => up((d) => void (d.prebrief = v))} path="/prebrief" testid="f-prebrief" />
          </F>
          <F label="When asked about something the case does not define, the patient says" path="/unknown_response" className="sm:col-span-2" hint="The patient never invents a clinical fact; this line is the fallback.">
            <Text value={c.unknown_response} onChange={(v) => up((d) => void (d.unknown_response = v))} />
          </F>
        </div>
      </Panel>

      <Panel title="Patient profile and persona" note="Drives how the patient speaks. It is never a source of clinical facts.">
        <Issues path="/profile" skip={["name", "age", "gender"]} />
        <div className="grid gap-3 sm:grid-cols-4">
          <F label="Name" path="/profile/name" className="sm:col-span-2">
            <Text value={c.profile.name} onChange={(v) => up((d) => void (d.profile.name = v))} path="/profile/name" testid="f-name" />
          </F>
          <F label="Age" path="/profile/age">
            <Num value={c.profile.age} min={0} max={120} onChange={(v) => up((d) => void (d.profile.age = v ?? 0))} path="/profile/age" testid="f-age" />
          </F>
          <F label="Gender" path="/profile/gender">
            <Text value={c.profile.gender} onChange={(v) => up((d) => void (d.profile.gender = v))} path="/profile/gender" />
          </F>
          <F label="Background" className="sm:col-span-4">
            <Area value={c.profile.background} onChange={(v) => up((d) => void (d.profile.background = v))} placeholder="Work, home, who they live with" />
          </F>
          <F label="Personality" className="sm:col-span-2">
            <Area value={c.profile.personality} onChange={(v) => up((d) => void (d.profile.personality = v))} />
          </F>
          <F label="Speech style" className="sm:col-span-2">
            <Area value={c.profile.speech_style} onChange={(v) => up((d) => void (d.profile.speech_style = v))} />
          </F>
          <F label="Race / ethnicity (optional)" className="sm:col-span-2">
            <Text value={c.profile.race_ethnicity} onChange={(v) => up((d) => void (d.profile.race_ethnicity = v || undefined))} />
          </F>
          <F label="Voice id (optional)" className="sm:col-span-2" hint="Used only when a speech service is configured.">
            <Text value={c.profile.voice} onChange={(v) => up((d) => void (d.profile.voice = v || undefined))} />
          </F>
        </div>
      </Panel>

      <Panel title="Faculty truth" note="Faculty only. Never sent to the learner's browser or to the patient role-play. Released as a debrief after the encounter is finished.">
        <Issues path="/faculty_truth" skip={["diagnosis", "expected_disposition", "expected_orders"]} />
        <div className="grid gap-3 sm:grid-cols-2">
          <F label="Diagnosis" path="/faculty_truth/diagnosis" className="sm:col-span-2">
            <Text value={ft.diagnosis} onChange={(v) => up((d) => void ((d.faculty_truth ??= {}).diagnosis = v))} path="/faculty_truth/diagnosis" />
          </F>
          <F label="Differential (comma-separated)" className="sm:col-span-2">
            <Csv value={ft.differential} onChange={(v) => up((d) => void ((d.faculty_truth ??= {}).differential = v))} />
          </F>
          <F label="Expected disposition" path="/faculty_truth/expected_disposition">
            <Select value={ft.expected_disposition ?? ""} onChange={(v) => up((d) => void ((d.faculty_truth ??= {}).expected_disposition = v || undefined))} options={[{ value: "", label: "Not set" }, ...opts(["discharge", "admit", "transfer"])]} />
          </F>
          <F label="Expected requests (comma-separated)" path="/faculty_truth/expected_orders" hint="e.g. order:ecg, order:troponin">
            <Csv value={ft.expected_orders} onChange={(v) => up((d) => void ((d.faculty_truth ??= {}).expected_orders = v))} path="/faculty_truth/expected_orders" />
          </F>
          <F label="Teaching points (one per line)" className="sm:col-span-2">
            <Lines value={ft.teaching_points} onChange={(v) => up((d) => void ((d.faculty_truth ??= {}).teaching_points = v))} />
          </F>
        </div>
      </Panel>

      <Panel title="Rubric" note="Which rubric the grader scores domains against. The organizers' Patient Encounter Performance Rubric is the default when it is present on this machine.">
        <F label="Rubric" path="/rubric_id">
          <Select
            value={c.rubric_id}
            onChange={(v) => up((d) => void (d.rubric_id = v))}
            path="/rubric_id"
            testid="f-rubric"
            options={[{ value: "default", label: `Default${rubrics.find((r) => r.is_default) ? ` (${rubrics.find((r) => r.is_default)!.title})` : ""}` }, ...rubrics.map((r) => ({ value: r.rubric_id, label: r.title }))]}
          />
        </F>
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {(rubrics.find((r) => r.rubric_id === c.rubric_id) ?? rubrics.find((r) => r.is_default))?.domains?.map((d) => (
            <li key={d.key} className="chip" style={{ background: "rgba(20,26,51,0.06)", color: "#4A5275" }}>
              {d.name}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------- facts
function renameFact(d: CaseDoc, from: string, to: string) {
  const swap = (xs?: string[]) => xs?.map((x) => (x === from ? to : x));
  d.facts.forEach((f) => {
    if (f.disclosure.confront_with) f.disclosure.confront_with = swap(f.disclosure.confront_with);
  });
  d.objectives.forEach((o) => (o.linked_fact_ids = swap(o.linked_fact_ids)));
  (d.chart.artifacts ?? []).forEach((a) => {
    a.linked_fact_ids = swap(a.linked_fact_ids);
    if (a.release.fact_id === from) a.release.fact_id = to;
    if (Array.isArray(a.content)) (a.content as LabRow[]).forEach((r) => r && typeof r === "object" && r.fact_id === from && (r.fact_id = to));
  });
  d.sources.forEach((s) => (s.supports = swap(s.supports)));
}

function FactEditor({ f, i, c, up }: { f: Fact; i: number; c: CaseDoc; up: Up }) {
  const refs = useRefs(c);
  const p = `/facts/${i}`;
  const rule = f.disclosure?.rule;
  const guarded = rule === "after_rapport" || rule === "denied_until_confronted";
  const set = (fn: (x: Fact) => void) => up((d) => fn(d.facts[i]));
  return (
    <div className="border-t border-line bg-white/50 px-3 pb-3 pt-3" data-testid="fact-editor">
      <Issues path={p} skip={["statement", "patient_answer", "cover_answer", "topics", "disclosure", "chart_section", "category", "fact_id"]} />
      <div className="grid gap-3 md:grid-cols-6">
        <F label="Fact id" path={`${p}/fact_id`} className="md:col-span-2" hint="Stable id; renaming updates every link to it.">
          <Text
            value={f.fact_id}
            path={`${p}/fact_id`}
            onChange={(v) =>
              up((d) => {
                renameFact(d, d.facts[i].fact_id, v);
                d.facts[i].fact_id = v;
              })
            }
          />
        </F>
        <F label="Category" path={`${p}/category`} className="md:col-span-2">
          <Select value={f.category} onChange={(v) => set((x) => void (x.category = v))} options={opts(CATEGORIES, catWord)} testid="fact-category" />
        </F>
        <F label="Shown in chart section" path={`${p}/chart_section`} className="md:col-span-2">
          <Select value={f.chart_section ?? ""} onChange={(v) => set((x) => void (x.chart_section = v || undefined))} options={[{ value: "", label: "Chosen from the category" }, ...refs.sections]} path={`${p}/chart_section`} />
        </F>
        <F label="Statement (clinical wording, faculty truth)" path={`${p}/statement`} className="md:col-span-6">
          <Area value={f.statement} onChange={(v) => set((x) => void (x.statement = v))} path={`${p}/statement`} testid="fact-statement" />
        </F>
        <F label="Patient's answer when it is disclosed" path={`${p}/patient_answer`} className="md:col-span-3" hint="First person, the patient's own words. The offline patient says exactly this.">
          <Area value={f.patient_answer} onChange={(v) => set((x) => void (x.patient_answer = v))} path={`${p}/patient_answer`} testid="fact-answer" />
        </F>
        <F label={guarded ? "Cover answer while it is withheld" : "Cover answer (used only by guarded rules)"} path={`${p}/cover_answer`} className="md:col-span-3" hint="What the patient says instead until the rule is satisfied. Leave empty for a neutral deflection.">
          <Area value={f.cover_answer} onChange={(v) => set((x) => void (x.cover_answer = v || undefined))} path={`${p}/cover_answer`} testid="fact-cover" />
        </F>
        <F label="Topics and trigger phrases (comma-separated)" path={`${p}/topics`} className="md:col-span-6" hint="Shared topic keys (onset, radiation, smoking, alcohol, drugs, medications, allergies, family_history, occupation, mood…) or your own phrases. A question that touches one counts as asking about this fact.">
          <Csv value={f.topics} onChange={(v) => set((x) => void (x.topics = v))} path={`${p}/topics`} testid="fact-topics" />
        </F>

        <div className="rounded-xl border border-line bg-white/70 p-3 md:col-span-6">
          <div className="grid gap-3 md:grid-cols-6">
            <F label="Disclosure rule" path={`${p}/disclosure/rule`} className="md:col-span-2">
              <Select
                value={rule}
                testid="fact-rule"
                path={`${p}/disclosure/rule`}
                onChange={(v) =>
                  set((x) => {
                    const prev = x.disclosure ?? { rule: "if_asked" };
                    x.disclosure = { rule: v as Fact["disclosure"]["rule"] };
                    if (v === "after_rapport") x.disclosure.rapport_needed = prev.rapport_needed ?? 3;
                    if (v === "denied_until_confronted") x.disclosure.confront_with = prev.confront_with ?? [];
                    if (v === "on_request") x.disclosure.request = prev.request ?? "";
                  })
                }
                options={opts(RULES, (r) => RULE_LABEL[r] ?? r)}
              />
            </F>
            <div className="md:col-span-4">
              {rule === "after_rapport" && (
                <F label="Rapport points needed" path={`${p}/disclosure/rapport_needed`} hint="An introduction, an open question, naming a feeling or normalising each add a point. 3 to 5 is typical.">
                  <Num value={f.disclosure.rapport_needed} min={1} max={12} onChange={(v) => set((x) => void (x.disclosure.rapport_needed = v))} path={`${p}/disclosure/rapport_needed`} testid="fact-rapport" />
                </F>
              )}
              {rule === "denied_until_confronted" && (
                <F label="Evidence the learner must have seen first" path={`${p}/disclosure/confront_with`}>
                  <IdPicker values={f.disclosure.confront_with} options={[...refs.artifacts, ...refs.facts.filter((x) => x.id !== f.fact_id)]} onChange={(v) => set((x) => void (x.disclosure.confront_with = v))} placeholder="Add a chart document or fact…" testid="fact-confront" />
                </F>
              )}
              {rule === "on_request" && (
                <F label="Released by request" path={`${p}/disclosure/request`} hint="exam:<name> or order:<name>, e.g. order:troponin">
                  <Text value={f.disclosure.request} onChange={(v) => set((x) => void (x.disclosure.request = v))} path={`${p}/disclosure/request`} list="hg-requests" testid="fact-request" />
                </F>
              )}
              <p className="mt-1 text-[11.5px] leading-snug text-ink-3">{RULE_HELP[rule] ?? ""}</p>
            </div>
            <Issues path={`${p}/disclosure`} skip={["rule", "rapport_needed", "confront_with", "request"]} />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 md:col-span-6">
          <Check value={f.critical} onChange={(v) => set((x) => void (x.critical = v || undefined))} label="Critical finding" hint="Missing a critical finding lowers the encounter's quality score." testid="fact-critical" />
          <Check value={f.patient_knows} onChange={(v) => set((x) => void (x.patient_knows = v))} label="The patient knows this" hint="Untick for findings only an examination or a test can show." />
          <label className="inline-flex items-center gap-2 text-[12px] text-ink-2">
            Polarity
            <select className={`${inputCls} !w-auto cursor-pointer !py-1 text-[12px]`} value={f.polarity ?? ""} onChange={(e) => set((x) => void (x.polarity = (e.target.value || undefined) as Fact["polarity"]))}>
              <option value="">not set</option>
              <option value="positive">present</option>
              <option value="negative">known negative</option>
              <option value="unknown">unknown</option>
            </select>
          </label>
          <span className="ml-auto">
            <RemoveBtn
              label="Delete fact"
              onClick={() =>
                up((d) => {
                  d.facts.splice(i, 1);
                })
              }
            />
          </span>
        </div>
      </div>
    </div>
  );
}

export function FactsTab({ c, up }: TabProps) {
  const [open, setOpen] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const refs = useRefs(c);
  const cats = [...new Set(c.facts.map((f) => f.category))];
  const rows = c.facts.map((f, i) => ({ f, i })).filter(({ f }) => (!cat || f.category === cat) && (!q || `${f.fact_id} ${f.statement} ${f.patient_answer ?? ""}`.toLowerCase().includes(q.toLowerCase())));
  const add = () => {
    let n = c.facts.length + 1;
    let id = `f.hpi.new_${n}`;
    while (c.facts.some((f) => f.fact_id === id)) id = `f.hpi.new_${++n}`;
    up((d) => {
      d.facts.push({ fact_id: id, category: "hpi", statement: "", patient_knows: true, patient_answer: "", topics: [], disclosure: { rule: "if_asked" } });
    });
    setQ("");
    setCat("");
    setOpen(id);
  };
  return (
    <Panel
      title={`Facts (${c.facts.length})`}
      note="Each fact is one thing that is true about this patient, with the wording the patient uses and the rule that decides when the learner gets it. The patient can only ever say what is written here."
      testid="facts-panel"
      right={
        <button className="btn-primary" onClick={add} data-testid="add-fact">
          Add fact
        </button>
      }
    >
      <RequestList id="hg-requests" requests={refs.requests} />
      <Issues path="/facts" skip={c.facts.map((_, i) => String(i))} />
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <input className={`${inputCls} max-w-[260px]`} placeholder="Search facts…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search facts" data-testid="fact-search" />
        <select className="select" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Filter by category">
          <option value="">All categories</option>
          {cats.map((x) => (
            <option key={x} value={x}>
              {catWord(x)}
            </option>
          ))}
        </select>
        <span className="ml-auto flex flex-wrap gap-1">
          {RULES.map((r) => {
            const n = c.facts.filter((f) => f.disclosure?.rule === r).length;
            return n ? (
              <Tone key={r} bg={RULE_TONE[r].bg} fg={RULE_TONE[r].fg} title={RULE_HELP[r]}>
                {RULE_LABEL[r]} · {n}
              </Tone>
            ) : null;
          })}
        </span>
      </div>
      <div className="overflow-hidden rounded-xl border border-line">
        <div className="hidden grid-cols-[110px_1fr_170px_70px] gap-3 bg-[#141a33]/[0.04] px-3 py-1.5 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-3 md:grid">
          <span>Category</span>
          <span>Statement</span>
          <span>Disclosure rule</span>
          <span className="text-right">Flags</span>
        </div>
        {rows.map(({ f, i }) => {
          const isOpen = open === f.fact_id;
          const t = RULE_TONE[f.disclosure?.rule] ?? RULE_TONE.chart_initial;
          return (
            <div key={i} className="border-t border-line first:border-t-0 md:first:border-t" data-testid="fact-row" data-fact-id={f.fact_id} data-open={isOpen}>
              <button className={`grid w-full grid-cols-1 items-center gap-x-3 gap-y-1 px-3 py-2 text-left transition-colors hover:bg-accent-soft/50 md:grid-cols-[110px_1fr_170px_70px] ${isOpen ? "bg-accent-soft/60" : "bg-white/60"}`} onClick={() => setOpen(isOpen ? null : f.fact_id)} aria-expanded={isOpen} data-testid="fact-toggle">
                <span className="text-[11.5px] font-semibold text-ink-2" data-category={f.category}>{catWord(f.category)}</span>
                <span className="min-w-0">
                  <span className="block truncate text-[13px] text-ink">{f.statement || <em className="text-ink-3">No statement yet</em>}</span>
                  <span className="block truncate text-[11px] text-ink-3">{f.fact_id}</span>
                </span>
                <span>
                  <Tone bg={t.bg} fg={t.fg}>
                    {RULE_LABEL[f.disclosure?.rule] ?? f.disclosure?.rule ?? "no rule"}
                    {f.disclosure?.rule === "after_rapport" && f.disclosure.rapport_needed ? ` · ${f.disclosure.rapport_needed}` : ""}
                    {f.disclosure?.rule === "on_request" && f.disclosure.request ? ` · ${requestLabel(f.disclosure.request)}` : ""}
                  </Tone>
                </span>
                <span className="flex items-center justify-start gap-1.5 md:justify-end">
                  {f.critical && (
                    <span className="chip" style={{ background: "rgba(20,26,51,0.06)", color: "#4A5275" }} title="Critical finding">
                      Key
                    </span>
                  )}
                  <IssueDot path={`/facts/${i}`} />
                </span>
              </button>
              {isOpen && <FactEditor f={f} i={i} c={c} up={up} />}
            </div>
          );
        })}
        {rows.length === 0 && <div className="bg-white/60 px-3 py-6 text-center text-[12.5px] text-ink-3">{c.facts.length ? "No fact matches." : "No facts yet. Add the presenting complaint first."}</div>}
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------- chart
function LabRows({ rows, onChange, facts, path }: { rows: LabRow[]; onChange: (r: LabRow[]) => void; facts: { id: string; label: string }[]; path: string }) {
  const set = (i: number, patch: Partial<LabRow>) => onChange(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  const cell = `${inputCls} !rounded-md !px-1.5 !py-1 text-[12px]`;
  return (
    <div data-testid="lab-editor">
      <div className="scroll-thin overflow-x-auto">
        <table className="w-full min-w-[640px] border-separate border-spacing-x-1 border-spacing-y-1 text-left">
          <thead>
            <tr className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-3">
              <th className="font-semibold">Test</th>
              <th className="w-[84px] font-semibold">Value</th>
              <th className="w-[92px] font-semibold">Unit</th>
              <th className="w-[150px] font-semibold">Reference range</th>
              <th className="w-[100px] font-semibold">Flag</th>
              <th className="w-[150px] font-semibold">Linked fact</th>
              <th className="w-6" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} data-testid="lab-edit-row">
                <td>
                  <input className={cell} value={r.test ?? ""} onChange={(e) => set(i, { test: e.target.value })} placeholder="Test" data-testid="lab-test" />
                </td>
                <td>
                  <input className={`${cell} tnum`} value={String(r.value ?? "")} onChange={(e) => set(i, { value: e.target.value !== "" && !isNaN(Number(e.target.value)) ? Number(e.target.value) : e.target.value })} placeholder="Value" data-testid="lab-value" />
                </td>
                <td>
                  <input className={cell} value={r.unit ?? ""} onChange={(e) => set(i, { unit: e.target.value })} placeholder="Unit" data-testid="lab-unit" />
                </td>
                <td>
                  <input className={`${cell} tnum`} value={r.ref_range ?? ""} onChange={(e) => set(i, { ref_range: e.target.value })} placeholder="e.g. 3.5-5.0" data-testid="lab-ref" />
                </td>
                <td>
                  <select className={`${cell} cursor-pointer`} value={r.flag ?? ""} onChange={(e) => set(i, { flag: e.target.value })} data-testid="lab-flag">
                    <option value="">normal</option>
                    <option value="H">H</option>
                    <option value="L">L</option>
                    <option value="C">critical</option>
                  </select>
                </td>
                <td>
                  <select className={`${cell} cursor-pointer`} value={r.fact_id ?? ""} onChange={(e) => set(i, { fact_id: e.target.value || undefined })}>
                    <option value="">none</option>
                    {facts.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.label.slice(0, 60)}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <button type="button" className="text-[14px] text-ink-3 hover:text-[#B4232C]" aria-label="Remove row" onClick={() => onChange(rows.filter((_, k) => k !== i))}>
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn-quiet mt-1 !h-7" onClick={() => onChange([...rows, { test: "", value: "", unit: "", ref_range: "", flag: "" }])} data-testid="lab-add-row">
        Add row
      </button>
      <Issues path={path} />
    </div>
  );
}

function ArtifactEditor({ a, i, c, up }: { a: ArtifactDef; i: number; c: CaseDoc; up: Up }) {
  const refs = useRefs(c);
  const p = `/chart/artifacts/${i}`;
  const set = (fn: (x: ArtifactDef) => void) => up((d) => fn(d.chart.artifacts![i]));
  const isLab = a.kind === "lab_report";
  return (
    <div className="rounded-xl border border-line bg-white/65 p-3" data-testid="artifact-editor" data-artifact-id={a.artifact_id}>
      <Issues path={p} skip={["title", "content", "release", "section_id", "linked_fact_ids"]} />
      <div className="grid gap-3 md:grid-cols-6">
        <F label="Title" path={`${p}/title`} className="md:col-span-3">
          <Text value={a.title} onChange={(v) => set((x) => void (x.title = v))} path={`${p}/title`} testid="artifact-title" />
        </F>
        <F label="Kind" className="md:col-span-1">
          <Select
            value={a.kind}
            onChange={(v) =>
              set((x) => {
                x.kind = v;
                if (v === "lab_report" && !Array.isArray(x.content)) x.content = [];
                if (v !== "lab_report" && Array.isArray(x.content)) x.content = "";
              })
            }
            options={ARTIFACT_KINDS.map((k) => ({ value: k, label: KIND_WORD[k] }))}
          />
        </F>
        <F label="Chart section" path={`${p}/section_id`} className="md:col-span-2">
          <Select value={a.section_id ?? ""} onChange={(v) => set((x) => void (x.section_id = v || undefined))} options={[{ value: "", label: "None" }, ...refs.sections]} path={`${p}/section_id`} />
        </F>
        <F label="Release timing" path={`${p}/release`} className="md:col-span-2" skip={["request", "fact_id"]}>
          <Select
            value={a.release?.rule}
            testid="artifact-release"
            onChange={(v) =>
              set((x) => {
                x.release = { rule: v as ArtifactDef["release"]["rule"] };
                if (v === "on_request") x.release.request = "";
                if (v === "on_fact") x.release.fact_id = "";
              })
            }
            options={[
              { value: "initial", label: "Initial: in the chart from the start" },
              { value: "on_request", label: "On request: when the learner asks for it" },
              { value: "on_fact", label: "On fact: when a fact is disclosed" },
            ]}
          />
        </F>
        {a.release?.rule === "on_request" && (
          <F label="Released by request" path={`${p}/release/request`} className="md:col-span-2" hint="e.g. order:cbc, order:ecg, order:prior_records">
            <Text value={a.release.request} onChange={(v) => set((x) => void (x.release.request = v))} list="hg-requests-chart" path={`${p}/release/request`} testid="artifact-request" />
          </F>
        )}
        {a.release?.rule === "on_fact" && (
          <F label="Released when this fact is disclosed" path={`${p}/release/fact_id`} className="md:col-span-2">
            <Select value={a.release.fact_id ?? ""} onChange={(v) => set((x) => void (x.release.fact_id = v))} options={[{ value: "", label: "Choose a fact…" }, ...refs.facts.map((f) => ({ value: f.id, label: f.label.slice(0, 70) }))]} path={`${p}/release/fact_id`} />
          </F>
        )}
        {a.release?.rule !== "initial" && (
          <F label="Delay (turns)" className="md:col-span-2" hint="0 = at once. A delayed result shows as pending.">
            <Num value={a.release?.delay_turns} min={0} max={20} onChange={(v) => set((x) => void (x.release.delay_turns = v || undefined))} />
          </F>
        )}
        <div className="md:col-span-6">
          <span className="mb-1 block text-[11px] font-semibold text-ink-2">{isLab ? "Results" : a.kind === "ecg" || a.kind === "xray" || a.kind === "ct" ? "Report text (findings as the learner reads them)" : "Text"}</span>
          {isLab ? (
            <LabRows rows={Array.isArray(a.content) ? (a.content as LabRow[]) : []} onChange={(r) => set((x) => void (x.content = r))} facts={refs.facts} path={`${p}/content`} />
          ) : (
            <>
              <Area rows={4} value={typeof a.content === "string" ? a.content : a.content ? JSON.stringify(a.content) : ""} onChange={(v) => set((x) => void (x.content = v))} path={`${p}/content`} testid="artifact-content" />
              <Issues path={`${p}/content`} />
            </>
          )}
        </div>
        <F label="Author's interpretation (faculty only until the debrief)" className="md:col-span-6">
          <Area value={a.interpretation} onChange={(v) => set((x) => void (x.interpretation = v || undefined))} />
        </F>
        <F label="Facts this document shows" path={`${p}/linked_fact_ids`} className="md:col-span-5" hint="These facts count as elicited when the document is released.">
          <IdPicker values={a.linked_fact_ids} options={refs.facts} onChange={(v) => set((x) => void (x.linked_fact_ids = v))} placeholder="Link a fact…" />
        </F>
        <div className="flex items-end justify-end">
          <RemoveBtn label="Delete" onClick={() => up((d) => void d.chart.artifacts!.splice(i, 1))} />
        </div>
      </div>
    </div>
  );
}

export function ChartTab({ c, up }: TabProps) {
  const refs = useRefs(c);
  const arts = c.chart.artifacts ?? [];
  const addArtifact = (kind: string) =>
    up((d) => {
      const list = (d.chart.artifacts ??= []);
      let n = list.length + 1;
      while (list.some((a) => a.artifact_id === `art.${kind}_${n}`)) n++;
      const section = (want: string[]) => d.chart.sections.find((s) => want.includes(s.section_id))?.section_id;
      const base = { artifact_id: `art.${kind}_${n}`, kind, synthetic: true, linked_fact_ids: [] as string[] };
      if (kind === "lab_report") list.push({ ...base, title: "Blood results", section_id: section(["labs", "lab"]), release: { rule: "on_request", request: "order:cbc" }, content: [{ test: "Hemoglobin", value: "", unit: "g/dL", ref_range: "12-16", flag: "" }] });
      else if (kind === "prior_note") list.push({ ...base, title: "Previous visit note", section_id: section(["records", "prior"]), release: { rule: "on_request", request: "order:prior_records" }, content: "" });
      else if (kind === "ecg") list.push({ ...base, title: "12-lead ECG (text description)", section_id: section(["imaging"]), release: { rule: "on_request", request: "order:ecg" }, content: "" });
      else list.push({ ...base, kind: "xray", title: "Imaging report", section_id: section(["imaging"]), release: { rule: "on_request", request: "order:chest_xray" }, content: "" });
    });
  return (
    <div className="space-y-4">
      <RequestList id="hg-requests-chart" requests={refs.requests} />
      <Panel
        title={`Chart sections (${c.chart.sections.length})`}
        note="The learner's chart. Triage note and vital signs are visible from the start; the others open when a fact lands in them or a request is made."
        testid="sections-panel"
        right={
          <button
            className="btn-quiet"
            onClick={() =>
              up((d) => {
                d.chart.sections.push({ section_id: `section_${d.chart.sections.length + 1}`, title: "New section", release: "on_fact" });
              })
            }
          >
            Add section
          </button>
        }
      >
        <Issues path="/chart/sections" skip={c.chart.sections.map((_, i) => String(i))} />
        <div className="space-y-2">
          {c.chart.sections.map((s, i) => (
            <div key={i} className="rounded-xl border border-line bg-white/60 p-2" data-testid="section-row">
              <div className="grid grid-cols-2 items-center gap-2 md:grid-cols-[140px_1fr_210px_auto]">
                <Text value={s.section_id} onChange={(v) => up((d) => void (d.chart.sections[i].section_id = slug(v) || v))} path={`/chart/sections/${i}/section_id`} placeholder="id" />
                <Text value={s.title} onChange={(v) => up((d) => void (d.chart.sections[i].title = v))} path={`/chart/sections/${i}/title`} placeholder="Title" />
                <Select
                  value={s.release}
                  onChange={(v) => up((d) => void (d.chart.sections[i].release = v as "initial" | "on_fact" | "on_request"))}
                  options={[
                    { value: "initial", label: "Initial: visible at start" },
                    { value: "on_fact", label: "On fact: opens with its first fact" },
                    { value: "on_request", label: "On request: opens with a result" },
                  ]}
                />
                <RemoveBtn onClick={() => up((d) => void d.chart.sections.splice(i, 1))} />
              </div>
              {s.release === "initial" && (
                <div className="mt-2">
                  <Area value={s.static_text ?? ""} onChange={(v) => up((d) => void (d.chart.sections[i].static_text = v || undefined))} placeholder="Optional text shown in this section from the start (e.g. the triage note)" />
                </div>
              )}
              <Issues path={`/chart/sections/${i}`} />
            </div>
          ))}
        </div>
      </Panel>

      <Panel
        title={`Chart documents (${arts.length})`}
        note="Lab reports, ECG and imaging reports, previous notes. Each is released at the start, on a request, or when a fact is disclosed. All content here is synthetic."
        testid="artifacts-panel"
        right={
          <div className="flex flex-wrap gap-1.5">
            <button className="btn-primary" onClick={() => addArtifact("lab_report")} data-testid="add-lab">
              Add lab report
            </button>
            <button className="btn-quiet" onClick={() => addArtifact("prior_note")} data-testid="add-note">
              Add previous note
            </button>
            <button className="btn-quiet" onClick={() => addArtifact("ecg")} data-testid="add-ecg">
              Add ECG report
            </button>
            <button className="btn-quiet" onClick={() => addArtifact("imaging")} data-testid="add-imaging">
              Add imaging report
            </button>
          </div>
        }
      >
        <Issues path="/chart/artifacts" skip={arts.map((_, i) => String(i))} />
        <div className="space-y-3">
          {arts.map((a, i) => (
            <ArtifactEditor key={i} a={a} i={i} c={c} up={up} />
          ))}
          {arts.length === 0 && <p className="text-[12.5px] text-ink-3">No documents yet.</p>}
        </div>
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------- objectives
export function ObjectivesTab({ c, up, rubrics }: TabProps & { rubrics: RubricSummary[] }) {
  const refs = useRefs(c);
  const domains = [...new Set([...c.objectives.map((o) => o.rubric_domain).filter(Boolean), ...((rubrics.find((r) => r.rubric_id === c.rubric_id) ?? rubrics.find((r) => r.is_default))?.domains?.map((d) => d.key) ?? [])] as string[])];
  const set = (i: number, fn: (o: Objective) => void) => up((d) => fn(d.objectives[i]));
  return (
    <Panel
      title={`Learning objectives (${c.objectives.length})`}
      note="Each objective is judged on its own after the encounter: met, partly demonstrated, not observed or not assessable, with the transcript evidence quoted. Link an objective to the facts or requests that show it."
      testid="objectives-panel"
      right={
        <button
          className="btn-primary"
          data-testid="add-objective"
          onClick={() =>
            up((d) => {
              let n = d.objectives.length + 1;
              while (d.objectives.some((o) => o.objective_id === `obj.new_${n}`)) n++;
              d.objectives.push({ objective_id: `obj.new_${n}`, criterion: "", kind: "elicit_fact", linked_fact_ids: [] });
            })
          }
        >
          Add objective
        </button>
      }
    >
      <datalist id="hg-domains">
        {domains.map((d) => (
          <option key={d} value={d} />
        ))}
      </datalist>
      <RequestList id="hg-requests-obj" requests={refs.requests} />
      <Issues path="/objectives" skip={c.objectives.map((_, i) => String(i))} />
      <div className="space-y-3">
        {c.objectives.map((o, i) => {
          const p = `/objectives/${i}`;
          return (
            <div key={i} className="rounded-xl border border-line bg-white/65 p-3" data-testid="objective-editor" data-objective-id={o.objective_id}>
              <Issues path={p} skip={["criterion", "linked_fact_ids", "linked_requests", "kind"]} />
              <div className="grid gap-3 md:grid-cols-6">
                <F label="Criterion (what the learner should do)" path={`${p}/criterion`} className="md:col-span-4">
                  <Area value={o.criterion} onChange={(v) => set(i, (x) => void (x.criterion = v))} path={`${p}/criterion`} testid="objective-criterion" />
                </F>
                <F label="Kind" path={`${p}/kind`} className="md:col-span-2">
                  <Select value={o.kind} onChange={(v) => set(i, (x) => void (x.kind = v))} options={opts(OBJ_KINDS)} testid="objective-kind" />
                </F>
                <F label="Linked facts" path={`${p}/linked_fact_ids`} className="md:col-span-3" hint="Met when all are elicited; partly when some are.">
                  <IdPicker values={o.linked_fact_ids} options={refs.facts} onChange={(v) => set(i, (x) => void (x.linked_fact_ids = v))} placeholder="Link a fact…" testid="objective-facts" />
                </F>
                <F label="Linked requests" path={`${p}/linked_requests`} className="md:col-span-3" hint="Examinations or tests that show this objective, e.g. order:ecg.">
                  <IdPicker values={o.linked_requests} options={refs.requests.map((r) => ({ id: r, label: requestLabel(r) }))} onChange={(v) => set(i, (x) => void (x.linked_requests = v.length ? v : undefined))} placeholder="Link a request…" allowFree />
                </F>
                <F label="Evidence rule (plain words)" className="md:col-span-4">
                  <Text value={o.evidence_rule} onChange={(v) => set(i, (x) => void (x.evidence_rule = v || undefined))} placeholder="What counts as met or partly demonstrated" />
                </F>
                <F label="Rubric domain" className="md:col-span-2">
                  <Text value={o.rubric_domain} onChange={(v) => set(i, (x) => void (x.rubric_domain = v || undefined))} list="hg-domains" />
                </F>
                <F label="Feedback when met" className="md:col-span-3">
                  <Area value={o.feedback_met} onChange={(v) => set(i, (x) => void (x.feedback_met = v || undefined))} />
                </F>
                <F label="Feedback when missed (shown as the next-time suggestion)" className="md:col-span-3">
                  <Area value={o.feedback_missed} onChange={(v) => set(i, (x) => void (x.feedback_missed = v || undefined))} testid="objective-missed" />
                </F>
                <div className="flex items-center justify-between md:col-span-6">
                  <Check value={o.critical} onChange={(v) => set(i, (x) => void (x.critical = v || undefined))} label="Key objective" />
                  <span className="flex items-center gap-3">
                    <span className="text-[11px] text-ink-3">{o.objective_id}</span>
                    <RemoveBtn label="Delete objective" onClick={() => up((d) => void d.objectives.splice(i, 1))} />
                  </span>
                </div>
              </div>
            </div>
          );
        })}
        {c.objectives.length === 0 && <p className="text-[12.5px] text-ink-3">No objectives yet. Without them, feedback covers the rubric domains only.</p>}
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------- sources
export function SourcesTab({ c, up }: TabProps) {
  const refs = useRefs(c);
  return (
    <Panel
      title={`Knowledge sources (${c.sources.length})`}
      note="What the clinical content rests on. List only sources you have read. Content without a source is the author's own and is labelled as needing faculty review."
      testid="sources-panel"
      right={
        <button
          className="btn-primary"
          data-testid="add-source"
          onClick={() =>
            up((d) => {
              d.sources.push({ source_id: `src_${d.sources.length + 1}`, title: "", url: "", role: "evidence_for_fact" });
            })
          }
        >
          Add source
        </button>
      }
    >
      <Issues path="/sources" skip={c.sources.map((_, i) => String(i))} />
      <div className="space-y-3">
        {c.sources.map((s, i) => {
          const p = `/sources/${i}`;
          return (
            <div key={i} className="rounded-xl border border-line bg-white/65 p-3" data-testid="source-editor">
              <Issues path={p} skip={["title", "url", "role"]} />
              <div className="grid gap-3 md:grid-cols-6">
                <F label="Title" path={`${p}/title`} className="md:col-span-3">
                  <Text value={s.title} onChange={(v) => up((d) => void (d.sources[i].title = v))} path={`${p}/title`} testid="source-title" />
                </F>
                <F label="URL" path={`${p}/url`} className="md:col-span-3">
                  <Text value={s.url} onChange={(v) => up((d) => void (d.sources[i].url = v || undefined))} path={`${p}/url`} placeholder="https://…" testid="source-url" />
                </F>
                <F label="Role" path={`${p}/role`} className="md:col-span-2">
                  <Select value={s.role} onChange={(v) => up((d) => void (d.sources[i].role = v))} options={opts(SOURCE_ROLES)} testid="source-role" />
                </F>
                <F label="Date" className="md:col-span-2">
                  <Text value={s.date} onChange={(v) => up((d) => void (d.sources[i].date = v || undefined))} placeholder="e.g. fetched 2026-10-10" />
                </F>
                <F label="Licence" className="md:col-span-2">
                  <Text value={s.license} onChange={(v) => up((d) => void (d.sources[i].license = v || undefined))} />
                </F>
                <F label="Supports" className="md:col-span-5">
                  <IdPicker values={s.supports} options={[...refs.facts, ...refs.artifacts]} onChange={(v) => up((d) => void (d.sources[i].supports = v))} placeholder="Link a fact or document…" />
                </F>
                <div className="flex items-end justify-end">
                  <RemoveBtn onClick={() => up((d) => void d.sources.splice(i, 1))} />
                </div>
              </div>
            </div>
          );
        })}
        {c.sources.length === 0 && <p className="text-[12.5px] text-ink-3">No sources listed. Everything in this case is then the author&apos;s own wording and needs faculty review.</p>}
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------- raw JSON
const SERVER_KEYS = ["case_id", "version", "status", "updated", "versions", "seed", "validation", "notes", "created_from", "new_version_created"];
export function JsonTab({ c, onReplace }: { c: CaseDoc; onReplace: (d: CaseDoc) => void }) {
  const initial = useMemo(() => JSON.stringify(c, null, 2), [c]);
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const apply = () => {
    try {
      const parsed = JSON.parse(text ?? initial) as CaseDoc;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("The document must be a JSON object.");
      const next = { ...parsed, case_id: c.case_id, version: c.version, status: c.status } as CaseDoc;
      next.facts ??= [];
      next.objectives ??= [];
      next.sources ??= [];
      next.chart ??= { sections: [], artifacts: [] };
      next.chart.sections ??= [];
      next.profile ??= { name: "", age: 0, gender: "" };
      onReplace(next);
      setText(null);
      setErr(null);
    } catch (e) {
      setErr(String((e as Error).message));
    }
  };
  return (
    <Panel
      title="Raw JSON"
      note={`The whole case as it is stored (contracts/case.schema.json). An escape hatch: everything here is also editable in the other tabs. ${SERVER_KEYS.slice(0, 3).join(", ")} are set by the server and cannot be changed here.`}
      testid="json-panel"
      right={
        <div className="flex gap-1.5">
          <button className="btn-quiet" onClick={() => setText(null)} disabled={text === null}>
            Discard JSON edits
          </button>
          <button className="btn-primary" onClick={apply} disabled={text === null} data-testid="json-apply">
            Apply to the draft
          </button>
        </div>
      }
    >
      {err && (
        <div className="mb-2">
          <InlineError>Not applied: {err}</InlineError>
        </div>
      )}
      <textarea className={`${inputCls} tnum h-[60vh] resize-y font-mono text-[11.5px] leading-relaxed`} spellCheck={false} value={text ?? initial} onChange={(e) => setText(e.target.value)} data-testid="json-text" />
    </Panel>
  );
}
