# TwinVerse requirements and architecture evidence

Reviewed October 9, 2026, America/New_York. The supplied package supports **Challenge 1, ER Encounter Studio**: a faculty member creates and approves a synthetic patient, a student conducts an encounter beside a progressively revealed chart, and feedback uses faculty objectives and interaction evidence. **A four-minute pitch and code repository are mandatory. During judging, faculty creates a new patient and immediately runs it without patient-specific code changes.** See the [action plan](action-plan.md) for execution and the [source register](source-register.md) for provenance. Source instructions below are challenge requirements or explanatory material; implementation choices remain explicitly labeled proposals.

## Package and evidence

The supplied `TwinVerse.zip` contains two challenge DOCX files and two archived explanatory MP4s. Both documents were reviewed structurally, including tables and hyperlinks, and all rendered pages were inspected: Challenge 1 has five rendered pages, Challenge 2 sixteen. No actual patient dataset, clinical image, JSON schema, faculty learning-objective file, prompt bundle, or starter implementation is included. The repository publishes research summaries; it does not redistribute the supplied source attachments.

| Source | Duration or rendered pages | Use |
|---|---|---|
| `TwinVerse_RUHealthHack_Challenge1.docx` | 5 pages | Mandatory Challenge 1 scope and deliverables |
| `TwinVerse_RUHealthHack_Challenge2.docx` | 16 pages | Alternative challenge scope and explicit state categories |
| `Video_Challenge_1_Virtual_Patient_Architecture.mp4` | 7:22.897 | Architecture illustrations; includes cross-challenge material |
| `Video_Challenge_2__Connected_Care.mp4` | 8:19.554 | Connected-care illustration |

Both videos were transcribed locally and inspected through sampled frames, including exact-time architecture slides. The automatic transcript has recognition errors in Rutgers, SBAR and TeamSTEPPS; this summary uses spellings verified against the documents and slides. Video narration is supplementary, and uncertain wording does not override written requirements. Timestamps below refer to the supplied MP4s.

## Exact Challenge 1 requirements

The written Challenge 1 document has three core components. These are requirements for the submitted prototype, not options created by this report.

**Patient Studio, faculty-facing (rendered page 1).** Faculty can create a profile through structured or descriptive inputs; add knowledge sources such as papers, guidelines or institutional protocols; attach labs, ECGs, X-rays, CT scans or prior notes; define when facts/artifacts become available; review and correct generated information; check internal clinical consistency; approve and publish; and maintain multiple reusable profiles.

A generic attachment system satisfies the architecture need to manage those artifact types, but the document does not specify a minimum count of every modality. Clarify the expected live demonstration with the mentor. Do not remove artifact management from Base; sophisticated artifact generation is Stretch.

**Encounter interface, student-facing (page 2).** The required split screen places patient interaction on the left and dynamically revealed medical information/chart on the right. Every published profile must run on the same architecture without patient-specific code. Text is required; voice/avatar encouraged. Preserve identity and conversational state; display prior notes, structured information and artifacts; release content progressively according to the profile and questions; prevent unsupported facts; record what was disclosed.

**Encounter feedback (page 2).** Feedback must follow faculty-defined objectives, identify important elicited/missed findings, assess interview structure/sequencing/quality, address communication/empathy/clarity/professionalism, link specific explanations to the encounter, describe strengths and improvements, suggest next-attempt actions, and log every encounter. A score with no evidence cannot satisfy the explainability requirement. Include strengths and actionable next practice advice in the planned debrief, not only a missed-fact checklist.

**Clinical validity (pages 2–3).** History, medications, diagnoses, labs and artifacts must agree. Unsupported information must not be presented as fact. Dynamic clinical findings must use approved or validated content. Attached records must remain consistent with the profile. These source requirements support the plan's canonical case contract, approval, versioning, controlled disclosure and event ledger.

**Complete Base experience (page 3).** Profile creation; knowledge/artifact management; review/publication; reusable profiles; complete student encounter; split screen and dynamic record; progressive disclosure; memory/state; clinical grounding/consistency; encounter logging; assessment and explainable feedback.

**Stretch (page 3).** Real-time voice, avatar (described as ideal), multimodal interaction, adaptive behavior, advanced memory/state, more sophisticated artifacts, external SaaS integration APIs such as Canvas. Neither voice nor Canvas is a Base requirement. No specific technology is compulsory.

## Required submission and judging

Challenge 1 required deliverables (page 4):

1. Working prototype showing profile creation, a complete encounter, and generated feedback.
2. Code repository containing implementation and infrastructure code if applicable.
3. Short demonstration video **or** live demonstration.
4. **Four-minute pitch** explaining solution, architecture, technical approach, and educational value.

The [action plan](action-plan.md) uses the required four-minute pitch, replacing the original provisional three-minute rehearsal. Keep a short fallback video even if using the live-demo option. A README should tell judges how to run the implementation and how approved cases reach the encounter engine. If AWS infrastructure is implemented, include its code/configuration without secrets or workshop access tokens.

Evaluation areas (pages 4–5) are architecture/reusability, profile quality and clinical validity, technical innovation, user experience, encounter quality, feedback effectiveness/explainability. The document gives no numerical weights, so do not invent rubric percentages.

**Key judging demonstration (page 5):** a faculty member creates a new patient in Patient Studio and then conducts an encounter with that newly created patient. It must run immediately in the reusable architecture with zero patient-specific code changes. Testing only the two prepared cases does not establish this requirement. Retain the held-out new-case gate and budget explicit pitch time for it.

## Resources promised versus actually available

Challenge 1 page 4 promises synthetic personas, existing VHS prompts, sample encounters/cases, learning objectives, documentation templates, and AWS Bedrock access/credits. The ZIP itself provides only challenge documents and videos. It does not supply those case/persona/prompt/objective/template assets or a predefined schema. The later October 10 resource bundle supplies synthetic profiles, faculty seeds, a rubric and clinician personas; see the [dataset review](discord-dataset-review-2026-10-10.md). Review those drafts and request remaining prompts/templates plus a mentor review slot. The absence statement applies to the initial ZIP only; do not call a generated local fixture an organizer-provided persona.

Challenge 2 explicitly labels provided resources TBD (page 14). Its faculty-provided structured case/scenarios are part of its expected workflow, but no actual case is bundled here.

## Why Challenge 2 is a different weekend scope

Challenge 2 is a connected multi-professional care journey. A student takes one professional role while AI plays the patient and other professional roles. The same patient must traverse **at least three encounters**, with shared state updated after each. Prior information must actually influence a later encounter. The final result is an integrated patient representation plus a coherent plan synthesized across professions, not three concatenated note summaries. These are Base obligations (pages 7–8).

The example professions are surgeon, cardiologist and dietitian; they are examples rather than proof that those exact roles are mandatory for every case. Base must use the supplied professional scenarios/personas.

| Challenge 2 level | Required behavior |
|---|---|
| Base | Three or more encounters, student role + AI others, shared state, integration of records/new findings, later-encounter influence, uncertainty/disagreement/unanswered-question distinctions, provenance, integrated patient/plan |
| Enhanced | Adds relevant TeamSTEPPS-aligned professional communication and explainable evaluation; SBAR is a specified approach, without requiring the entire TeamSTEPPS framework |
| Stretch | Includes Base + Enhanced and adds communication outside the fixed sequence: consultations, huddles, check-backs/call-outs, closed loops, conflict reconciliation and collaborative plan changes |

Enhanced evaluation asks whether professionals communicated situation/background/findings, distinguished facts from interpretations, expressed uncertainty and requested next action; whether recipients reviewed prior information, recognized changes/contradictions/missing concerns; whether they clarified/responded/acknowledged/escalated; and whether responsibilities, next steps, patient goals and recommendations were coordinated (pages 9–11). The behavioral trace identifies the behavior, observed yes/no, evidence location and actionable feedback.

Challenge 2 required deliverables (pages 14–15): Base-compliant prototype; architecture/integration document covering state, transfers, persistence, provenance, sharing, communication evaluation and extensibility; final integrated patient representation with contribution provenance; integrated care plan; runnable/understandable repository; four-minute pitch explaining journey, architecture, level achieved, continuity and transfers, applicable SBAR/collaboration, and limitations. The document describes its evaluation considerations as a current working draft (page 16).

## Source-defined state categories and proposed Challenge 1 contract

No exact JSON schema is supplied. Challenge 2 lists content categories for shared state (pages 5–6):

| Category | Explicit source content |
|---|---|
| Medical | History, symptoms, findings, diagnoses, medications, tests/results, referrals |
| Patient-centered | Goals, preferences, strengths, concerns, functional limitations, capabilities, social/environmental context |
| Care | Assessments, interpretations, recommendations, progress, outstanding actions, care-plan items |
| Uncertainty | Unanswered questions, uncertain information, conflicts, different professional interpretations |
| Provenance | Source, contributing professional role, encounter, timing; example additionally labels a finding patient-reported |

For our **recommended** Challenge 1 contract, use `case_id`, immutable `case_version`, identity/setting, patient-known fact IDs with approved first-person answers, chart fact IDs, unavailable/unknown states, artifact records, disclosure rules, source references, faculty objectives, review findings, approver/status, and encounter events. This is our implementation proposal, not an organizer-supplied schema.

Each artifact proposal should store `artifact_id`, type, source/permission reference, case version, linked finding IDs, and release rule. Each objective proposal should store `objective_id`, faculty description, expected question/action/fact IDs, evidence rules, feedback templates, and uncertainty when the behavior cannot be assessed. Every encounter event proposal should store question/action, actor, time, disclosed facts/artifacts and approved case version. Use the same identifiers to generate the patient answer, chart update and feedback evidence.

## Required planning decisions

| Plan area | Verified requirement or decision |
|---|---|
| Pitch | Four minutes required; allocate live-case demonstration plus architecture, technical method and educational value |
| Submission | Repository mandatory; implementation + infrastructure if used; prototype, demo/video, pitch |
| Faculty Studio | Explicit knowledge-source management, artifact release timing, correction and consistency review; multiple profile library |
| Clinical artifacts | Include CT/prior notes in supported artifact types; automatic diagnosis/generation remains optional |
| Debrief | Include strengths, sequencing/interview quality, professionalism/clarity/empathy, concrete next-attempt suggestion, objective evidence |
| Logging | Retain every encounter and disclosure record; show logs can be reviewed |
| Starter assets | Mentor must supply/review persona, objectives, prompts/templates; none actually included in ZIP |
| Scope | Written Challenge 1 Base controls; do not add Challenge 2's three encounters/SBAR merely because an architecture video references them |

## Video interpretation and verification

The first video is titled Virtual Patient Architecture and its frames plus local machine transcript illustrate a broader platform: faculty content pipeline, dual patient/chart interface, shared patient state, provenance, level progression, and faculty-controlled clinical templates. A sampled slide describes Enhanced as real-time voice plus SBAR and Stretch as interprofessional collaboration, although the Challenge 1 DOCX lists voice under Stretch and contains no Enhanced tier. That discrepancy is material. The written Challenge 1 document remains the plan's requirement authority; treat the video as broader explanatory architecture until the mentor resolves any change.

The second video illustrates connected care, student role replacement, shared state, provenance, uncertainty/interpretation distinctions, SBAR, explainable communication assessment, advanced team collaboration and a unified final plan. The clinical journey shown is illustrative, not an approved patient case or calibrated hospital workflow.

The evidence below describes source-video illustrations. It does not independently verify their clinical claims or educational efficacy.

| Video 1 time | Supported point | Planning consequence |
|---|---|---|
| 01:57–02:23 | Split patient dialogue and dynamic EHR; progressive labs/ECG/CT reveal | Same fact/artifact IDs feed both panels |
| 02:23–02:49 | A patient self-report can intentionally differ from a chart finding to test reasoning | Only include a discrepancy if faculty explicitly authors both observations and the learning objective; no AI improvisation |
| 02:57–03:19 | Log interactions; evaluate elicited/missed findings, empathy, professionalism, sequence; map advice to objectives | Debrief needs more than fact count |
| 03:26–03:55 | JSON/YAML authored profile, release rules, publication, reusable engine | Keep content as data; JSON/YAML suggestions do not prescribe an exact schema |
| 03:55–05:06 | Moves into multi-encounter shared state and four provenance fields | Broader platform/Challenge 2 explanation; no expanded Challenge 1 Base obligation |
| 05:12–05:43 | Mentions Base/Enhanced/Stretch with voice + SBAR Enhanced | Inconsistent tier mapping with written Challenge 1; written document governs our plan pending mentor clarification |
| 05:43–06:30 | No invented vitals/labs/findings; LLM handles dialogue/formatting; faculty profile controls facts | Backend validates every clinical fact and approved source |

The glucose/nonadherence example in the first video must not be treated as a validated diagnostic inference. A discrepancy between self-report and a lab can prompt inquiry; it does not by itself establish why the lab is abnormal. If used, the faculty-approved case must define what is known, what is patient-reported and what remains uncertain.

| Video 2 time | Supported point | Planning consequence |
|---|---|---|
| 00:33–02:30 | Illustrative Denise care story, fragmentation, goals, conflict recognition and coordinated plan | Motivation for Challenge 2, not an actual persona/case asset |
| 03:05–03:30 | Student takes professional role; AI plays other roles | Alternative scope, not needed for our selected Challenge 1 |
| 03:36–04:45 | Three encounters, shared state/provenance, uncertainty, earlier findings influence later actions | Matches Challenge 2 written Base |
| 04:51–05:15 | Clinical facts bounded by faculty-approved content | Same grounded-content boundary applies in both challenges |
| 05:19–06:35 | TeamSTEPPS/SBAR handoffs and explainable behavioral evidence | Challenge 2 Enhanced; raw STT sometimes writes SBR, normalized here from source document |
| 06:39–07:12 | Active collaboration outside fixed linear encounters | Challenge 2 Stretch |
| 07:19–07:54 | Final contributions, information influence, uncertainty and synthesized coordinated plan | Challenge 2 final deliverables, not concatenated notes |

The inspected source slides at 02:10, 03:30 and 06:22 in `Video_Challenge_1_Virtual_Patient_Architecture.mp4` show the split screen, author-profile → define-rules → reusable-engine pipeline, and faculty-controlled clinical-fact boundary. Slides at 04:07 and 06:20 in `Video_Challenge_2__Connected_Care.mp4` show provenance and evidence-linked communication feedback. They are explanatory diagrams, not an implemented product or an approved clinical case. Raw videos, extracted frames and full machine transcripts are not redistributed here.

## Practical acceptance matrix

These are proposed prototype checks, not a numeric official judging rubric. Test two reviewed original synthetic cases plus a held-out case created through Studio. A successful prepared fixture alone does not establish reusability.

| Concern | Observable check |
|---|---|
| New patient | Faculty creates and approves previously unseen content, starts it immediately, and finishes the encounter/debrief with zero code edits |
| Approval | Draft or malformed case cannot launch; existing encounter retains its approved version after a later edit |
| Grounding | At least 30 dialogue probes; manually count unsupported clinical claims and report failures, with a target of zero in this finite test set |
| Consistency | Repeat/paraphrase at least 10 questions; values, units, allergy/history facts and timing agree across dialogue and chart |
| Disclosure | Hidden diagnosis/answer key remains concealed; release follows authored rules; unknown, missing and known-negative states differ |
| Artifacts | Correct artifact, findings, release rule and permission metadata belong to the same case/version; absent asset is explicit |
| Feedback | At least 10 objective decisions compared with faculty expectations; observed/missed/not-assessable labels carry evidence and actionable advice |
| Reliability | Isolated encounters, safe duplicate/retry behavior, refresh/reset, provider timeout fallback, second-device access |
| Usability | Observe at least three short sessions if available; record completion, confusion and authoring/startup time |

Communication feedback remains formative coaching. Finite prototype tests cannot establish validated empathy measurement, educational benefit or hallucination-free performance. Report observed counts and disagreements and state the next supervised faculty pilot.
