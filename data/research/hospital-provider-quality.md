---
title: Hospital Provider Quality
kind: research
topics: [hospital, evidence]
---

# New Brunswick hospital, practitioner, quality and case-mix acquisition

Acquired 2026-10-10 through official CMS and NPPES APIs. The checked-in raw snapshots and normalized records are actual source observations. They have **not** received clinical or operational review and do not establish a calibrated simulation.

## Acquired scope

| Dataset / catalog | Rows | Scope and join |
|---|---:|---|
| [Facility inventory](../catalog/cms-hospital-general-information.json) | 3 | All New Brunswick, NJ rows in CMS general hospital information |
| [HCAHPS](../catalog/cms-hcahps.json) | 136 | Published patient-experience measure rows for two CCNs |
| [Timely and effective care](../catalog/cms-timely-effective-care.json) | 60 | Published process/ED measure rows for two CCNs |
| [Complications and deaths](../catalog/cms-complications-deaths.json) | 40 | Published measure rows for two CCNs |
| [Healthcare-associated infections](../catalog/cms-infections.json) | 72 | Published measure rows for two CCNs |
| [Unplanned visits](../catalog/cms-unplanned-visits.json) | 28 | Published measure rows for two CCNs |
| [Facility affiliations](../catalog/cms-facility-affiliations.json) | 2,142 | 1,485 RWJUH and 657 Saint Peter's rows; 1,911 distinct NPIs across both |
| [NPPES individuals](../catalog/nppes-new-brunswick-practitioners.json) | 200 | First API page of New Brunswick NPI-1 city-search results, incomplete sample |
| [2024 Medicare provider/service](../catalog/cms-inpatient-provider-service-2024.json) | 241 | 186 RWJUH and 55 Saint Peter's released DRG rows |
| **Total** | **2,922** | Rows across different observation types; not distinct people or patients |

The two main facility identifiers are `310038` (Robert Wood Johnson University Hospital) and `310070` (Saint Peter's University Hospital). The facility inventory also includes `313300` (Children's Specialized Hospital); its quality/affiliation records are outside this initial acquisition scope. Preserve CCNs and NPIs as strings.

## What these observations enable

The records support facility identity, public practitioner affiliation relationships, baseline quality measures, reported patient experience, and a first historically grounded Medicare case-mix inventory. They support research about case families and benchmark selection before simulation parameters are approved.

Examples directly inspectable in the snapshots:

- CMS measure `OP_18b` reports ED median duration of **206 minutes for RWJUH** and **208 for Saint Peter's**, for **2024-10-01 through 2025-09-30**, with source samples 408 and 409. The source definition excludes transfers and psychiatric/mental-health patients. This is a reported aggregate duration, not an arrival distribution, service-time distribution, live wait estimate or boarding measure. [Local data](../normalized/cms-timely-effective-care.jsonl), [official dataset](https://data.cms.gov/provider-data/dataset/yv7e-xc69).
- HCAHPS `H_COMP_2_A_P` reports **77% / 76%** saying doctors always communicated well at RWJUH/Saint Peter's for that same period. Completed surveys are 2,393 / 339 and response rates 17% / 15%; these are survey-level counts repeated on measure rows and must not be summed across questions. This is a useful quantitative anchor for communication experience, not a transcript corpus or behavioral model of real clinicians. [Local data](../normalized/cms-hcahps.jsonl), [official dataset](https://data.cms.gov/provider-data/dataset/dgck-syfz).
- The 2024 DRG rows sum to **6,402 RWJUH** and **1,397 Saint Peter's** published discharges. The largest released DRG at both is `871`, septicemia or severe sepsis without prolonged mechanical ventilation, with major complication/comorbidity: **588 / 164** discharges. DRG `291`, heart failure and shock with major complication/comorbidity, has **278 / 121**. These are Original Medicare fee-for-service Part A IPPS records and exclude suppressed provider/DRG cells with ten or fewer discharges. They are **not** total hospital encounters, all-payer volumes, ED complaint frequencies, local resident prevalence, or total sepsis incidence. [Local data](../normalized/cms-inpatient-provider-service-2024.jsonl), [official scope and suppression documentation](https://data.cms.gov/provider-summary-by-type-of-service/medicare-inpatient-hospitals/medicare-inpatient-hospitals-by-provider-and-service).

## Ontology mapping and usage limits

| Source concept | Suggested entity/relation | Keep distinct |
|---|---|---|
| CCN + facility identity | Facility with Identifier | Facility, organization, campus, wing and physical bed |
| NPI identity/taxonomy | Practitioner with Identifier and Specialty assertion | Registry taxonomy, verified specialty, license and competence |
| NPI → CCN affiliation | PractitionerAffiliation assertion | Affiliation, employment, privileges, scheduled shift and availability |
| HCAHPS response | QualityMeasureObservation with MeasureDefinition | Respondents, questions, response percentages, adjusted ratings and firsthand narratives |
| ED/process score | QualityMeasureObservation with reporting period | Median duration, queue delay, service duration and distribution |
| CCN + year + DRG | UtilizationObservation | DRG grouping, diagnosis, procedure, pathway and clinical indication |
| Charge/payment fields | FinancialObservation | Submitted charge, total payment, Medicare payment, hospital cost and patient share |

Each normalized record includes its source URL, retrieval time, SHA-256 of the saved source snapshot and source record key. Original numeric strings, missing markers, footnotes and periods remain intact. Unit/measure-definition review is required before conversion to numeric simulation parameters. An aggregate outcome that is risk-adjusted must retain its population, denominator and adjustment method; it cannot be interpreted as an individual patient's event probability.

## Reproduction and snapshot boundaries

```sh
python3 data/scripts/acquire_hospital_data.py
python3 data/scripts/acquire_hospital_data.py --only cms-inpatient-provider-service-2024
```

The standard-library script uses bounded timeouts, retries and pagination, validates facility filters, and writes dataset catalogs even for acquisition failures. The current acquisition succeeded for every source; NPPES is intentionally recorded as partial because only 200 search results were requested. Re-running overwrites snapshots in place; commit the existing version before a refresh to retain history. CMS provider-data resources are current-publication endpoints; the DRG API uses a pinned 2024 resource UUID discovered in the official CMS catalog rather than its moving `latest` endpoint. Each catalog records publication metadata and the exact scope.

CMS provider-data raw files preserve response bytes. NPPES differs deliberately: its saved raw file is a **documented professional-field projection**, not a verbatim API response. Mailing addresses, street addresses, telephone/fax, personal demographic fields, license numbers and alternate identifiers are removed before persistence. Hashes authenticate the saved projection. Some registry practice addresses can be residential, which is unnecessary detail for this inventory. The NPPES city-search sample is not guaranteed to match the affiliated clinician list; join only on explicit NPI values, never inferred name matches.

## Remaining acquisitions

1. Expand NPPES by explicit affiliated NPIs with cache/rate limits, preserving professional-field minimization. Do not interpret registry status as credential verification.
2. Inspect CMS HCRIS hospital cost reports for reported beds, staffing/cost components and fiscal-year alignment. No HCRIS records were acquired in this pass.
3. Acquire NJ public all-payer discharge aggregates with explicit hospital-versus-resident geography, period and suppression metadata. They are needed to complement the Medicare-only DRG view.
4. Obtain reviewed local unit inventories, staffing patterns, patient-flow transitions and conditional duration distributions. The present snapshots do not expose live beds, shifts, wings, service-time distributions or care-team behavior.
5. Review each measure's dictionary and applicability before creating simulation parameter distributions, case sampling weights or outcome rules.

Additional source documentation: [CMS facility affiliations](https://data.cms.gov/provider-data/dataset/27ea-46a8), [CMS patient-experience methodology](https://data.cms.gov/provider-data/topics/hospitals/hcahps/), [CMS unplanned visit methods and risk adjustment](https://data.cms.gov/provider-data/topics/hospitals/unplanned-hospital-visits), [NPI API](https://npiregistry.cms.hhs.gov/api-page), [CMS machine-readable catalog](https://data.cms.gov/data.json).
