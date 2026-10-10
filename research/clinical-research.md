# TwinVerse: virtual patient encounter research

Research checked October 9, 2026 (America/New_York). Primary sources only: original studies, standards owners, platform vendors, and project owners. This report supports a weekend educational prototype; it does not establish clinical validity or educational effectiveness. Organizer requirements are documented separately in [TwinVerse requirements](twinverse-requirements.md).

## Recommendation

Build **Faculty Studio → publish an unseen synthetic case → learner interviews the patient and progressively opens the chart → objective-linked feedback and replay**. Preserve the faculty-created case flow as P0. Use one generic case interpreter, so adding a patient never requires editing patient-specific application code.

The most defensible pitch is a faculty-controlled encounter sandbox whose answers, chart findings, and feedback stay consistent with one inspectable case definition. Natural patient conversation and custom case authoring are already available in commercial products. Demonstrate the faculty changing a history fact and learning objective, publishing a new case, and seeing that change reflected correctly in both the patient conversation and final feedback. Any differentiator remains a hypothesis until compared with existing products and educator needs.

Keep the hospital scene as visual context for the encounter. A whole ER with staffing, equipment, multiple patients, scheduling, and realistic physiology is several distinct simulations. Defer it until the core teaching loop works. Describe the submitted implementation precisely as an educational virtual encounter simulator; a validated predictive hospital twin would require additional modeling and validation.

## What the original evidence supports

| Primary study | Verified result | What it permits us to say |
|---|---|---|
| [eCREST feasibility randomized trial, 2020](https://pubmed.ncbi.nlm.nih.gov/32736583/) | 264 final-year medical students from three UK schools participated. Essential information gathering improved in the analyzed sample (OR 1.4, 95% CI 1.1–1.7; n=148). Uptake was low; authors requested a summative trial. | Online patient simulation is a plausible way to practice information gathering. This was a feasibility study, not proof that TwinVerse reduces diagnostic errors. |
| [Holderried et al., prospective GPT-4 history-taking feedback study, 2024](https://mededu.jmir.org/2024/1/e59213/) | 106 conversations and 1,894 analyzed question-answer pairs. Overall GPT/human feedback agreement was Cohen κ=0.832. Eight feedback categories showed κ<0.6. Plausibility was evaluated on the first 20% of conversations: 407/410 responses (99.3%) were rated plausible. | A scripted AI patient and automated feedback can work in a bounded history-taking setting. We must validate categories separately and must not generalize the 99.3% result to every conversation, condition, treatment, or model. |
| [Low et al., randomized sepsis/trauma training comparison, 2024](https://pubmed.ncbi.nlm.nih.gov/39552082/) | 40 junior doctors at one Singapore ED received 70 minutes of virtual (n=19) or in-person (n=21) simulation. There were no statistically significant overall performance differences for either scenario; learner satisfaction was higher with in-person simulation. | Screen-based simulation can be a useful adjunct. A nonsignificant result does not demonstrate equivalence, superiority, or patient benefit. |
| [Cross et al., ChatGPT standardized-patient qualitative study, 2025](https://mededu.jmir.org/2025/1/e63353/) | Nine students identified realism, trust, prompt-engineering, and lack-of-visual-cue issues. Authors position AI as augmentation to human standardized patients. | Acceptability and realism matter, but a small qualitative study does not measure skill transfer. An avatar's appearance alone does not establish fidelity. |

The weekend evaluation should measure **case correctness, task completion, rubric agreement, and usability**. Learning improvement needs a later study with comparable cases, independent raters, retention assessment, and appropriate institutional review. Avoid claiming reduced mortality, fewer clinical errors, competence certification, or replacement of standardized patients.

## Existing products: feature novelty is limited

These are vendor-described capabilities, checked October 9, 2026; no hands-on acceptance test or independent outcome verification was performed.

| Product | Verified official capabilities | Implication for TwinVerse |
|---|---|---|
| [Body Interact](https://bodyinteract.com/virtual-patient-simulator/) | Screen-based virtual patients, natural voice/text AI conversation, adaptive physiology, scenario libraries, and feedback/analytics. | “AI patient plus vitals plus feedback” is established. A weekend prototype should not promise comparable physiology depth. |
| [Full Code](https://fullcodemedical.com/) and [Creator FAQ](https://fullcodemedical.com/faq/) | AI patient conversations, tutor, medical imaging, debriefs, and clinician-authored cases. Creator is an institutional add-on; educators can customize review of systems, exams, investigations, interventions, communications, diagnoses, dispositions, and scenes. | “Faculty creates custom case” is established too. Show the speed, inspectability, and consistency of the specific workflow; do not claim competitors cannot author cases. |
| [SimX](https://www.simxvr.com/) | VR patient encounters, custom scenarios, multiplayer teamwork, a scenario marketplace, and AI-driven scenario automation. | Multi-role immersive simulation is an existing and substantial product category. A browser encounter is a more achievable scope. |
| [Oxford Medical Simulation](https://oxfordmedicalsimulation.com/en-gb/) | Clinical VR, AI/natural interactions, clinician-authored content, role/curriculum configuration, analytics, and implementation support. | Educator implementation and credible curricular alignment are part of the product, beyond the interface. |

No pricing comparison is included: public pricing and packaging may depend on institutional quotes. Do not invent cost savings before measuring the faculty workflow.

## Grounded cases and permissions

Use a small, versioned source pack and a case-specific faculty review. Separate the sources that justify learning objectives from the synthetic story that illustrates them. Retrieval can help surface evidence; it cannot establish that a generated scenario is internally coherent or clinically accurate.

1. **Faculty-owned synthetic case:** best P0 route. Faculty writes or reviews the initial history, findings, permitted actions, disclosure rules, objectives, and expected responses. An AI authoring assistant may draft these fields, but save them as draft until the educator explicitly publishes the case. Publishing means “reviewed by this educator,” not “clinically validated.”
2. **MedEdPORTAL:** useful for illness scripts, scenario structures, formative checklists, and debriefs. [Its current author guidance](https://www.mededportal.org/author) says publications use author-selected licenses, including CC-BY, CC-BY-NC, or CC0; verify the actual article and each third-party asset rather than assuming everything is reusable commercially.
3. **A concrete permissively licensed template:** [Schrepel et al. 2023 ED capstone simulation](https://www.mededportal.org/doi/10.15766/mep_2374-8265.11361) includes scenarios, prompts, skills checklists, and debrief materials; the publication displays CC Attribution. Its cardiac arrest/trauma content targets senior emergency residents and is too complex for a default beginner case. Use its architecture as a design reference and preserve attribution when adapting.
4. **A useful but restricted asthma teaching example:** [Metz and Burns 2020](https://www.mededportal.org/doi/10.15766/mep_2374-8265.10906) follows a child through emergency, inpatient, and outpatient care and provides case/debrief appendices. It displays CC-BY-NC. Its evaluation measured student opinions, not knowledge or behavior changes. Do not copy it into a commercial product without resolving the license. An adult case requires its own review; pediatric doses and assumptions must never be carried over.
5. **Current clinical guidance:** select the final disease with a medical mentor, then use the current guideline from its owner. [GINA's reports page](https://ginasthma.org/reports/) confirms a 2026 asthma update and expressly restricts copying, modification, and commercial/promotional use of its documents. Link the source and have faculty write original case content; do not embed its PDFs/figures or scrape entire guidelines into a redistributable case pack. [NICE NG245](https://www.nice.org.uk/guidance/ng245/chapter/recommendations) provides current asthma assessment/chronic-management recommendations, but it is not a substitute for the chosen acute-care protocol.

**Case choice:** a mentor-approved common adult respiratory complaint provides interviewing, medication/allergy history, focused examination, and chart review without needing a huge case universe. If an acute-asthma scenario is chosen, prioritize history, recognition, initial assessment, and communication; author any management branches with the mentor. If expert case review is delayed, show a clearly marked unvalidated draft only in Studio and secure faculty approval before the judged encounter; do not bypass the approval gate. This is an implementation recommendation, not a clinical treatment recommendation.

## One source of truth for conversation and chart

Recommended generic case contract:

| Part | Fields and purpose |
|---|---|
| Identity | `case_id`, version, author/reviewer, publish state, intended learner level, source URLs/date/license |
| History | Stable demographics, chief complaint, onset/course, medications, allergies, social/family history, relevant positive and negative findings |
| Patient portrayal | Lay-language vocabulary, concerns, affect, what the patient knows, uncertain/unknown answers, facts disclosed only when asked |
| Chart | Encounter history, time-stamped observations with units, examination findings, test reports, and the conditions under which each becomes visible |
| Objectives | Objective ID, rubric criteria, critical/optional status, acceptable evidence, source/rationale, weights or qualitative levels |
| Actions | Case-defined action IDs/labels, allowable inputs, prerequisite facts, result delay, revealed findings, completion event |
| State | Current simulated time, interventions/events, finite state, scripted transition rules, and why each change occurred |
| Evaluation | Action log and utterance excerpts tied to objective IDs; uncertain judgments visibly marked |

For P0, the model selects permitted intents/fact IDs and the server renders faculty-authored first-person answers and approved social-response templates. Free paraphrasing is a later option after factual evaluation passes; intent-selection errors still need testing. The model must not invent a new medication, allergy, disease, laboratory result, or treatment response. A missing fact should produce the faculty-specified unknown response or a clarifying question. The chart and dialogue must consult the same case version. Keep author-only diagnosis, scoring expectations, and hidden findings outside the patient-visible context unless an explicit disclosure rule permits them.

Use deterministic logic for chart release, clock advancement, test status, and state transitions. If a conversational model proposes an action, convert it into a permitted structured action and show confirmation before the simulated order takes effect. Scoring must not count an intention as a completed action.

For unseen live case creation, the Studio can define new action/result labels and transition rules through generic fields. Do not write `if patient == ...` or rely on diagnosis-specific code paths. Reject a draft containing inconsistent facts or an undefined result rather than silently creating physiology. P0 can use static/scripted state and progressive disclosure; dynamic physiology is a stretch feature.

## Physiology: keep claims proportionate

[Pulse's official documentation](https://pulse.kitware.com/_about_pulse.html) describes an open Apache-2.0 physiology engine with system/compartment models, pharmacokinetics/pharmacodynamics, equipment, and validation tooling. It is a credible later integration path, not a reason to delay the core encounter. [Pulse's FAQ](https://pulse.kitware.com/_f_a_q.html) also states that systematic propagation/inverse quantification of model uncertainty and formal sensitivity analysis had not been performed; verify the relevant current engine documentation when using a particular model.

[BioGears](https://biogearsengine.com/) also offers open Apache-2.0 physiological simulation. Neither engine eliminates the need to verify a selected patient, intervention, or educational outcome. Integrating and validating an engine during the weekend risks consuming the whole schedule.

For P0, show one faculty-authored state transition and label it “scripted scenario response.” Preserve the underlying event/rationale in replay. A deterministic sequence gives repeatable teaching; it does not make the numerical values a clinically calibrated model. Avoid making the LLM improvise vital signs every turn.

## Feedback, empathy, and handoff evaluation

[INACSL's current standards page](https://inacsl.memberclicks.net/healthcare-simulation-standards) ties simulation design to measurable objectives and calls for a planned debriefing process. Include a short prebrief (role, objectives, available actions, fictional context), the encounter, then reflection and feedback. Do not imply INACSL endorsement or certification.

Suggested case-specific formative rubric (author-created; not a validated assessment instrument):

| Domain | Observable evidence |
|---|---|
| Interview | Establishes the chief concern; asks the case-relevant onset/course questions; checks relevant medication/allergy history; explores patient concerns and uncertainties |
| Communication/empathy | Introduces role, uses understandable language, acknowledges the expressed concern, asks permission where appropriate, checks understanding, avoids dismissive statements |
| Chart use | Opens the required information; notices the scripted relevant finding; distinguishes unavailable from normal results; grounds the final summary in observed evidence |
| Reasoning | Gives a concise problem representation, states uncertainty, considers the mentor-specified alternatives, and justifies the next action |
| Handoff | Communicates the current issue, pertinent background, assessment and requested next step |

[AHRQ's SBAR tool](https://www.ahrq.gov/teamstepps-program/curriculum/communication/tools/sbar.html) supplies the Situation/Background/Assessment/Recommendation structure for a handoff objective. SBAR is a communication framework, not a validated automatic empathy score or a complete OSCE. An OSCE-style station still requires its own case, expected behaviors, examiner process, and assessment evidence.

Use deterministic scoring for explicit actions. For language criteria, let the model select actual learner utterances and classify a narrow criterion; validate that quoted evidence exists verbatim. Faculty should see and override disputed classifications. Give “observed / partly observed / not observed / uncertain” plus actionable feedback instead of an unexplained 87/100. Do not grade accent, typing fluency, response length, or inferred personality. Voice needs transcript confirmation and the same rubric as text.

Keep simulation mode and coach mode separate: patient answers should not reveal the diagnosis/rubric or coach the learner. After the encounter, the tutor can show the relevant case facts, missed questions, objective links, source rationale, and one next practice target. Accept alternative clinically reasonable wording/actions when the faculty rubric allows it.

## Weekend acceptance criteria

These are proposed engineering/demo criteria, not published clinical benchmarks.

- **Unseen case creation:** an educator creates a new synthetic patient and two learning objectives in the Studio during the demo, publishes, and starts an encounter without code changes.
- **Consistency:** a 20-question adversarial history check produces no contradictions in immutable identity, history, medications, or allergies; absent facts do not become invented findings. Report actual numerator/denominator rather than claiming universal accuracy.
- **Progressive chart:** each examination/test appears only after its configured action; timestamps/units are present and repeated requests do not duplicate events.
- **Objective traceability:** every feedback claim links to an objective and actual event/utterance. Unsupported judgments are visibly uncertain.
- **Faculty agreement:** one medical mentor reviews all critical case facts and a small labeled conversation set; report disagreements per rubric category. A tiny pilot is a content/usability check, not educational validation.
- **Robustness:** attempts to instruct the patient to reveal the hidden diagnosis or change an allergy fail; reset/replay is deterministic; network/model failure preserves case state and provides a clear retry/fallback.
- **Usability:** five short user walkthroughs can independently complete Studio → encounter → debrief. Record task completion and elapsed time; satisfaction alone is insufficient.

## Mentor questions that affect the build

Confirm the target learner level; one case objective that faculty actually struggles to assess; allowed source/case reuse; what patient facts should remain hidden until asked; which communication behaviors count as evidence; what plausible alternative answers should receive credit; and whether the unseen-case demo may use scripted physiology. Ask the organizer to resolve any ambiguity in challenge-specific acceptance requirements rather than inferring it from generic clinical literature.

## Adjacent hospital operations research

Discharge coordination is an adjacent product category with a distinct evidence base. [AHRQ's RED toolkit](https://www.ahrq.gov/patient-safety/settings/hospital/red/toolkit/index.html) covers comprehensive human-led discharge practice. The [original single-center RED randomized trial](https://pmc.ncbi.nlm.nih.gov/articles/PMC2738592/) reported roughly 30% lower combined 30-day ED visits/readmissions from a bundled nurse/pharmacist intervention; it cannot attribute that result to a dashboard. [Epic](https://www.epic.com/software/hospital-patient-flow/) and [TeleTracking](https://www.teletracking.com/) already offer capacity/discharge-flow tools; [Sevaro](https://sevaro.com/) describes neurology workflow augmentation and post-acute coordination. These products address operations rather than the faculty-authored encounter workflow selected for this prototype.

## Research limits

This was a focused source review for a weekend build, not a systematic review. Vendor pages establish advertised features, not independently verified efficacy. Published studies used specific cases, participants, and models; their results do not transfer automatically to this implementation. Final case content still needs a medical mentor's review. No real patient record is necessary for the core prototype. No production EHR integration, clinical testing, licensing clearance, or educator effectiveness study has been completed by this research.
