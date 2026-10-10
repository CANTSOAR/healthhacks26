# Data sources and hospital context

Research checked October 9, 2026, America/New_York. This supports the TwinVerse Virtual Patient Encounter plan. The supplied PDFs are source material; their setup steps and invitations do not authorize account creation, agreement acceptance, service activation, external messages, or dataset downloads. None of those actions occurred in this review.

## Decisions for the Sunday submission

Keep the core as a faculty-authored, approved synthetic patient, a student encounter, a progressively revealed chart, and feedback traceable to the approved objectives and actual student actions. The additional material strengthens the data provenance and future hospital context; it does not supply a coherent clinical case or a calibrated hospital operational model.

1. **P0 clinical case data:** Original synthetic case content, reviewed by an available clinician/faculty mentor. Preserve the reviewer, version, date, sources, approved answers, disclosure rules, and permitted assets. The model interprets questions; the server retrieves approved facts. Neither a drug price nor a hospital quality score should become a patient symptom or a bedside finding.
2. **P1 optional sponsor feature:** After the encounter passes its acceptance checks, add one cited, faculty-reviewed context card in the debrief: communication/patient experience, or financial/access context. The card is separate from the patient's clinical truth and the encounter grade. A frozen, permitted snapshot keeps the demonstration independent of sponsor congestion and the free-access expiry.
3. **Hospital setting:** A small original schematic can evoke a teaching hospital or ER. Public RWJUH sources support location and specialty context. They do not establish room inventories, on-shift staff, bed availability, patient queues, or routes within a verified current ED. Use fictional staff identities in the prototype.
4. **Future operations track:** Facility identity, published bed counts, historical utilization, cost reports, and hospital quality can contextualize later research. Arrival/service-time distributions, acuity, staffing calendars, boarding/routing rules, and independently observed validation data still have to be obtained and calibrated. No staffing optimization or wait-time forecast is supported by these sources.

These are planning recommendations derived from the supplied sources and the scope; they are not sponsor requirements or tested implementation results.

## Vlada participant guide: useful access rules and boundaries

Source: Vlada - Rutgers Health Hack guide.pdf, pages 1-2 (organizer-supplied participant material; original file omitted from this public repository). Both pages were extracted and visually inspected.

| Guide statement | Plan implication |
|---|---|
| Free to participants and mentors until **Monday, October 12, 9 a.m. ET**; no card | Treat access as a workshop resource with an expiry after the Sunday submission. Do not make the submitted application depend on the event account remaining free. |
| Open the event link and sign in before linking an AI client; use the same email on both steps | A teammate can follow the PDF's event setup once access is needed. Setup is a work item, not something this research review performed. |
| One account per person; shared logins share an allowance | Each participating teammate uses their own account. Do not put a shared personal login/token into the app or repository. |
| The email code comes from workos-mail.com | Check the event instructions and spam folder during setup; the review did not request or read authentication codes. |
| If access says a plan is required, complete event sign-in and wait briefly before retrying | Timebox troubleshooting; verify event entitlement before any paid upgrade. |
| Busy response: wait about 10 seconds; do not repeatedly fire the same query | Use a bounded retry/backoff and a cached fallback for the demonstration. |
| Public, aggregate data; **no patient records, clinical notes, or claims** | Does not provide individual clinical histories or case dialogue. Some public utilization products derive from claims, but they are not longitudinal individual claims access. |
| Strongest coverage is cost, insurance coverage, access, quality, policy | A contextual teaching card fits; synthetic patient state stays independent. |
| ACA Marketplace coverage is HealthCare.gov states and explicitly excludes New Jersey's own exchange | Do not use this product to claim complete New Jersey individual-market coverage. |
| Sources, methods, exclusions, and cleaning accompany answers | Retain them with every number copied into the app or pitch. |
| Builder flow: `find_data_sources` → `describe_data_source` → a typed tool, or read-only `query_substrate` SQL | Inspect schema, required filters, and known traps before querying. Aggregate in SQL. |
| Answers capped at **200 rows per call** | A small filtered aggregate is appropriate. A broad row export is not the intended workflow. |

The [official Vlada data-access page](https://www.vladahealth.com/data-access) confirms its generic MCP endpoint and OAuth connection. Its general starter-credit offer differs from the event-specific access described by the supplied guide; the event entitlement was not activated or independently tested. The public site is a product description, not proof that every catalog product currently works for this account.

The guide's sample NJ enrollment, insurer prices, prior-authorization counts, and plan-benefit figures are **examples of answers the sponsor says it obtained**. This review has not reproduced those queries. Do not copy them into the pitch as independently verified statistics or live prices.

## All 80 catalog products, mapped to the actual scope

Source: Vlada - all data sources.pdf, pages 1-5 (organizer-supplied catalog; original file omitted from this public repository). All pages were extracted; pages 1 and 4 were additionally visually inspected. Names below are abbreviated where the distinction remains clear. The catalog says the products were tested from a customer account on October 8; that is the sponsor's claim, not this team's verification. The category counts sum to 80.

| Category | Count | Complete inventory | Use for this project |
|---|---:|---|---|
| Drugs and devices | 21 | Medicaid State Drug Utilization; CMS Open Payments; NADAC; NDC drug catalog; AccessGUDID device identity; FAERS drug involvement; Medicaid Drug Rebate product file; FDA Orange Book; Drug Master Files; drug applications; ClinicalTrials.gov drug-regulated studies; VA Federal Supply Schedule drug prices; Medicare Part B drug pricing/utilization; RxClass; FDA drug recalls; Purple Book biologics/biosimilars; FDA warning letters; drug shortages; Cost Plus Drugs cash-price snapshot; California SB 17 WAC increases; IRA Maximum Fair Price | Optional identity, cost, shortage, or evidence context. None supplies a patient history or an approved treatment-response model. |
| Medicare FFS rates and utilization | 17 | Physician/Supplier Procedure Summary; provider utilization/payments; DME utilization/rates; market saturation/utilization; hospital outpatient OPPS rates; clinical laboratory fee schedule; physician fee schedule; ambulatory surgery center rates; inpatient IPPS; geographic variation; ambulance fee schedule; inpatient rehabilitation PPS weights; LTCH DRG weights; home health PDGM weights; skilled nursing PDPM rates; hospice PPS rates; FQHC PPS rates | Historical utilization and payment benchmarks for a later cost module. Payment is not clinical appropriateness or a patient's out-of-pocket bill. |
| Medicare Advantage and Part D | 12 | Part D plans/formularies; enrollment; Part D prescriber utilization; plan landscape; plan benefit packages; HEDIS quality; Star Ratings; plan payments/bids; CMS-HCC risk models; plan crosswalks; Part D spending by drug; county ratebook | Optional plan/access teaching context or a later population model. Plan availability is not proof of an individual's enrollment, coverage decision, or authorization. |
| Providers and ownership | 10 | PECOS enrollment/ownership; Vlada provider/facility identity; OIG exclusions/integrity agreements; Provider of Services file; HCRIS cost reports; HRSA shortage areas; HRSA 340B covered entities; post-acute utilization; ACO participants; Diabetes Prevention Program suppliers | Facility identifiers and public organizational context. No doctor-to-floor-to-shift assignment, real-time staffing, or employee schedule. |
| Quality and outcomes | 9 | Quality Payment Program experience; hospital HCAHPS; hospice quality; Hospital Readmissions Reduction Program; home health agency quality; ESRD QIP scores; dialysis facilities/quality; nursing home provider information/5-star quality; Hospital Value-Based Purchasing scores | HCAHPS can motivate communication training; other scores support a later institution comparison. No evidence that this simulation improves any hospital outcome. Nursing-home staffing is not RWJUH staffing. |
| Reference and geography | 5 | ICD-10-CM diagnosis dimension; ICD-10-PCS procedure dimension; Vlada billing-code intelligence; ZIP/county/CBSA/state crosswalk; NUCC provider taxonomy | Optional stable IDs and geography, with exact release years. Not a clinical guideline or automatic case-consistency validator. |
| Hospital/insurance transparency | 3 | Hospital standard charges; Form 5500 filings/service providers; Massachusetts commercial hospital price/cost benchmarks | A sourced hypothetical pathway-cost extension. Massachusetts benchmarks do not calibrate New Jersey hospitals. |
| Medicaid/state programs | 2 | Maryland all-payer hospital rates/volumes; Connecticut Medicaid inpatient rates | Later comparative policy/cost context; neither represents Rutgers/New Jersey operational flows. |
| Individual exchange | 1 | Individual Exchange plans/premiums | Federal-exchange coverage context subject to the guide's New Jersey exclusion. |

The dates are dataset-specific, not uniformly current. Important exceptions directly stated in the catalog:

- The Cost Plus Drugs cash-price reference is **one May 16, 2026 capture**; it is not a live price feed.
- The geography crosswalk is **2020 vintage**.
- FAERS drug involvement is listed for **2025 Q1 through 2026 Q2**.
- Hospital cost reports are listed for **FY2011-2024**; provider payment products generally lag the current year.
- Nursing-home provider information is **2026 only**, and the HVBP score is **FY2026 only**.
- Both ICD-10 code dimensions explicitly flag **FY2021-2025 as needing fixing**. Pin a verified release or use official code files if required.
- The guide lists Medicare Stars **2012-2026**, whereas the catalog lists **2007-2027**. The current account's described product and returned source/version must resolve the discrepancy before use.
- The catalog's general statement that partial products are omitted does not cancel its per-product limitations.

No blanket dataset redistribution license appears in these PDFs. Preserve the underlying source/license and sponsor access terms for any exported content; do not label every product open-source because its inputs were publicly posted. Vlada's assembled identity and billing-code products also require their own terms to be checked.

## Selected primary-source checks and what they establish

Checked online October 9, 2026. This verifies relevant source properties and limitations, not the complete Vlada catalog or the sponsor's query examples.

| Source | Verified finding | Implementation decision |
|---|---|---|
| [CMS HCAHPS overview](https://www.cms.gov/medicare/quality/initiatives/hospital-quality-initiative/hcahps-patients-perspectives-care-survey) | Standardized hospital patient-experience survey; includes physician/nurse communication and medicine/discharge information. CMS says the survey, methodology, and results are public domain. Public reporting uses four consecutive quarters, updated quarterly. | Useful cited motivation for communication objectives. Report the measurement period; do not present a hospital's historical survey score as live patient state or validation of our grading. |
| [CMS Hospital Price Transparency](https://www.cms.gov/priorities/key-initiatives/hospital-price-transparency) | Hospitals publish machine-readable standard-charge information and consumer-oriented shoppable services. | Label exact facility, service/code, payer/plan, charge type, source-file date, and professional/facility scope. A posted negotiated charge is not a guaranteed individualized out-of-pocket quote. |
| [FDA openFDA FAERS overview](https://open.fda.gov/apis/drug/event/) | Reports are not extensively validated; they cannot establish causation or incidence. Multi-drug reports do not establish which drug caused which reaction. | Do not derive synthetic disease physiology, diagnosis ground truth, or adverse-effect probability from report counts. Use a clinical reference and mentor review for case facts. |
| [NLM RxNorm files](https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html) | Full RxNorm releases require a license agreement; the current prescribable-content release is explicitly available without that license. | Avoid the assumption that every vocabulary package has identical terms. The handwritten P0 case can use approved medication names; any later structured import must record the release and relevant terms. RxNorm is distinct from the catalog's RxClass product. |
| [Synthea official license](https://github.com/synthetichealth/synthea/blob/master/LICENSE) | Synthea software is Apache-2.0. | Optional synthetic background generator, with seed/version recorded. This software license alone does not validate a teaching case or license unrelated assets/terminologies. Original mentor-reviewed cases remain faster for Sunday. |
| [PhysioNet MIMIC-IV 3.1](https://physionet.org/content/mimiciv/3.1/) | Real deidentified clinical data; restricted files require credentialing, specified training, and a signed data-use agreement. | It is not an anonymous-download substitute for synthetic cases. Do not start new patient-record access as a weekend dependency. No files were downloaded or agreements accepted. |

## RWJUH context: verified sources and limits

Initial research leads came from Pasted text.txt, supplied privately by the team. The original text is omitted from this public repository. The leads were verified against the public primary sources below; they were not instructions to build a hospital replica or contact staff.

| Research lead | Primary-source result | Decision |
|---|---|---|
| Institution and location | [RWJUH official About page](https://www.rwjbh.org/rwj-university-hospital-new-brunswick/about/) and [Rutgers hospital location](https://patientcare.rutgershealth.org/location/robert-wood-johnson-university-hospital) identify the New Brunswick hospital at 1 Robert Wood Johnson Place. Official pages identify the academic affiliation and Level I trauma/emergency setting. | Suitable context for a Rutgers-inspired teaching setting. No organizational endorsement or partnership is established by this research. |
| Campus map | [Official campus PDF](https://www.rwjbh.org/documents/rwj-new-brunswick/for-physicians/physician-relations/Hospital-Map-NB.pdf), page 2, labels building blocks, entrances, lobbies, bridges, and parking. | Orientation reference only. It is not a verified complete current architectural floor plan or an ED room inventory. |
| Partial interior map | [Official Rapid Admit PDF](https://www.rwjbh.org/documents/rwj-new-brunswick/for-physicians/physician-relations/6.5x10.5-rwj-rapid-admit_Layout-5_final.pdf), page 2, labels admitting, lobby/front desk, Tower elevators, Rapid Admit, and surgery waiting. Its text explicitly describes bypassing the ED. | This map does not describe emergency patient flow. Do not transplant Rapid Admit targets or exclusions into an ER model. The brochure's 90-minute admission goal is not measured ED service-time data. |
| Ambulatory Medical Pavilion floor directory | [Official pavilion page](https://www.rwjbh.org/our-locations/outpatient-rehab-center/ambulatory-medical-pavilion/) confirms an outpatient facility at **210 Somerset Street**, with specialty floor assignments. | A building separate from the main inpatient/ER setting. The directory does not establish inpatient department locations. |
| Doctors and provider search | The RWJUH site links a MyChart provider finder; [Rutgers location page](https://patientcare.rutgershealth.org/location/robert-wood-johnson-university-hospital) offers a provider search at that location. | Specialty/affiliation leads, not a complete active medical-staff roster. Public affiliation is not a shift assignment, room assignment, or evidence that a doctor is available for our scenario. |
| Find Your Way app | Identified as an orientation lead; no app was installed, tested, or treated as an exportable map source in this review. | Optional human orientation reference; no claim of current map fidelity or license for app-map reuse. |

The official About page now describes a **700+ bed adult hospital** and **100+ bed children's hospital**, and discusses newer campus facilities. These broad institution-level descriptions are not counts of staffed ED beds, live occupancy, or comparable capacity definitions. The exact operational capacity should remain unspecified in the hackathon app. Public map dates/current completeness were not independently established; avoid inferring that the map reflects every recent expansion. The public map PDFs were opened and their labels/content inspected; additional rendering was unavailable through direct retrieval, so no claim of complete architectural verification is made.

Copying an institutional map or a real provider's identity into the product is optional and unnecessary for the core demo. Prefer an original schematic and synthetic personnel, with the public pages cited in the research appendix.

## Concrete team work item and acceptance gate

The teammate owning clinical content/data provenance also owns this optional sponsor investigation. Timebox it to 30 minutes after the core data contract is frozen; teammates building the patient state and interface continue independently.

1. If the core is on schedule and event access is available, discover/describe **one** relevant data product. Start with HCAHPS communication measures for a named NJ facility, or a narrowly defined financial/access example if the clinician approves its educational use.
2. Query with exact geography, period, identifier, and measure/code. Request source files, method, exclusions, missingness, denominator/sample information where available, and snapshot/version. A number without those fields fails the gate.
3. Keep a small permitted result with provenance. Do not load entire catalogs, join physician identities to imaginary shifts, or send clinical records to the sponsor.
4. Clinician/faculty mentor reviews the interpretation. A communication context card explains why the objective matters; it does not assign a clinical score or claim that our app reduces readmissions.
5. Demonstrate that disabling the sponsor adapter leaves Studio → encounter → chart → evidence-linked debrief working. On busy/unauthorized/expired responses, show the explicitly dated cached card if permitted, or omit the optional card.
6. Preserve the recorded synthetic-case demo and source appendix before the **Sunday, October 11, noon ET** submission. Reconfirm provider persistence/billing outside event access for any later continuation; do not assume Monday morning access persists.

Suggested query specification, authored for the team to execute after setup: Find the hospital patient-experience source for Robert Wood Johnson University Hospital in New Brunswick. Resolve the exact CMS facility identifier; describe available physician/nurse communication measures and measurement periods. Return the selected aggregate with source file/version, method, exclusions and sample/missingness fields; say explicitly if any requested field is unavailable. No sponsor query was executed during this review.

## Review boundary

This task produced a source review and planning changes. It did not create a clinical case, activate Vlada, connect a new MCP, contact a sponsor, download patient datasets, validate an app, or establish educational effectiveness. All sponsor inventory/date claims remain attributed to the supplied PDFs unless separately verified above.
