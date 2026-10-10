# Rutgers Health Hack 2026 challenges and event

Reviewed October 9, 2026, America/New_York. **Plan to submit Sunday, October 11 at noon EDT, with materials complete at 11 a.m. and submission verified by 11:30 a.m.** The selected direction is TwinVerse Challenge 1, the Virtual Patient Encounter. This document preserves the broader challenge comparison and event constraints; the [action plan](action-plan.md) and [TwinVerse requirements](twinverse-requirements.md) contain the selected execution scope.

The subsequently supplied `TwinVerse_RUHealthHack_Challenge1.docx` resolves presentation and deliverable uncertainty: a four-minute pitch, working prototype, code repository including infrastructure if applicable, and short video or live demonstration. It requires the faculty Studio, reusable encounters and explainable feedback, with a faculty-created new patient during judging. Exact submission-portal fields and numerical judging weights remain unverified.

## Sources and confidence

- `New_RUHealthHack_TeamFormation_Challenges.pdf` is the primary cross-track challenge source. All 13 pages were extracted and visually inspected. Page numbers in the comparison refer to that supplied deck. Source attachments are not redistributed; see the [source register](source-register.md).
- [Official event brochure](https://www.ruhealthhack.com/brochure) is the best public schedule located: correct October 9-11, 2026 dates and a Sunday noon project submission time. Its schedule is labeled preliminary and subject to change. The rendered brochure was inspected on October 9: its 2026 banner and Sunday schedule showed noon submissions, 1 p.m. track judging and 5 p.m. awards. The schedule remains preliminary.
- [Official homepage](https://ruhealthhack.com/) identifies track partners and industry support. [Official conduct and rules](https://www.ruhealthhack.com/conduct) contains preliminary participation/IP rules; the full terms are to be signed onsite.
- [2026 Devpost homepage](https://rutgers-health-hack-2026.devpost.com/) confirms the event but lists a 5:00 PM EDT deadline and says criteria are revealed onsite. That conflicts with the correct-year official brochure. Treat noon as the build/submission deadline.
- [Legacy schedule page](https://www.ruhealthhack.com/schedule) still shows Friday October 10 / Saturday October 11 / Sunday October 12, which are the 2025 weekday/date pattern. Do not use it as the 2026 schedule.

## Deadline and logistics

**Working submission deadline: Sunday, October 11, 2026, 12:00 PM EDT.** This is the correct-year official brochure's submission time. Final action-plan targets: all materials ready at 11:00 AM; submission verified by 11:30 AM. The 5:00 PM Devpost display is not a reason to extend development.

The supplied deck says Friday 8:00-9:00 PM challenge reveal/team formation, followed by 9:00-10:00 PM team registration. The brochure says Saturday mentoring runs 8:00 AM-5:00 PM, Microsoft workshop 10:00 AM, Amazon workshop 11:00 AM, Sunday noon project presentations/submissions, track judging 1:00 PM, and awards 5:00 PM. The brochure remains preliminary. [Official brochure](https://www.ruhealthhack.com/brochure)

The brochure puts Friday keynote/networking at HELIX's fifth floor and Saturday hacking in MEB/Atrium/Innovation Center. Confirm room assignments with the onsite organizer. [Official brochure](https://www.ruhealthhack.com/brochure)

From Friday 8:00 PM until Sunday noon is **40 hours**, despite the event's general 48-hour branding. A late-Friday kickoff therefore needs a single narrow demonstrable workflow.

## Rules that affect planning

The preliminary official rules require teams larger than a solo or pair; therefore form a team of at least three. The page states projects must be developed during the hackathon and puts restrictions on third-party/IP/licensing material; full signed onsite terms govern. Verify whether existing libraries, boilerplate, or prior project components are allowed before incorporating them. This is a summary of the event rules, not a legal interpretation. Team maximum, exact AI-tool policy, and the signed terms were not located. [Official rules](https://www.ruhealthhack.com/conduct)

Devpost eligibility says participants must be at least 18 and attend all three days in person. The supplied TwinVerse package provides the Challenge 1 required submission and evaluation considerations; see [requirements](twinverse-requirements.md). A numeric rubric, portal-specific fields/public visibility, and whether new work after noon is permitted remain unverified. The current Devpost page advertises $10,000 distributed across winning teams. [Devpost rules](https://rutgers-health-hack-2026.devpost.com/rules), [Devpost event](https://rutgers-health-hack-2026.devpost.com/)

## All 11 official challenges

Requirements below come from the supplied deck. The "weekend assessment" column is analysis, not an organizer scoring rubric.

| Track and challenge | Required core | Demonstration specifically requested | Weekend assessment |
|---|---|---|---|
| Ops Unleashed 1: Discharge AI (p. 2) | Ingest dictation or EMR text; simplify to fifth-grade reading level; one-click native-language translation; secure large-font mobile link; hard-coded record deletion after 30 days | Dictate an instruction, show simplified/translated result on a phone, show expiry code | Strong visible demo; semantic preservation, medication numbers, translation review, and actual deletion behavior matter more than fluent writing |
| Ops Unleashed 2: AI Call Bell Router (p. 3) | Large-font multilingual text/voice bedside UI; structured department routing; immediate high-priority nurse escalation for urgent clinical requests; department dashboard | Pillow request appears in housekeeping queue instead of nurse pager | Feasible if the hospital routing taxonomy and urgency rules are validated; high clinical safety burden for ambiguous or mixed requests |
| Ops Unleashed 3: Scholarship Decision Platform (p. 4) | Persistent student accomplishment record; separate configurable award criteria; evidence-linked matching; explicit missing data; reviewer assignments/decisions/audit history | Show exact evidence for each criterion; resist invented facts | Feasible deterministic evidence workflow; less direct patient-care story; broad administration scope must be constrained |
| Ops Unleashed 4: AI Research Copilot (p. 5) | Question -> structured question/protocol/statistical plan; real NHANES variables vs derived ones; reproducible executable analysis with proper survey weights; range/weight/convergence/plausibility validation | Final-day test question -> Table 1, regression, figures | Higher-risk statistical project; needs a survey-statistics owner and a real end-to-end baseline before expanding coverage |
| Twinverse 1: The Virtual Patient Encounter (p. 6) | Faculty Patient Studio, structured approved profiles and attached tests; split-screen patient chat/progressive chart; objective-linked elicitation/interview/empathy feedback; no invented chart facts | Faculty creates a new patient live, with zero patient-specific code | Best general-purpose bounded demo if faculty can validate one schema/case; state/grounding are the engineering contribution |
| Twinverse 2: The Connected Care Journey (p. 7) | One patient across 3+ encounters; student as one professional role, AI as others; evolving shared findings/uncertainty/disagreements; who/when/encounter provenance | Integrated view shows each profession's contribution and how prior findings affected later encounters | More moving parts than single encounter; viable only with a narrow scripted care path and explicit state updates |
| Wellness Reimagined 1: Wellness, Made Personal (p. 8) | Five-minute conversational check-in; plain-language dimension feedback; 1-2 next steps per low dimension; actual geolocated campus/community resources, especially Newark/Camden | One recommendation tied to a real nearby resource | Lowest data-access risk; differentiate through accurate eligibility/location/hours and tangible follow-through rather than generic advice |
| Wellness Reimagined 2: Counselor Wellness Dashboard (p. 9) | De-identified cross-campus wellness aggregation; dimensions/campus/population trends; academic/public-health calendar overlay; resource-gap discovery; natural-language questions | Identify a dip, connect it to a calendar event, describe counselor decision | Attractive if usable data exist; synthetic data must be labeled and calendar correlation must not be presented as causal evidence |
| Wellness Reimagined 3: Predict My Glucose Response (p. 10) | Person-specific model from seven synthetic days: 5-minute CGM, heart rate, meal images/macros/medications; Day 8 glucose at 30/60/90/120 min, peak/time-to-peak/excursion; feature relevance and uncertainty | Predict a meal the person has never eaten | Highest modeling/evaluation risk: small personal sample, temporal leakage, unseen-meal extrapolation, synthetic-to-real limitations |
| Sevaro 1: The Workflow Companion (p. 11) | Primary proactive case-event/hospital/time-dependent guide nudges; hard-stop/advisory/info tiers; secondary cited Q&A with answered/not-in-guide/time-dependent/stale/conflict statuses; low nudge fatigue; new hospitals as data | Set LVO present = Yes, get correct hospital/hour transfer pathway; irrelevant cases stay quiet; add new guide live | Excellent bounded technical project if actual guide schema and sponsor interpretation are available; do not replace a policy engine with unconstrained chat |
| Sevaro 2: The Command Center (p. 12) | Detect present and 60-90-minute risks; decide intervention/approver; human-approved act/closed loop; reconcile inconsistent/late/duplicate availability signals; explain split-shift eligible/ineligible physicians; accept new live events | Predict coverage gap, rank eligible split-shift physicians, explain all reasons | Strong systems project but broadest operational complexity; requires event fixtures, eligibility constraints, explicit split-shift-trap definition |

### Track partners / sponsor specificity

The homepage associates Twinverse with Rutgers SHP & BMIHAI, Wellness Reimagined with Rutgers Health & BMIHAI, Ops Unleashed with Rutgers Health & RWJBH, and the Sevaro track with Sevaro. It names Amazon Web Services, Microsoft, and Sevaro as technology/resource supporters. [Official homepage](https://ruhealthhack.com/)

The challenge deck gives concrete Sevaro operational scenarios but does not provide hospital guides, the 80+ field schema, an event feed, the physician eligibility specification, or the definition of the split-shift trap. The brochure says datasets will be available during the event and mentions Microsoft, AWS, and Oracle; it does not specify accessible API keys, quotas, sample files, or deployment credits. Availability is a blocking dependency to resolve onsite, not an assumption.

## Prioritized TwinVerse direction

**Provisional choice: The Virtual Patient Encounter (PDF p. 6).** Build a reusable faculty-authored simulation system, with two faculty-reviewed original synthetic cases and a third held-out case for the live test. The product must cover Studio, encounter, feedback and the live new-case acceptance test; a chat-only patient is incomplete.

1. **Faculty Patient Studio:** editable structured patient profile, symptoms/history/exam findings, labs/ECGs/X-rays as attachments, learning objectives, disclosure conditions, preview, and faculty approval. Cases must be data that fit the same schema; do not create a special code path for each case.
2. **Grounded dialog:** the approved profile is the fact authority. Track each patient claim to a fact ID. Clinical facts absent from the case should stay unavailable instead of being fabricated. Ask a clinical mentor to validate the standard response for unknown history and findings.
3. **Progressively revealed chart:** an encounter ledger records what the student asked and what was elicited. The split-screen chart reveals the appropriate findings as the interview unfolds; do not show the entire answer key at encounter start. Requesting approved labs or images reveals those attachments; absence of an attachment is explicit.
4. **Objective-linked feedback:** connect elicited/missed facts to faculty-defined objectives; provide specific transcript evidence for communication/empathy feedback. Present observed behaviors and missing questions, not a claim that automated feedback has been clinically or educationally validated.
5. **Live new-case acceptance:** a faculty member uses the Studio to enter and approve a brand-new profile while judges watch. Start a fresh encounter immediately, interview it, reveal its facts/attachments, and show feedback linked to its own objectives. No restart, source edits, or patient-specific code.

Suggested five-person ownership, to be assigned by the team: faculty Studio/schema; encounter/chat/state; chart/attachments/interface; clinical content and adversarial evaluation; integration/deployment/demo/submission. Each owns a working output and one clear acceptance check. The clinical-content role still needs access to a qualified mentor; assigning a teammate does not make that teammate a clinician.

A practical demo promise: “A faculty member creates and approves a case; a student interviews that patient; the chart reveals only approved elicited facts; feedback explains what was learned or missed using the faculty's objectives.”

### Feasible boundary

Start with text interaction and uploaded attachments, one encounter, one approved schema, and a faculty-curated checklist. Voice, avatars, rich animation, diagnosis scoring, real EHR integration and multi-institution deployment can follow the complete Base loop. The multi-agent care journey is the separate Challenge 2 scope; it must not be silently promoted into Challenge 1 Base. Do not let those consume time before the live new-case test passes.

### Meaningful checks before Sunday

- A known-case student question produces the correct approved facts and records provenance.
- Asking about an absent medication, symptom, lab, or past event produces an honest unavailable response.
- Leading questions and instructions to disregard the case cannot insert new clinical facts.
- Previously unrevealed chart content remains concealed until the intended trigger; obtained facts persist through reload/reconnect.
- Feedback distinguishes “elicited,” “missed,” and “not assessable,” cites encounter evidence, and uses the current case objectives.
- An unapproved or malformed case cannot be launched; an approved case with different names/findings/objectives works through the same interface.
- A teammate creates a case that the implementation owner has never seen and the entire workflow runs without edits.

These are proposed prototype acceptance checks, not a retrieved official judging rubric. A deterministic evidence ledger for case facts and objectives provides a stronger demonstration than claiming the language model never makes mistakes.

## Before committing to an implementation

Resolve these with the challenge mentor/onsite organizer in the first 30-45 minutes:

- Obtain the full selected problem statement, sample data, field dictionary, and live-test input format.
- Record what must work at judging and what can be a stretch feature. Ask for scoring weights and how the required four-minute pitch relates to the faculty-led live new-case test.
- Verify submission platform, noon cutoff, required deck/video/repo/URL fields, permitted licenses/boilerplate, and track selection rules.
- Identify the clinical/domain reviewer and their availability Saturday. Book a first prototype review before midday.
- Choose a small fixture set before coding: ordinary case, ambiguous/missing data, adversarial case, and new unseen input.
- Write a one-sentence demo promise with a measurable observable; assign one owner to the interface, one to core logic/data, and one to validation/pitch/domain verification.

Do not assume the challenge's asserted problem statistics are independently verified. The deck's "60-70%" non-clinical call-bell figure and readmission story need primary evidence before being presented as general facts. Likewise, its 30-day deletion is a specific challenge requirement; the deck does not establish a universal law requiring patient discharge data to be deleted after 30 days.

## Scope pattern that fits the deadline

By Friday night: choose one challenge, get fixtures, define acceptance checks, and produce one vertical slice with a visibly real input/output. By Saturday noon: working end-to-end demo plus first mentor review. By Saturday evening: chosen unseen-input test, meaningful failure handling, evidence/results, and deployment. Sunday morning: freeze functionality, verify access from a second device, record a fallback demo, finish submission materials by 11:00 AM, and verify submission by 11:30 AM. Use the remaining time to repair submission/access problems.

The final narrative should explain a specific user's current work, show the smallest useful change, demonstrate one live unseen input, present measured prototype results with limitations, and state the next real-world validation step. The selected TwinVerse document supplies evaluation areas, but no numerical weights. This narrative structure is preparation rather than an invented scoring rubric.

## Relationship to the selected research

- [TwinVerse requirements](twinverse-requirements.md) records exact Base/Stretch scope, live-case judging, four-minute pitch and repository deliverables, and written-document/video discrepancies.
- [Clinical research](clinical-research.md) separates educational evidence, competitor capabilities and unvalidated hypotheses.
- [Technical and data research](technical-and-data-research.md) proposes the canonical approved-case contract, disclosure ledger, provider boundaries and evaluation checks.
- [Sponsor resources](sponsor-resources.md) maps AWS, Kiro, ElevenLabs and Anakin to bounded weekend uses.
- [Data sources and hospital context](data-sources-and-hospital-context.md) separates public aggregates and public maps from patient-case evidence or hospital-model calibration.
- [Recording and decisions](recording-and-decisions.md) preserves the broader hospital-world vision and its weekend boundary.
