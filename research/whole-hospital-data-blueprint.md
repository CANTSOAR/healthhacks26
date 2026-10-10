# Whole-hospital data blueprint: New Brunswick and beyond

Prepared October 10, 2026. Current user direction expands the research and ontology from patient encounters to the qualitative and quantitative hospital system: real clinicians, departments/wings, procedures, insurance, local case mix and all important supporting services. This supersedes the earlier encounter-only acquisition emphasis for the research scope. It does not establish that a whole-hospital simulator has been implemented or that real institutional data is accessible.

## What the model needs to explain

A hospital model should follow patients from the surrounding community through referral/arrival, triage, diagnosis, treatment, admission/transfer and discharge/follow-up. Each stage connects clinical state, people, authority, resources, time, information, patient goals and money.

Distinguish four things: a real-world inventory; general clinical/workflow knowledge; measured local operational parameters; and synthetic scenarios. Public hospital names and real physician profiles can populate an inventory, while shifts and behavioral scenarios remain explicitly fictional until supplied and reviewed. A model based on real names is not automatically a calibrated digital twin.

Start with clear intended outputs: patient wait/boarding time, throughput, staffed capacity, utilization, cancellations, workload, cost/reimbursement, discharge delays, patient experience and evidence-linked educational feedback. Predictive physiology and actual treatment outcomes require separate models and validation.

## Data domains and research deliverables

This table specifies proposed inputs, not measurements already collected.

| Domain | Quantitative inputs | Qualitative/process inputs | Core entities |
|---|---|---|---|
| Community and catchment | Population, age, insurance, language, disability, deprivation, disease estimates, travel/access | Care barriers, trust, family support, food/housing constraints, community priorities | GeographicArea, PopulationEstimate, Catchment, SocialNeed, CommunityResource |
| Facilities, wings and units | Licensed/physical/staffed beds, rooms, distances, hours, closures | Service capabilities, admission compatibility, isolation rules, access restrictions | HealthSystem, Facility, Campus, Building, Wing, Floor, Unit, Room, Bed |
| Clinicians and workforce | Role counts, staffing ratios, shifts, workload, absences, overtime | Specialties, privileges, supervision, handoffs, escalation, skill compatibility | Clinician, StaffRole, Specialty, Credential, Privilege, Shift, Assignment |
| Patient demand and case mix | Visits by complaint/diagnosis, acuity, age, route, payer and time; admissions/referrals | Presenting concern, clinical uncertainty, preferences, knowledge, emotional state | Encounter, PresentingComplaint, Diagnosis, Acuity, Arrival, Referral |
| Clinical pathways and procedures | Procedure volumes, durations, recovery, resource needs, observed complications | Indications, prerequisites, consent, contraindications, alternatives, local protocols | CarePathway, ProcedureDefinition, ProcedureInstance, Order, Consent, Decision |
| Diagnostics and consults | Order-to-start, service and result times, queues, equipment uptime | Ordering authority, preparation, specimen routing, result acknowledgement | Test, Specimen, Lab, ImagingService, Consult, Result |
| Capacity and flow | Census, admissions/transfers/departures, occupancy, boarding, bed turnover | Bed assignment, transfer acceptance, prioritization, discharge-ready criteria | CapacityState, Queue, Admission, Transfer, Disposition, Blocker |
| Nursing and allied health | Care minutes, nurse staffing, therapy capacity, interpreter availability | Task dependencies, patient assistance, education, care coordination, supervision | CareTask, SkillRequirement, AlliedHealthService, InterpreterRequest |
| Pharmacy, blood and supplies | Stock, consumption, expiry, shortages, replenishment, turnaround | Formulary/substitution, medication reconciliation, blood compatibility, approval | Medication, InventoryItem, BloodProduct, SupplyOrder, Shortage |
| Insurance and access | Payer mix, benefit limits, authorization delays, network status, denial/appeal frequency | Coverage rules, prior authorization, referrals, financial counseling | Payer, Plan, Coverage, NetworkParticipation, Authorization, Appeal |
| Finance and revenue cycle | Charges, negotiated/allowed amounts, cost, reimbursement, patient share, bad debt | Coding, claim submission, bundled services, assistance, billing disputes | ChargeItem, RateAgreement, Claim, Payment, CostAllocation, AssistancePolicy |
| Discharge and regional partners | Placement capacity, transport delays, follow-up slots, readmissions | Caregiver readiness, home equipment, SNF/rehab acceptance, housing and goals | DischargePlan, Destination, ReferralPartner, Transport, FollowUp |
| Quality, safety and experience | Safety/infection measures, returns, survey measures, disparities | Communication, safety culture, complaints, error recovery, consent and dignity | QualityMeasure, SafetyEvent, ExperienceMeasure, Feedback, Review |
| Resilience and administration | Outages, downtime, surge demand, cancellation/backlog, staffing disruption | Command authority, downtime procedures, incident escalation, contingency rules | Disruption, Policy, ActionAuthority, ContingencyPlan, ServiceDependency |

Include hospitalists, residents, nurses, pharmacists, technicians, therapists, interpreters, social workers, case managers, environmental services, transport, schedulers and billing staff alongside attending doctors. Their constrained availability can determine whether care progresses.

## Verified primary-source routes

Sources below were inspected as documentation/pages or selected PDF sections. Linked raw datasets were not bulk downloaded or profiled in this task. Exact columns, release years, institution matching and reuse terms need verification during acquisition.

### New Brunswick and Middlesex County

1. **RWJUH / Healthier Middlesex 2025 CHNA.** The [official landing page](https://www.rwjbh.org/rwj-university-hospital-new-brunswick/about/community-health-needs-assessment/) links the [257-page report](https://www.rwjbh.org/documents/community-health-needs-assessment/RWJUH-CHNA-2025.pdf). Selected methods and contents sections were inspected, not the entire report. It combines community statistics, hospital-provided material, surveys and qualitative discussions. PDF pages 22–23 describe interviews, focus groups and survey methods; printed pages 7–8 differ from PDF indices. Extract source-specific community themes and aggregate tables with their original dates and limitations. These are community findings, not individual behavior probabilities or a full hospital event stream.
2. **NJDDCS / NJSHAD.** [NJ DOH's discharge system documentation](https://www.nj.gov/health/healthcarequality/health-care-professionals/njddcs/) identifies inpatient and ED billing-derived utilization, hospital IDs, dates, services, charges and payer type. It links a data dictionary and public aggregate query route. Detailed non-confidential records route through HCUP or Rutgers iPHD; the latter requires IRB approval according to the page. The aggregate query endpoint returned 403 in this research tool; no query results were obtained. Verify geographic filters and hospital-level availability before promising New Brunswick-specific tables.
3. **Census ACS.** The [ACS five-year API](https://www.census.gov/data/developers/data-sets/acs-5year.html) supports places, counties, census tracts and ZCTAs. Select New Brunswick and Middlesex geographies for language, age, income, housing, disability, insurance and transport context. Retain margins of error, annotation fields, denominators and reference period. Do not equate ZIP, ZCTA, municipality and hospital catchment.
4. **CDC PLACES.** [PLACES](https://www.cdc.gov/places/about/) supplies small-area health estimates. Its [methodology](https://www.cdc.gov/places/methodology/index.html) uses model-based estimation. These can inform population context; they do not measure RWJUH's actual ED complaint or admission distribution.

The target cohorts must stay separate: New Brunswick residents, Middlesex residents and patients treated at RWJUH. Regional referrals, specialty services and other hospitals mean these sets overlap without being interchangeable. Include Saint Peter's and relevant outpatient/post-acute partners in a regional inventory, then estimate catchment only from suitable referral/origin data.

### Real hospital structure and workforce

5. **NJ licensed facility directory.** [NJ acute-care facility search](https://www.nj.gov/health/healthfacilities/findhospital.shtml) provides licensed-facility identities and details. Use it to reconcile campuses and legal organizations; inspect the actual records before claiming specific bed counts.
6. **RWJUH maps and service pages.** The [public campus map](https://www.rwjbh.org/documents/rwj-new-brunswick/for-physicians/physician-relations/Hospital-Map-NB.pdf) is a historical orientation source. Current department/service pages help identify functions. A [June 2025 official opening announcement](https://www.rwjbh.org/blog/2025/june/rwjbarnabas-health-rutgers-cancer-institute-welc/) establishes the new Morris Cancer Center, illustrating why old maps need reconciliation. No complete current interior map was obtained; room capacity, secure routes and travel times need a current institutional inventory or labeled illustrative assumptions.
7. **NPPES, affiliation data and hospital directories.** [NPPES downloads](https://download.cms.gov/nppes/NPI_Files.html) give provider identities and taxonomy. [CMS facility affiliation data](https://data.cms.gov/provider-data/dataset/27ea-46a8) offers a separate affiliation source. Hospital directories can add published specialty and location context. NPI issuance does not validate licensing/credentialing; affiliation is not current privileges, call coverage or shift availability. Preserve independent source assertions and dates.
8. **Public nurse staffing.** [NJ nurse-staffing documentation](https://www.nj.gov/health/healthcarequality/health-care-professionals/nurse-to-patient-staffing/) links [quarterly reports](https://healthapps.nj.gov/nursestaffing/quarterly.aspx). Research hospital/unit coverage and reporting definitions. This is a useful historical workforce baseline, not a live roster, individual workload log or all-profession staffing schedule. No RWJUH report values were extracted here.
9. **CMS cost reports.** [HCRIS](https://www.cms.gov/data-research/statistics-trends-and-reports/cost-reports) supports historical accounting and reported capacity context. Preserve report status, fiscal period and campus/provider scope; do not translate annual aggregates into instantaneous staffed capacity.

### Procedures, insurance and economics

10. **Hospital charges and rates.** [RWJUH's charges page](https://www.rwjbh.org/rwj-university-hospital-new-brunswick/billing/charges/) links chargemaster, DRG charges and a machine-readable file. Inspect code systems, payer/plan labels, settings, bundled services and missing rates before normalization. Public standard charges are not actual patient bills or resource costs. Keep facility and professional components separate.
11. **Coverage and networks.** [RWJBH accepted-insurance information](https://www.rwjbh.org/patients-visitors/accepted-insurances/) distinguishes facility participation from physician participation. Combine dated plan-specific network records, summary-of-benefits/coverage documents, formularies and insurer authorization policies. [GetCoveredNJ](https://www.nj.gov/getcoverednj/help/about/publicinfo.shtml) is the NJ marketplace source; federal-exchange products alone cannot fill NJ coverage. Patient deductible accumulators, current eligibility and actual authorization timelines are not established by public plan documents.
12. **Payer rate files.** [CMS public-data guidance](https://www.cms.gov/initiatives/healthplan-price-transparency/overview/public-data) provides a route to insurer machine-readable pricing information. Begin with one provider/plan/service slice rather than every national file. Published rates do not show utilization, claim outcomes or guaranteed coverage of a scenario.
13. **Procedure/case classification.** [CMS MS-DRG documentation](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/ms-drg-classifications-and-software) informs diagnosis/procedure grouping. Distinguish clinical procedure definitions, billing codes and bundled payment groups. [AMA CPT licensing guidance](https://www.ama-assn.org/amaone/cpt-current-procedural-terminology) requires permission/license for CPT content. Version and scope terminology rights before KB redistribution or AI use; a code in a public price file does not establish broad rights to the codebook.
14. **Case-mix benchmarks.** [HCUP query tools](https://hcup-us.ahrq.gov/dataquerytools.jsp) provide hospital-care statistics; NJ detailed availability and access depend on dataset/year. [MIMIC-IV](https://physionet.org/content/mimiciv/3.1/) is a credentialed clinical trajectory source. It can inform schema/method research under its terms, but its population does not calibrate New Brunswick. Neither discharge diagnosis nor DRG automatically provides the presenting complaint or exact triage state.

### Quality and qualitative realism

15. **Measured experience and safety.** [CMS HCAHPS](https://www.cms.gov/data-research/research/consumer-assessment-healthcare-providers-systems/hospital-cahps-hcahps) covers patient experience; the [hospital data catalog](https://data.cms.gov/provider-data/topics/hospitals) provides quality datasets. [NJ hospital performance reports](https://www.nj.gov/health/healthcarequality/health-care-professionals/hospital-performance-report/) offer hospital safety/infection/quality summaries. Retain populations, periods, adjustments, suppression and metric definitions. Survey scores and standardized infection ratios are not raw per-event probabilities.
16. **Staff perspectives and process research.** [AHRQ SOPS](https://www.ahrq.gov/sops/index.html) supplies safety-culture instruments. Combine published community themes with consented clinician/staff/patient interviews, process mapping, validated survey instruments and authorized observation. A public survey framework is not RWJUH's actual culture score. Public patient stories are selected accounts, not representative behavioral data.

## Acquiring qualitative knowledge

Acquire process maps, decision rules, role responsibilities, common exceptions, handoff conventions and patient goals alongside numbers. Interview multiple roles to distinguish written policy from actual practice. Start with published CHNA themes and official workflow materials; later collect original interviews through an agreed research process. No interviews or external messages were performed here.

Represent a qualitative finding as Theme/Rule/Decision/Exception + Source + Context + Population + Date + Review + uncertainty. Preserve disagreement instead of collapsing conflicting perspectives. Convert reviewed findings into scenario triggers and observable behaviors; do not infer personalities from names, demographic groups or professional specialties.

An interpreter delay can require a scheduler decision and change queue state. A caregiver's availability can affect discharge planning and transport. A specialist's supervision/privileges can constrain who performs a procedure. These are proposed modeled interactions; estimate timing and likelihood only from suitable evidence or explicit assumptions.

## Quantitative acquisition: collect relationships, not disconnected averages

For local calibration, first request a process dictionary and aggregates, including counts and conditional distributions. Suggested breakdowns: hour/day, arrival route, acuity, service line, destination, broad age/payer groups and disruption state, subject to adequate cell sizes. Preserve dependence between acuity, resources, duration and disposition.

Ask for distinct stage intervals: arrival→triage; triage→clinician; order→start; service duration; completion→result; consult request→response; admission decision→ED departure; discharge ready→actual departure; bed vacated→clean/available. A single length-of-stay mean cannot recover these mechanisms. Capture unfinished waits/censoring and order cancellations.

Minimal event contract: encounter/resource ID, event type, event time, recorded time, origin/destination, state before/after, order/procedure reference, responsible role, exception reason, source/version and uncertainty. Request restricted event extracts only if aggregates cannot answer the stated model question and an approved processing/access arrangement exists.

Independent validation needs observed census/flow snapshots and an untouched period with demand, staffing and disruption context. Avoid fitting and validating on the same sample. Historical relationships do not establish causal effects of a new staffing policy.

## Expanded ontology and evidence model

Inventory graph: HealthSystem → Facility → Campus/Building → Wing/Floor → Unit → Room → Bed. Clinical and operational units may span multiple physical locations; model their relationship explicitly rather than forcing one hierarchy.

People graph: Clinician/StaffRole → Specialty/Skill → Credential/Privilege → Shift → Assignment. Keep public real identities separate from synthetic behavioral personas.

Care graph: Patient/Population → Encounter → PresentingComplaint/Diagnosis → CarePathway → Order/Procedure → ResourceAllocation → Event → Outcome/Disposition.

Finance graph: Encounter/Procedure → Claim/ChargeItem → Payer/Plan/Coverage → NetworkParticipation/Authorization → AllowedAmount/Payment/PatientLiability.

Community graph: GeographicArea/Catchment → PopulationEstimate/AccessBarrier → CommunityResource/ReferralPartner → FollowUp/DischargePlan.

Every claim/parameter needs source ID/version/locator, acquisition state, valid time, institution/geography, population/denominator, units, transformation, uncertainty and review. Separate evidence kinds: observed local data, published local aggregate, published external benchmark, reviewed policy, synthetic example and assumption. Also record whether an input is usable for identity, teaching, calibration or validation. "Acquired" alone is not a sufficiency test.

Identifiers require versioned crosswalks: NPI, CMS certification number, NJ facility license, payer/plan ID, code-system version, geographic FIPS and local unit/resource IDs. Name-only joins are insufficient. Record parent/campus distinctions, ambiguous matches and date-bounded affiliations.

## Coupled simulation architecture

- Numerical/event engine: arrivals, queues, schedules, eligibility, capacity, inventory, service times and costs.
- Clinical scenario engine: reviewed patient facts, permitted actions, scripted or separately validated clinical transitions.
- Human/workflow engine: beliefs/goals, conversations, authority, handoffs, negotiation, exceptions and policy decisions.
- Shared event log: all proposed decisions become structured actions with prerequisites and effects; conversation cannot silently create a bed, test result or insurance approval.

Maintain patient/resource conservation, exclusive assignments, eligibility, causal time ordering and cost-component consistency. Describe supported effects, uncertainty and scope separately from visual realism. A hospital map can render the same unit/resource IDs without pretending to supply missing state.

## Acquisition sequence and readiness

1. **Public local evidence pack:** facility/service inventory, selected provider/affiliation records, CHNA themes, NJSHAD/HCUP aggregate availability, staffing report definitions, selected HCAHPS/quality metrics, one RWJUH price-file slice and one NJ plan policy bundle.
2. **Local case-mix dossier:** distinguish residents versus hospital encounters; extract suitable counts by setting, diagnoses/procedures, payer and disposition with period/population/missingness. Leave unsupported strata unknown.
3. **Qualitative process dossier:** reviewed pathways, role authority, exceptions, handoffs, discharge barriers and patient priorities. Track unresolved interviews/observations.
4. **Synthetic regional model:** instantiate a functional topology and joint assumptions with visible parameter ranges; test conservation, replay and sensitivity. Label it a training/research model until calibrated.
5. **Institutional calibration pack:** process dictionary, aggregate conditional durations/demand, unit capacity/staffing and independent observations; seek approved event data only for specific remaining questions.
6. **Validation dossier:** technical invariants, local operational fit/holdout, human realism and educational outcomes are separate evaluations. An accurate historical volume total does not validate queues or treatment outcomes.

Each source acquisition task should record requested fields, exact scope, intended model use, access/rights, preprocessing, review owner and acceptance criteria. Start with complete patient journeys rather than collecting disconnected sources indefinitely. A proposed first linked journey is ED→diagnostics/consult→admission or discharge→follow-up, including interpreter, resource and insurance context. Select case families from actual acquired local evidence; no local frequency ranking was calculated here.

## Delivery state

This task verified source routes and expanded the research/ontology scope. It did not acquire a complete real physician roster, full wing inventory, detailed NJDDCS records, patient insurance data, service-time dataset, institution-specific behavior model or validated simulator. No external requests, agreement acceptance or restricted-data processing occurred. The source catalog is a research inventory; later acquisition must inspect actual files and permissions.
