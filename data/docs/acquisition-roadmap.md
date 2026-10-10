# Whole-hospital acquisition roadmap

This is the executable research backlog for the qualitative and quantitative hospital model. It covers **27 domains** and references every one of the **19 currently cataloged sources**. The current evidence is preliminary: no domain is marked complete or calibrated. The machine-readable task fields live in [acquisition-backlog.json](../workflows/acquisition-backlog.json).

## Work order

1. **Close the public evidence gaps:** strengthen ACS context, clinician taxonomy joins, NJ staffing values, all-payer case mix, terminology and one pricing/insurance slice. Preserve exact geography, payer population and time windows.
2. **Connect one complete patient journey:** define clinical/workflow prerequisites, resources, authority, disclosure, diagnostic stages and discharge barriers. Submit bounded review packets for clinical and operational review.
3. **Prepare institutional collection specifications:** request-ready aggregate dictionaries for demand, shifts, bed states, stage durations and discharge delays. Actual outreach and restricted access require separate authorization.
4. **Calibrate and validate separately:** acquire suitable conditional distributions and an untouched validation period; test conservation, operational fit, human realism, learning outcomes and fairness as separate questions.

## Domain register

Status **partial** means some evidence has been acquired but does not satisfy the full domain. **Missing** means required domain data is absent; a URL or questionnaire is not acquired local evidence. All domains remain uncalibrated.

| Domain | Priority / state | Existing sources | Next bounded collection |
|---|---|---|---|
| Geography, demographics and catchment | P0 / partial | `local-cdc-acs-middlesex-2017-2021`, `local-cdc-acs-new-brunswick-2017-2021` | Acquire one latest available ACS New Brunswick/Middlesex table bundle for age, language, insurance, disability, commuting and housing with margins of error. |
| Population health and community risks | P0 / partial | `local-cdc-places-middlesex-2025`, `local-cdc-places-new-brunswick-2025` | Review all acquired PLACES measures and extract measure definitions, uncertainty and valid comparison rules for ten relevant measures. |
| Hospitals, campuses, wings and units | P0 / partial | `cms-hospital-general-information`, `local-rwjuh-services` | Reconcile three CMS facilities to NJ licensed facilities; extract public service/unit names and historical map date for RWJUH and Saint Peter's. |
| Practitioners, specialty and affiliations | P0 / partial | `nppes-new-brunswick-practitioners`, `cms-facility-affiliations` | Look up a deterministic first 100 unique affiliated NPIs, retain minimized professional identity/taxonomy fields and report exact join coverage. |
| Staffing, shifts and skill coverage | P0 / partial | `local-nj-staffing-discovery` | Acquire one reported quarter of staffing values for the two hospitals and capture unit definitions and denominators. |
| Authority, privileges and supervision | P0 / missing | None | Draft an evidence-linked authority matrix for one ED-to-admission workflow using public policies, marking local unresolved rules for faculty review. |
| Patient demand, diagnoses and case mix | P0 / partial | `cms-inpatient-provider-service-2024` | Acquire one NJ public all-payer aggregate table with hospital/resident geography clearly stated; compare coverage against acquired Medicare DRGs. |
| Clinical pathways and procedure definitions | P0 / missing | None | Create two reviewed-pathway candidate dossiers for case families present in the acquired DRG data; separate sourced clinical rules from operational assumptions. |
| Clinical terminology and identifier crosswalks | P0 / partial | `nlm-rxnorm-seed-terms` | Extend the eight RxNorm seed concepts to medication names actually needed by two draft cases; research a small permitted lab-code set and CCN/NPI/FIPS crosswalk policy. |
| Laboratory, imaging and consult services | P0 / missing | None | Inventory public diagnostic and consult capabilities for one facility; draft event/interval dictionary for one lab and one imaging workflow. |
| Patient flow, beds, boarding and capacity | P0 / partial | `cms-timely-effective-care` | Document acquired ED measure definitions; construct an aggregate request specification for one ED-to-bed flow with admission decision, departure and bed-cleaning intervals. |
| Nursing, allied health and interpreter tasks | P1 / missing | None | Create one reviewed task-dependency inventory spanning nursing, interpreter, social work and transport for an ED journey. |
| Pharmacy, medication and formulary | P1 / partial | `nlm-rxnorm-seed-terms` | Add formulation/ingredient identity only for acquired case medications; define separate medication order, administration and inventory entities. |
| Blood, supplies, equipment and maintenance | P1 / missing | None | Create one public-service-grounded resource taxonomy and a clearly synthetic stock fixture for two procedures; inventory local data needed for calibration. |
| Insurance plans, networks and access | P0 / partial | `local-rwjbh-insurance-directory` | Acquire one current NJ plan benefit/policy bundle and record facility/professional network distinctions for a defined service. |
| Prior authorization, claims and appeals | P1 / missing | None | For the selected plan, extract one public authorization policy into prerequisites, decision states and stated time standards. |
| Charges, negotiated rates and reimbursement | P0 / partial | `cms-inpatient-provider-service-2024` | Inspect RWJUH machine-readable pricing metadata, then acquire one bounded service/payer slice after rights and size checks. |
| Hospital costs, accounting and assistance | P1 / missing | None | Acquire one HCRIS report slice per target hospital for reported capacity, cost centers and staffing where available; separately index assistance policy. |
| Discharge, post-acute partners and follow-up | P0 / partial | `cms-unplanned-visits`, `local-rwjuh-chna-2025` | Inventory ten public regional post-acute/community service entries with service scope and source date; draft discharge blocker taxonomy. |
| Patient goals, experience and communication | P0 / partial | `cms-hcahps`, `local-rwjuh-chna-2025` | Extract a bounded set of ten CHNA themes with page locators and context; map to scenario concerns and evidence-linked communication criteria. |
| Safety, complications, infection and outcomes | P0 / partial | `cms-complications-deaths`, `cms-infections`, `cms-unplanned-visits` | Review ten acquired safety/outcome definitions, populate denominators/units/adjustment applicability and suppression metadata. |
| Workflow narratives, handoffs and staff culture | P0 / missing | None | Index one public safety-culture instrument and produce a draft role-specific process-map/interview guide for the chosen patient journey. |
| Synthetic cases, learning objectives and evaluation | P0 / partial | `twinverse-patient-profiles` | Reconcile two acquired synthetic profiles against their source and create structured fact/disclosure/objective review packets; catalog rubric source separately when rights permit. |
| Disruptions, utilities, maintenance and resilience | P1 / missing | None | Build one clearly hypothetical outage/surge scenario plus a public policy inventory and explicit unknown dependencies. |
| Equity, language, disability and access validation | P0 / partial | `local-cdc-acs-new-brunswick-2017-2021`, `local-cdc-acs-middlesex-2017-2021`, `local-cdc-places-new-brunswick-2025`, `local-rwjuh-chna-2025` | Define five fairness/access evaluation questions with denominators, missing data and subgroup coverage checks using acquired context. |
| Calibration, causal assumptions and independent validation | P0 / missing | None | Draft one calibration dossier for ED-to-disposition including joint parameter needs, public benchmarks, institutional gaps and untouched validation design. |
| Provenance, rights, lineage and knowledge review | P0 / partial | All 19 cataloged sources | Audit every catalog for exact scope, rights, hashes, source references, partial status and intended-use gates; preserve upstream corrections. |

## Collection contract

Each JSON task specifies the operational question, required grain, units, time semantics, source URLs, access limits, next collection and acceptance criteria. A research worker should select one bounded task, record its exact slice, retrieve permitted evidence, normalize it without losing suppression/uncertainty, and update its catalog and review state. It should stop and record the blocker when an agreement, inaccessible source, unclear reuse rights or institutional authorization is needed.

Use `gpt-6-luna` for source discovery, extraction and review-packet drafting within these boundaries. Model-produced content is proposed interpretation until checked against source material; it cannot create observed local parameters or clinical approval. No recurring automation or unlimited collection is implied by this backlog.

## Critical interpretation boundaries

- Facility identities and public clinician affiliations do not establish wings, staffed beds, privileges, shifts or availability.
- Medicare DRGs describe a specific insured inpatient population and suppressed public cells. They do not establish all-payer demand, ED complaints or New Brunswick resident prevalence.
- PLACES estimates are modeled population measures. ACS periods, geography and uncertainty remain explicit.
- Published medians, quality ratios and survey scores are benchmarks; they are not joint service-time distributions or individual outcome probabilities.
- Patient concerns and workflow narratives need context and review. Public clinician names never provide personalities or behavior.
- Charge, allowed amount, total payment, Medicare payment, hospital cost and patient liability remain distinct.
- Actual staffing values, price-file slices, plan rules, unit topology, inventory and local stage-time distributions are still incomplete or absent.

## Source inventory

| Source ID | Acquired rows | Acquisition state |
|---|---:|---|
| [cms-complications-deaths](../catalog/cms-complications-deaths.json) | 40 | acquired |
| [cms-facility-affiliations](../catalog/cms-facility-affiliations.json) | 2142 | acquired |
| [cms-hcahps](../catalog/cms-hcahps.json) | 136 | acquired |
| [cms-hospital-general-information](../catalog/cms-hospital-general-information.json) | 3 | acquired |
| [cms-infections](../catalog/cms-infections.json) | 72 | acquired |
| [cms-inpatient-provider-service-2024](../catalog/cms-inpatient-provider-service-2024.json) | 241 | acquired |
| [cms-timely-effective-care](../catalog/cms-timely-effective-care.json) | 60 | acquired |
| [cms-unplanned-visits](../catalog/cms-unplanned-visits.json) | 28 | acquired |
| [local-cdc-acs-middlesex-2017-2021](../catalog/local-cdc-acs-middlesex-2017-2021.json) | 9 | acquired_bounded_geographic_slice |
| [local-cdc-acs-new-brunswick-2017-2021](../catalog/local-cdc-acs-new-brunswick-2017-2021.json) | 9 | acquired_bounded_geographic_slice |
| [local-cdc-places-middlesex-2025](../catalog/local-cdc-places-middlesex-2025.json) | 80 | acquired_bounded_geographic_slice |
| [local-cdc-places-new-brunswick-2025](../catalog/local-cdc-places-new-brunswick-2025.json) | 80 | acquired_bounded_geographic_slice |
| [local-nj-staffing-discovery](../catalog/local-nj-staffing-discovery.json) | 2 | acquired_selected_paraphrased_facts |
| [local-rwjbh-insurance-directory](../catalog/local-rwjbh-insurance-directory.json) | 6 | acquired_selected_paraphrased_facts |
| [local-rwjuh-chna-2025](../catalog/local-rwjuh-chna-2025.json) | 5 | acquired_selected_paraphrased_facts |
| [local-rwjuh-services](../catalog/local-rwjuh-services.json) | 7 | acquired_selected_paraphrased_facts |
| [nlm-rxnorm-seed-terms](../catalog/nlm-rxnorm-seed-terms.json) | 8 | acquired |
| [nppes-new-brunswick-practitioners](../catalog/nppes-new-brunswick-practitioners.json) | 200 | partial |
| [twinverse-patient-profiles](../catalog/twinverse-patient-profiles.json) | 8 | acquired |

Source-route research: [whole-hospital blueprint](../../research/whole-hospital-data-blueprint.md). The backlog records official discovery URLs from that research and the current catalogs; it does not claim additional downloads.
