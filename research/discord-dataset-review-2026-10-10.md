# Discord dataset review — October 10, 2026

## Recommendation

Use the **eight structured TwinVerse synthetic patient profiles**, the **faculty seed CSV**, and the **supplied encounter rubric** for Encounter Studio. They directly support reusable case authoring, approved patient facts, progressive disclosure, and explainable feedback. Start with a communication/nutrition case such as Yvette or Omar, subject to mentor selection and review. These supplied cases do not provide an approved acute chest-pain encounter.

For the longer-term hospital vision, the **new Sevaro synthetic operations kit** is the most useful additional resource. It supplies concrete event, staffing, eligibility, demand and coverage schemas. It can support a fictional tele-neurology operations replay; it cannot calibrate an RWJUH ED model.

The earlier project finding that TwinVerse case resources had not been obtained is superseded: organizers posted a separate Box resource folder after midnight. The earlier ZIP-only review did not include these later resources. The later Sevaro developer kit also supersedes the October 9 statement that data would only arrive at judging: development samples are now available, while unseen judging files remain promised.

## Evidence and coverage

Read the signed-in Rutgers Health Hack Discord server through the user's browser, including all four challenge channels, seven tech-partner channels, and a server-wide search for `dataset` (10 results). Followed the TwinVerse Box link and downloaded its 40-file resource bundle, the 80-product Vlada catalog, the updated Sevaro kit, and the eight-profile Hugging Face source. Parsed their small data files locally. Opened the NHANES folder and both glucose file links; large glucose/NHANES data were not downloaded or profiled.

Counts below distinguish records, files, products, and duplicated packaging. A sponsor offer is not proof of activated account entitlement or a successful query. No messages were sent, accounts created, agreements accepted, cloud resources changed, or data published.

Original packs and a normalized profile file are kept locally under ignored `.private/research/datasets-2026-10-10/`. The derived report is included in the public research handoff; original packs and normalized case files remain excluded. Discord links below identify the source channels; access-bearing attachment URLs and SharePoint links are omitted from this repository-facing document.

## Every identified data resource

| Resource | What is actually supplied | Fit for this project | Access/verification |
|---|---|---|---|
| TwinVerse structured patient profiles | 8 synthetic personas, 9 nested sections, JSON source | **Use first:** grounded interview, chart, disclosure, learning objectives | Public HF file downloaded and all 8 records parsed; CC BY 4.0 stated on card |
| Faculty sample patient CSV | 8 rows, 10 columns; patient IDs, summary, personality and portrait pointer | **Use:** seed/import table and original faculty content | Box file downloaded and parsed |
| Patient portraits | 8 named images plus a nested ZIP, duplicated across the two challenge folders | **Optional:** patient selection/avatar display | Archive inventory inspected; individual image provenance/license not independently established |
| Encounter evaluation materials | JSON rubric, matching-title PDF, pediatric-treatment DOCX | **Use:** feedback scaffold and faculty configuration | JSON fully parsed: 7 domains, scores 1–4 or N/A |
| Sample course | Hematology II Fall 2026 syllabus PDF | **Later:** curriculum/objective ingestion demonstration | File inventoried; full syllabus not analyzed |
| TwinVerse clinician personas | 5 structured JSON profiles + 5 DOCX counterparts | **Later:** supervisor conversation and interprofessional handoffs | All JSON profiles parsed; fictional-role resources, not real staff assignments |
| Patient–Doctor dialogue corpus | 60,640 rows with a text column containing conversations | **Secondary:** dialogue examples and testing interview flow | HF viewer inspected; no dataset card and no clear dataset-specific license/provenance established |
| Diagnostic Pathology Test Results | `health_markers_dataset.csv`, 1.53 MB, 9 biomarkers + condition label | **Low priority:** chart-import examples after consistency review | Kaggle description/schema inspected; row count and original clinical provenance not verified |
| Sevaro guided workflow kit | 7 synthetic hospital guides; context, field map, source conflicts, expected-answer cases and nudge scenarios | **Later:** source-grounded hospital protocol retrieval | Downloaded; structured JSON/CSV inspected |
| Sevaro operations kit | 12 hospitals, 14 physicians, 1,164 events and reference snapshots | **Best operations extension:** synthetic coverage/queue replay | Downloaded; every CSV counted and headers inspected |
| MetaboNet event file | `Type1Diabetes.parquet`, longitudinal glucose/insulin/carbohydrate data | **Separate future feature:** glucose-history chart or forecasting research | SharePoint file page reachable; full event-file schema/count/license tier not inspected |
| CGMacros 1.0.0 | CGM, meals/photos/macronutrients, activity and participant measurements | **Separate future feature:** meal/glucose teaching charts | Event ZIP page reachable; official documentation inspected, large archive not downloaded |
| NHANES 2021–2023 package | Cleaned/merged SAS file, example code/protocol DOCX, 4 papers | **Research context:** population distributions and study methods | Folder reachable; 73.8 MB SAS file inventoried, not analyzed |
| Vlada | 80 public/aggregate healthcare products | **Optional:** HCAHPS/cost/access context; later institution/cost modeling | Catalog downloaded, 80 rows extracted; event account/query execution untested |

The TwinVerse Box archive contains 16 Challenge 1 files, 23 Challenge 2 files, and one root pathology-link note. These are not 40 independent datasets: patient images and reference notes are duplicated, and many files are briefs/rubrics.

Sources: [TwinVerse Discord](https://discord.com/channels/1166068843232383016/1557194921507819581), [Sevaro Discord](https://discord.com/channels/1166068843232383016/1550181691128021102), [Wellness Discord](https://discord.com/channels/1166068843232383016/1557194969591316531), [Ops Unleashed Discord](https://discord.com/channels/1166068843232383016/1557195036742127746), [Vlada Discord](https://discord.com/channels/1166068843232383016/1558296151206273074).

## TwinVerse: direct implementation inputs

### Structured patient profiles

[Organizer's eight-profile dataset](https://huggingface.co/datasets/joeljames270/virtual-patient-profiles-sample) is explicitly synthetic and focused on dietetics/nutrition education. Its card declares CC BY 4.0 and asks users to cite the Rutgers VHS project. Inspected revision: `ee5c260a6e24cd9d6baf5c0ab7ec636788c64c70`.

| Section | How to use it |
|---|---|
| `patient_overview`, `demographics` | Patient identity and background |
| `clinical_profile` | Authored diagnoses, symptoms, allergies, findings, labs, vitals, anthropometrics |
| `medication_profile` | Medication names/doses, adherence and patient concerns |
| `nutrition_profile` | Diet, meals, activity and habits |
| `psychosocial_profile` | Communication style, goals, worries, motivations and barriers |
| `information_disclosure` | Initial, discoverable, reluctant and hidden information |
| `learning_opportunities` | Case objectives, expected discoveries and reactions |
| `metadata` | Generation assumptions and optional details that require review |

| Persona | Main teaching use suggested by the supplied profile |
|---|---|
| Yvette Armstrong, 64 | Health literacy, sodium explanations, checking understanding |
| Omar Sinclair, 45 | Medication skepticism and cardiovascular-risk counseling |
| Nisha Patel, 29 | Anxiety, detailed questions and diabetes counseling |
| Marcus Ramirez, 59 | Heart failure, early satiety and multiple-condition counseling |
| Walter Greene, 72 | Rapport, dietary adherence, aging and isolation |
| Wyatt Nelson, 18 | Young-person communication, bowel-health sensitivity and diet |
| Dominic Rivera, 22 | Trust, cultural humility and motivational interviewing |
| Vladko Bareche, 31 | Immigration context, substance-use conversations and dietary constraints |

**Observed import issues:** despite the `.jsonl` extension and card's one-record-per-line description, the downloaded source contains concatenated pretty-printed JSON objects. A strict JSONL parser fails. All eight objects were recovered with a streaming JSON decoder and saved as `patients.normalized.jsonl` without changing case content. Faculty CSV headers include `patient-uuid`, `patient-name`, `age`, `background`, `gender`, `notes`, `patient-img`, `personality`, `race/ethinicity`, and `summary`; retain an explicit mapping for the misspelled ethnicity field.

The CSV portrait pointers are S3 URIs, while supplied images have person-name filenames. Public folder access does not establish S3 credentials. Map local portraits to UUIDs; the archive contains `Vadko Bareche patient.png` while the CSV/profile name is Vladko. The dataset card acknowledges generated inconsistencies. Visible records also contain dubious/inconsistent terms (for example “Non-Human Sexually Transmitted Infection” and “NYHA Stage C”) and unfinished text. Record those as review issues rather than silently making them clinical truth.

Recommended import path: original source → normalized draft → faculty corrections → explicit approval/version → encounter. Keep source assumptions separate from faculty-approved facts. Use the nutrition cases as supplied contexts; adapting one to an ER case requires new approved content.

### Supplied rubric

The JSON defines seven domains: opening/purpose; rapport/respect/empathy; information gathering; listening/responding to cues; explanation/shared decisions; clinical reasoning/synthesis; and professionalism/safety/closure. It allows 4 (Strong), 3 (Competent), 2 (Developing), 1 (Unsafe or absent), or N/A. Rate only observable criteria. Maximum all-applicable total is 28, explicitly a discussion aid rather than a pass/fail grade. A score of 1 in clinical reasoning or professionalism/safety triggers review.

This is a newly obtained organizer example rubric, distinct from the earlier proposed 12/18-point totals and objective-status approach. Make it a versioned faculty-configurable rubric alongside objective evidence. Preserve N/A, explain the applicable denominator, attach transcript evidence and missed opportunities, and keep safety review visible. Organizer supply does not establish psychometric validation of automated grading.

### Clinician profiles and other external leads

The five JSON profiles describe an emergency attending (Brian Lee), cardiologist (David Bennet), pharmacist (Nasir Mahmoud), hospitalist (Priya Narang), and dietitian (Tasha Dunbar). They contain clinical role, communication, simulation behavior, interprofessional relationships, learning opportunities and assumptions. Useful for a later supervisor/handoff feature. They do not encode live staffing schedules, queues, capacity or service-time distributions. The evaluation note names TeamSTEPPS and SBAR; it is not a populated scoring dataset.

[Patient–Doctor](https://huggingface.co/datasets/Postzeun/Patient-Doctor) has a single train split and 60,640 text records. Treat it as a lead for conversational examples. Without a dataset card, clear source history and verified reuse rights, avoid bulk importing or fine-tuning on it. It is not an approved case bank or grading ground truth.

[Diagnostic Pathology Test Results](https://www.kaggle.com/datasets/pareshbadnore/diagnostic-pathology-test-results) advertises Blood_glucose, HbA1C, Systolic_BP, Diastolic_BP, LDL, HDL, Triglycerides, Haemoglobin, MCV and Condition (Fit/Anemia/Hypertension/Diabetes/High Cholesterol). The uploader calls it real-world data; that claim was not independently substantiated. The page lists Open Database/Database Contents licenses. Prefer each approved profile's own labs; randomly joining external lab rows to a persona can break consistency. This resource is tabular biomarkers, not pathology slide images.

## Sevaro: concrete synthetic operations and workflow data

The kit README explicitly states that all data is synthetic, with no patient data, real hospital protocols, or production access, and is for hackathon prototyping. New same-format data will be supplied at judging, with live loading expected. Cross-track use in a TwinVerse submission remains unconfirmed; treat it as an architectural/research lead until organizer expectations are resolved.

| Operations file | Inspected count | Model use |
|---|---:|---|
| `event_stream.csv` | 1,164 events, 07:00–18:20 ET | Reconstruct shifts, physician/consult state; distinguish event time and ingestion time |
| `hospitals.csv` | 12 rows | Hospital identity, timezone, coverage tier |
| `physicians_on_shift.csv` | 8 rows | Shift start/end and eligibility |
| `physicians_off_shift_roster.csv` | 6 rows | Opt-in, rest/work history, time-to-online and contact-channel attributes |
| `credentialing_matrix.csv` | 14 rows × 12 hospital eligibility columns | Constrain assignments to credentialed physicians |
| `baseline_hourly_volume.csv` | 288 rows | Mean/p90 demand by hospital and hourly block; includes weeks sampled |
| `coverage_requirements.csv` | 36 rows | Minimum available credentialed physicians by hospital/time block |
| `snapshot_physicians_1820.csv` | 8 rows | Reference physician state for replay comparison |
| `snapshot_open_consults_1820.csv` | 18 rows | Reference consult queues/stages for replay comparison |

Build a deterministic replay that matches the reference snapshots before exploring any staffing recommendation. These are tele-neurology consult operations, not measured ED arrivals, bed turnover or nurse staffing. Published baseline means/p90s do not by themselves establish a validated arrival model or causal policy effect.

| Guided-workflow file | Inspected content | Useful pattern |
|---|---|---|
| `hospital_guides.json` | 7 synthetic hospital guides, per-field verification dates | Versioned local protocol/source retrieval |
| `storyboard_notes.json` | Conflicting/agreement examples against guides | Surface source discrepancies |
| `caselog_field_map.csv` | 11 rows | Map workflow steps/fields to source facts and nudges |
| `encounter_context_example.json` | Hospital, consult, event, local/provider timezones | Context-aware retrieval contract |
| `validation_set.csv` | 20 questions with expected answers/status/source fields | Verify retrieval/abstention behavior |
| `nudge_scenarios.json` | N1–N9 | Event-triggered advisory examples |

For Encounter Studio, borrow the provenance/conflict pattern, not the synthetic hospital's treatment protocols as clinical guidance.

## Glucose and NHANES: useful for other modules

**MetaboNet:** the event link resolves to `Type1Diabetes.parquet`. The [official format](https://metabo-net.org/data) uses a five-minute grid with glucose, basal/bolus insulin, carbs, timestamps, subject IDs and study-dependent activity/physiology fields. The [project access notes](https://metabo-net.org/about) distinguish public and DUA-protected source tiers. The event export's exact subjects, study mix, size and permitted redistribution remain unknown. This is Type 1 diabetes research; do not substitute its dynamics for the supplied Type 2 nutrition personas.

**CGMacros:** the linked ZIP is version 1.0.0. [Official PhysioNet documentation](https://physionet.org/content/cgmacros/1.0.0/) describes 45 participants (15 healthy, 16 prediabetes, 14 Type 2 diabetes), ten-day recordings, two CGMs, meal composition/photos, activity and other measurements. License is CC BY-NC-SA 4.0. It fits an optional meal/glucose teaching replay better than generic hospital physiology. Small-cohort results do not establish an individual treatment model. Organizer's seven-days→eighth-day prediction task belongs to Wellness. Large event ZIP not downloaded; per-person completeness not checked.

**NHANES:** organizer supplied merged/cleaned 2021–2023 data. The reachable folder contains `nhanes20212023.sas7bdat` (73.8 MB), `Example Codes and Protocol.docx`, and four `NHANES_Paper*.pdf` files. Best use is population-level context and survey-analysis research, not a patient conversation script or hospital event stream. Variable availability, analytic cohort, survey weights, strata/PSUs, cleaning and missingness must be inspected before estimating population quantities. This review did not open the SAS data or verify its cleaning.

## Vlada: optional aggregate context

The October 10 kickoff slide and participant guide offer free event access until **Monday October 12, 9 a.m. ET**. Account activation and actual query access were not exercised. Data discovery is via `find_data_sources` → `describe_data_source` → typed tool or read-only SQL, with the guide's 200-row response cap. Keep exact source, period, geography, measure/code, exclusions and missingness with any result.

Recommended shortlist: HCAHPS communication measures for a debrief context card; NADAC/Part D formularies for a medication-access illustration; HPSA for access context; provider/facility identity + POS for institution context; hospital standard charges + HCRIS for a later cost module. These do not populate clinical facts, validate a grade, or calibrate hospital queue dynamics.

The catalog's 80-product claim and held years are sponsor statements, not our query verification. Dates vary; Cost Plus is a single May 16, 2026 capture, geography is 2020 vintage, ICD-10 FY2021–25 is flagged for fixes, and federal-exchange data excludes NJ in the participant guide. Refer to the [earlier detailed source boundaries](data-sources-and-hospital-context.md) for interpreting rates, adverse-event reports and quality data. Individual underlying-source and assembled-product terms still apply.

## Full 80-product Vlada inventory

Every row below was extracted from the downloaded five-page catalog. The project-fit column is our engineering assessment, not the sponsor's claim. Category counts: drugs/devices 21; FFS 17; MA/Part D 12; providers 10; quality 9; reference 5; transparency 3; state programs 2; exchange 1.

### Drugs and devices (21)

| Product | Sponsor-listed years | Project fit |
|---|---|---|
| Medicaid State Drug Utilization | 1991–2026 | Later drug identity, access, cost or supply context |
| CMS Open Payments (Sunshine Act) | 2016–2025 | Later drug identity, access, cost or supply context |
| NADAC — National Average Drug Acquisition Cost | 2013-11 to 2026- 09 | Optional medication acquisition-cost illustration |
| Drug Product Catalog (NDC) | 2016–2026 | Later drug identity, access, cost or supply context |
| NLM AccessGUDID — Device Identity (FDA Global UDI Database) | 2026 only | Later drug identity, access, cost or supply context |
| FDA FAERS — Adverse-Event Drug Involvement (DRUG file) | 2025Q1-2026Q2 | Report counts only; avoid diagnostic/physiology use |
| Medicaid Drug Rebate Program — product file | 2014–2026 | Later drug identity, access, cost or supply context |
| FDA Orange Book | 2021–2026 (current list Oct 2026) | Later drug identity, access, cost or supply context |
| FDA Drug Master Files (DMF) | 2020–2026 | Later drug identity, access, cost or supply context |
| FDA Drug Applications (NDA/ANDA/BLA dimension) | 2019–2026 | Later drug identity, access, cost or supply context |
| Clinical Trials (ClinicalTrials.gov, drug- regulated) | 1999–2026 | Later drug identity, access, cost or supply context |
| VA Federal Supply Schedule (FSS) drug prices | 2019–2026 | Later drug identity, access, cost or supply context |
| Medicare Part B Drug Pricing & Utilization | Q1 2005 - Q4 2026 | Later drug identity, access, cost or supply context |
| Drug Classification (RxClass) | 2026 | Later drug identity, access, cost or supply context |
| FDA Drug Recalls (Enforcement Reports) | 2012–2026 | Later drug identity, access, cost or supply context |
| FDA Purple Book — licensed biologics + biosimilars | 2020–2026 | Later drug identity, access, cost or supply context |
| FDA Warning Letters | letters issued 2021–2026 | Later drug identity, access, cost or supply context |
| FDA Drug Shortages | shortage postings 2012– 2026 | Later drug identity, access, cost or supply context |
| Consumer cash-price reference (Cost Plus Drugs snapshot) | one capture 2026-05-16 | Optional dated cost illustration; not live price |
| WAC increases — California HCAI SB 17 notices | 2025–2026 | Later drug identity, access, cost or supply context |
| IRA Maximum Fair Price (CMS- negotiated) | price applicability years 2026 and 2027 | Later drug identity, access, cost or supply context |

### Medicare FFS (17)

| Product | Sponsor-listed years | Project fit |
|---|---|---|
| CMS Physician/Supplier Procedure Summary (PSPS) | 2010–2025 | Later payment/utilization benchmarks |
| Medicare Fee-for-Service Utilization & Payments | 2013–2024 | Later payment/utilization benchmarks |
| Medicare DME Utilization & Rates | 2014–2024 | Later payment/utilization benchmarks |
| CMS Medicare Market Saturation & Utilization | rolling windows 2014-10/2015-09 through CY2025 | Later payment/utilization benchmarks |
| Medicare Hospital Outpatient (OPPS) Rates | 2004–2026 | Later payment/utilization benchmarks |
| Medicare Clinical Laboratory Fee Schedule (CLFS) | Fee schedule 2019–2026; private-payer 2018, 2026 | Later payment/utilization benchmarks |
| Medicare Physician Fee Schedule (PFS) | 2003–2026 | Later payment/utilization benchmarks |
| Medicare Ambulatory Surgery Center (ASC) Rates | 2001–2026 | Later payment/utilization benchmarks |
| Medicare Inpatient Prospective Payment System (IPPS) | FY2006–2026 | Later payment/utilization benchmarks |
| CMS Medicare Geographic Variation | 2007–2024 | Later payment/utilization benchmarks |
| CMS Medicare Ambulance Fee Schedule (AFS) Public Use File | 2004–2026 | Later payment/utilization benchmarks |
| Medicare Inpatient Rehabilitation Facility PPS Weights | FY2006-FY2027 | Later payment/utilization benchmarks |
| CMS LTCH PPS MS-LTC-DRG Relative Weights (Table 11) | FY2021-FY2027 | Later payment/utilization benchmarks |
| Medicare Home Health PDGM Weights | CY2020-CY2026 | Later payment/utilization benchmarks |
| Medicare Skilled Nursing Facility PDPM Rates | FY2020-FY2027 | Later payment/utilization benchmarks |
| Medicare Hospice Prospective Payment Rates | FY2005-FY2027 | Later payment/utilization benchmarks |
| Medicare FQHC Prospective Payment Rates | 2014, 2016–2026 | Later payment/utilization benchmarks |

### Medicare Advantage / Part D (12)

| Product | Sponsor-listed years | Project fit |
|---|---|---|
| Part D Plans & Formularies | 2019-Q1 to 2026- Q2 | Optional medication-access example |
| Medicare Advantage & Part D Enrollment | 2006-07 to 2026-09 | Later insurance/access context |
| Medicare Part D Prescriber Utilization | 2013–2024 | Later insurance/access context |
| Medicare Advantage & Part D Plan Landscape | 2006-10 to 2026- 09 | Later insurance/access context |
| Medicare Advantage Plan Benefit Packages (PBP) | 2001–2027 | Later insurance/access context |
| Medicare Advantage HEDIS Quality | 2019, 2021–2025 | Later insurance/access context |
| Medicare Advantage Star Ratings | 2007–2027 | Later insurance/access context |
| Medicare Advantage Plan Payments & Bids | Payments 2006– 2024; MLR 2018 on | Later insurance/access context |
| CMS-HCC Risk Adjustment Model | rate years 2016– 2027 | Later insurance/access context |
| Medicare Plan Crosswalks | 2006–2027 | Later insurance/access context |
| Medicare Part D Spending by Drug (PUF) | 2019–2024 | Later insurance/access context |
| Medicare Advantage County Ratebook | 2015–2027 | Later insurance/access context |

### Providers and ownership (10)

| Product | Sponsor-listed years | Project fit |
|---|---|---|
| Provider Enrollment & Ownership (PECOS) | 2016–2026 | Later institution/provider context |
| Vlada Provider & Facility Identity | current | Resolve facility/provider identities; no shifts |
| OIG Exclusions & Integrity Agreements | 2016–2026 | Later institution/provider context |
| CMS Provider of Services (POS) File | 2011–2026 | Historical certified facility/bed context; no live capacity |
| Hospital Cost Reports (HCRIS) | FY2011–2024 | Later hospital accounting cost context |
| HRSA Health Professional Shortage Areas (HPSA) | 2020–2026 | Optional access/shortage-area teaching context |
| HRSA 340B Covered Entities | 2026 | Later institution/provider context |
| Medicare Post-Acute Care Utilization | 2013–2024 | Later institution/provider context |
| Medicare ACO Participants | 2016–2026 | Later institution/provider context |
| Medicare Diabetes Prevention Program (MDPP) Suppliers | 2024–2026 | Later institution/provider context |

### Quality and outcomes (9)

| Product | Sponsor-listed years | Project fit |
|---|---|---|
| CMS Quality Payment Program Experience | 2017–2024 | Later quality-context comparison |
| CMS Care Compare HCAHPS — Hospital patient-experience survey | 2014–2025 | Best optional communication-motivation card |
| CMS Care Compare Hospice provider-quality measures | 2019–2026 | Later quality-context comparison |
| CMS Hospital Readmissions Reduction Program (HRRP) | FY2013-FY2026 | Later quality-context comparison |
| CMS Care Compare Home Health Agencies — per- agency quality | 2015–2026 | Later quality-context comparison |
| CMS ESRD QIP Total Performance Score (dialysis pay-for-performance) | PY2012–2021 and PY2023–2026 | Later quality-context comparison |
| CMS Dialysis Facilities & Quality | 2019–2026 | Later quality-context comparison |
| CMS Care Compare Nursing Home (Provider Information) — 5-star quality | 2026 only | Later quality-context comparison |
| CMS Hospital Value-Based Purchasing (HVBP) Total Performance Score | FY2026 only | Later quality-context comparison |

### Reference and geography (5)

| Product | Sponsor-listed years | Project fit |
|---|---|---|
| ICD-10-CM Diagnosis Code Dimension | FY2012–2027 (FY2021–25 needs fixing) | Optional codes; verify release, FY2021–25 flagged |
| ICD-10-PCS Inpatient Procedure Code Dimension | FY2012–2027 (FY2021–25 needs fixing) | Optional codes; verify release, FY2021–25 flagged |
| Billing Code Intelligence | current | Optional codes/identity/geography |
| U.S. Geography Crosswalk (ZIP ↔ County ↔ CBSA ↔ State) | 2020 vintage | Optional codes/identity/geography |
| NUCC Healthcare Provider Taxonomy Code Set | releases 2009-01 to 2026-07 | Optional codes/identity/geography |

### Transparency (3)

| Product | Sponsor-listed years | Project fit |
|---|---|---|
| Hospital Standard Charges (Price Transparency) | 2026 | Later sourced procedure-charge illustration |
| Form 5500 Filings & Service Providers | 2009–2025 | Later cost/benefit context |
| Massachusetts Commercial Hospital Price & Cost Benchmarks | 2018–2023 | Later cost/benefit context |

### State programs (2)

| Product | Sponsor-listed years | Project fit |
|---|---|---|
| Maryland All-Payer Hospital Rates & Volumes | Revenue 2016– 2026; unit rates 2013–2024, 2026 | Comparative state policy context |
| Connecticut Medicaid Inpatient Rates | 2023 and 2026 | Comparative state policy context |

### Exchange (1)

| Product | Sponsor-listed years | Project fit |
|---|---|---|
| Individual Exchange | 2014–2026 | Federal-exchange context; NJ excluded |

## Proposed build sequence

1. Import the supplied eight profiles as drafts; use CSV UUIDs to preserve identity and explicitly reconcile the richer profile against the faculty seed.
2. Select one supplied case with a mentor, correct inconsistencies and approve facts, disclosure and objectives.
3. Use the supplied rubric with transcript evidence, N/A, faculty review flags and a versioned scale.
4. Finish Studio → approved encounter/chart → evidence-linked debrief before adding data-dependent features.
5. If time remains, add one dated HCAHPS/access card. For the future operations branch, implement Sevaro event replay against its snapshots, subject to cross-track reuse permission.

Remaining gaps: exact asset reuse rights, cross-track Sevaro use, sponsor query entitlement, clinician approval, and calibrated RWJUH hospital data. No accessed source provides a verified whole-hospital physiology model or real-time RWJUH staffing/bed state.

## Other sponsor channels

At inspection, Cigna and Sevaro's tech-partner channels contained no dataset posts. Sevaro's challenge channel does contain the later developer kit above. Microsoft offered Azure account access; AWS described cloud/AI services and workshops; Anakin and ElevenLabs posted their participant/credit guides. These are tool/access resources; this review found no separate named clinical dataset in those channels. Cigna's in-person table may have resources not posted online, so Discord inspection cannot establish their absence onsite.
