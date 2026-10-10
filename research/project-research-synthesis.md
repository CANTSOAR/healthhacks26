# ChatGPT project research synthesis

Consolidated October 10, 2026 from the team's signed-in Health Hacks project. This is derived planning research, not a transcript export. Fifteen conversation titles were inventoried; their recommendations, principal findings and limitations were inspected. Long responses were read in selected sections, not every cited appendix or paper. Chat outputs are secondary research leads: their claims of verification are not independent verification by this repository review. Original chats and participant identifiers remain private.

## What the project adds

| Conversation | Useful contribution | Adoption / verification boundary |
|---|---|---|
| Project Handoff Summary | Shared authoring, approval, events and assessment; distinct interview and operations engines | Architecture proposal. Its suggested two-demo slice is too large for the locked weekend scope |
| Hospital Simulation Action Plan | Encounter Studio → Operations Lab → Hospital World; common entity IDs and reproducibility | Adopt staged architecture; exact provider access remains a separate gate |
| Validation framework design | Operational conservation, holdout calibration, policy feasibility, educational transfer | Adopt separate operational and educational validation dossiers; no validation achieved |
| Design Training Scenarios | Surge, nursing absence, imaging failure, discharge delay, elective-capacity tradeoffs | Later scenario library; numerical examples are hypothetical |
| Compare Simulation Approaches | DES for queues/resources, selective agent behavior, longer-term strategic models | Numerical controller computes state; LLM narrates and coaches |
| Hospital data request draft | Process map → aggregate inputs → minimum event data if necessary → holdout | Adopt minimum-data request below; no institutional data access established |
| ER Encounter Workflow Research | Initial assessment, focused interviewing, chart reconciliation, supervisor presentation | Student scope and safety reviewed by faculty; presentation differs from transfer of responsibility |
| Research on Assessment Rubrics | Observable communication criteria, evidence spans, human agreement, limits of text | Candidate instruments need original-source and adaptation-rights checks |
| Design Hospital Curriculum | Shift, weekly and strategic horizons with different decision authority | Later curriculum, not extra Challenge 1 requirements |
| ER Simulation Evidence Review | Flow-engine studies and calibration limits | Paper leads, not empirical parameters for RWJUH |
| Compare Healthcare Datasets | Synthetic longitudinal records, restricted clinical datasets, aggregate claims | Each dataset/version has separate rights and task suitability |
| Research simulation resources | MedEdPORTAL scripts, ECG/CXR assets, per-image permissions | Candidate pack; inspect individual files before reuse |
| Virtual Patient Evidence Review | Mixed outcomes; active comparators, unseen assessments, retention and transfer | Do not inherit other systems' learning gains or nonverbal claims |
| Synthetic Patient Validation Research | Structural, temporal, cross-field clinical and conversational checks | Automation flags issues; clinical approval remains independent |
| Compare Interview Scenarios | Stable possible-ACS interview versus syncope/abdominal pain; draft six objectives | Draft content requires clinical review; no case approved by this review |

## Consolidated design decisions

The weekend remains one complete faculty-authoring → approved patient → interview/chart → evidence-linked debrief workflow. Preserve the full hospital vision through compatible data contracts, rather than adding a second unfinished demonstration. Operational scenarios, curriculum and detailed geometry are later modules with their own acceptance gates.

Use three layers: **Encounter Studio** owns approved facts, artifacts, disclosure and learning objectives; **Operations Lab** owns events, queues, staff eligibility and numerical resource consequences; **Hospital World** presents the same IDs and state in an optional map/3-D scene. Patient conversation cannot create lab results, staffing capacity, diagnoses or queue outcomes. An operational action is a request with authority, prerequisites and delay, not an instant unconstrained state change.

Separate wall-clock latency, teaching session time and simulated clinical/operational time. Advancing an interview must not silently complete diagnostic testing. Keep available urgent information accessible, permit escalation before checklist completion, and identify whether a finding was volunteered, elicited, read in the chart or authored by a supervisor. Existing chart access should not require guessing a question keyword. Faculty can configure staged or whole-chart availability while retaining the challenge's progressive interview record.

## Conflicts resolved

- **First case:** one chat recommends an inferior-STEMI source pack; another recommends a stable possible-ACS interview with no confirmed diagnosis and pending troponin. These are different cases. Do not mix a STEMI ECG into the stable draft. Prefer the narrower interview-only draft for mentor selection; no clinical facts, timings or interpretation become approved merely by importing this research.
- **Scoring:** drafts suggest six domains scored 0–2 (12 total) and 0–3 (18 total). Neither is a validated platform scale. Core encounter feedback uses objective-level `met`, `partly_demonstrated`, `not_observed`, or `not_assessable`, with separate safety/review flags and evidence. Later administrator rubrics must have an explicitly versioned scale approved for their own tasks. No shared generic competency total.
- **Publication rights:** open reading, dataset access, article license, third-party image license and external-model processing rights are distinct. A case needs an asset-level rights record and reviewer decision.
- **Research outcomes:** satisfaction, simulated skill, retention, workplace transfer and patient benefit are separate outcomes. An in-app score cannot be the sole effectiveness assessment. Proposed study counts in chats are planning examples, not completed experiments or powered sample requirements.

## Data request for a credible operations model

Start with a process interview and data dictionary. Ask for unit/bed compatibility, physical versus staffed versus unavailable capacity, shift/skill constraints, demand counts by hour/day and broad route, transfer rules, diagnostic/support-service capacity, discharge/cleaning/transport stages, and disruptions. Public provider directories do not supply these inputs.

Prefer aggregates and distributions first: counts, histograms/quantiles, sample sizes, observation windows, units, exclusions, missingness and censored unfinished waits. Distinguish order-to-start, service duration, result turnaround, admission-decision-to-departure boarding, discharge-ready-to-departure and vacated-to-ready cleaning. Preserve authorized dependencies between acuity, destination and duration rather than sampling each independently. Check census conservation with admissions, transfers and departures.

If event data is necessary, request only approved event type, elapsed times, broad origin/destination and exception categories. A tokenized patient ID is not itself evidence of permission to use or upload a record. Hospital authorization, applicable agreements and a permitted processing environment precede ingestion. Request an untouched validation period; period length depends on volume, seasonality and task, rather than adopting arbitrary chat examples.

Until such data exists, label the operations module **synthetic training**, with exposed assumed parameters and sensitivity ranges. It is not a calibrated RWJUH forecast, causal estimate of a policy, or physiology model. Face review and technical invariants are useful but do not establish predictive validity.

## Primary checks and research leads

Checked during this consolidation: [SAEM's undifferentiated-patient curriculum](https://www.saem.org/about-saem/academies-interest-groups-affiliates2/cdem/for-students/online-education/m3-curriculum/group-approach-to-the-undifferentiated-patient/approach-to-the-undifferentiated-patient) supports adapting the encounter to acuity instead of enforcing a rigid history-before-care order. [MIMIC-IV-ED Demo 2.2](https://physionet.org/content/mimic-iv-ed-demo/2.2/) is an open-access, deidentified subset of 100 real patients with six relational tables; it is not synthetic, representative hospital calibration data, or a ready patient script. Use its schema as a lead before deciding whether record ingestion is needed. Full [MIMIC-IV-ED 2.2](https://physionet.org/content/mimic-iv-ed/2.2/) remains credentialed.

Additional leads from the project, **not independently revalidated here**:

| Lead | What to extract next |
|---|---|
| [Heitz chest-pain teaching module](https://doi.org/10.15766/mep_2374-8265.9482), [Jackson cardiology clinic](https://doi.org/10.15766/mep_2374-8265.11008) | Learner level, current clinical applicability, scripts/artifacts and individual-file rights |
| [Kron communication trial](https://doi.org/10.1016/j.pec.2016.10.024), [Reger motivational-interviewing trial](https://doi.org/10.1001/jamanetworkopen.2020.17348) | Comparator, independent outcome, intervention differences, retention limits; no transfer of effect size to our app |
| [Synthea validation](https://doi.org/10.1186/s12911-019-0793-0) | Cross-field validity limits and clinically relevant defects |
| [STRESS-DES reporting guidance](https://doi.org/10.1080/17477778.2018.1442155), [ED model validation](https://doi.org/10.1007/s10916-009-9307-4) | Reproducibility and validation design, not local service-time constants |
| [PTB-XL 1.0.3](https://physionet.org/content/ptb-xl/1.0.3/) | Version, license, waveform/label meaning and clinician-selected compatible ECG; no bulk download needed for P0 |
| SEGUE, Calgary–Cambridge/GCRS, Four Habits, CARE, mini-CEX and IDEA | Original instrument, intended observable construct, rights and adaptation limits; patient perception and workplace observation cannot be inferred from text alone |

Use the [Luna workflow pack](luna-data-workflows.md) and [acquisition manifest](data-acquisition-manifest.json) to expand these leads with provenance and explicit gaps. This review consolidated research; it did not run the full acquisition pipeline, obtain hospital data, approve a clinical case, or implement the product.
