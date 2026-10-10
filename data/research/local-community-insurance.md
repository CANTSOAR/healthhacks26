---
title: Local Community Insurance
kind: research
topics: [hospital, evidence]
---

# Local community, hospital services and insurance acquisition

Acquired 2026-10-10. This slice contains **198 records**: 178 government statistical estimates and 20 limited factual source assertions. Source bytes, metadata, hashes and normalization outputs are under `data/`. No full hospital PDF or webpage is redistributed.

## Collected datasets

| Dataset | Records | Geography / time | Evidence |
|---|---:|---|---|
| CDC PLACES place 2025 release | 80 | New Brunswick FIPS 3451210; row years 2022/2023 | 40 measures, each crude and age-adjusted estimate, confidence bounds |
| CDC PLACES county 2025 release | 80 | Middlesex FIPS 34023; row years 2022/2023 | Same measure structure |
| CDC non-medical ACS factors | 9 | New Brunswick; ACS 2017–2021 | Historical estimates with margin of error |
| CDC non-medical ACS factors | 9 | Middlesex; ACS 2017–2021 | Historical estimates with margin of error |
| RWJUH community needs assessment | 5 | Selected sections of 2025 report | Method and qualitative barriers |
| RWJBarnabas insurance directory | 6 | System directory as retrieved | Selected payer/product assertions and facility/professional distinction |
| RWJUH services/about page | 7 | New Brunswick public inventory | Services, buildings and carefully qualified capacity assertions |
| NJ staffing documentation | 2 | State report scope | Available metric types and limitations; actual hospital staffing values still pending |

Each source has a `data/catalog/local-*.json` entry and corresponding `data/normalized/local-*.jsonl`. The CDC sources also have bounded raw JSON, full dataset metadata and a retrieval receipt under `data/raw/local-*`. Metadata explicitly declares `PUBLIC_DOMAIN`. Mirror catalog descriptions sometimes disagree about release year/license: the checked-in authoritative CDC dataset metadata is used here.

## Early findings with uncertainty

These are **2023 modeled crude prevalences** from the 2025 release, percent with 95% model confidence intervals. They describe residents, not patients treated at RWJUH. Each row has a different eligible population specified by its measure definition.

| Measure | New Brunswick | Middlesex |
|---|---:|---:|
| Lack of insurance, adults 18–64 | 24.7 [22.2, 27.3] | 10.8 [8.7, 13.2] |
| Food insecurity in previous 12 months, adults | 33.9 [30.7, 37.2] | 13.7 [11.2, 16.5] |
| Unreliable transport in previous 12 months, adults | 17.3 [15.6, 19.2] | 7.0 [5.9, 8.1] |
| Frequent mental distress, adults | 20.9 [18.8, 23.0] | 13.8 [12.2, 15.7] |
| Diagnosed diabetes, adults | 11.1 [9.9, 12.3] | 11.6 [10.1, 13.1] |

Sources: [CDC New Brunswick query](https://data.cdc.gov/resource/eav7-hnsx.json?locationid=3451210&%24limit=500), [CDC Middlesex query](https://data.cdc.gov/resource/swc5-untb.json?locationid=34023&%24limit=500), [methodology](https://www.cdc.gov/places/methodology/index.html). The source field `totalpopulation` uses 2020 Census context for places and 2023 estimates for counties. It is not a universal denominator. Age-adjusted values cannot be multiplied by population to create case counts. The measures do not establish a joint distribution or policy effects.

The historical ACS slice covers age 65+, broadband, crowding, housing burden, education, poverty, minority status, single-parent households and unemployment. It does **not** cover language, detailed insurance products or income. Never present 2017–2021 values as current. Sources: [place ACS factors](https://data.cdc.gov/d/edkk-ze78), [county ACS factors](https://data.cdc.gov/d/i6u4-y3g4).

The [CHNA](https://www.rwjbh.org/documents/community-health-needs-assessment/RWJUH-CHNA-2025.pdf) contributes participant-reported barriers rather than event probabilities. Only selected executive conclusions and synthesis pages were inspected. Extracts preserve PDF and printed-page locators. A reported survey sample is not a probability sample of hospital admissions.

The [insurance directory](https://www.rwjbh.org/patients-visitors/accepted-insurances/) provides selected network assertions. They do not establish member eligibility, authorization, physician participation or current negotiated price. The [hospital about page](https://www.rwjbh.org/rwj-university-hospital-new-brunswick/about/) identifies actual capabilities; its bed and expansion language requires reconciliation before numerical capacity calibration. [NJ staffing reports](https://healthapps.nj.gov/nursestaffing/quarterly.aspx) offer a next acquisition route, with omitted professions and cross-hospital comparability limitations.

## Reproduce and extend

```sh
python3 data/scripts/acquire_local_data.py          # refresh four bounded government slices
python3 data/scripts/acquire_local_data.py --offline # rebuild from saved bytes; verify hashes
```

Online runs require dataset metadata to remain PUBLIC_DOMAIN and abort on a possibly truncated 500-row response, oversized response, unexpected geography or duplicate record IDs. Offline runs preserve original retrieval timestamps. Manually paraphrased hospital assertions need new source review to refresh; the script deliberately does not manufacture them from old summaries.

## Gaps and next acquisitions

1. Official ACS 2024 five-year API returned a `Missing Key` HTML page to an unauthenticated request; no new key was registered. Census Reporter fallback returned HTTP 403. No 2024 values were inferred. Obtain an approved Census API key or verified official bulk slice for language, disability, income, housing, transport and coverage tables; retain variable metadata and MOE.
2. Retrieve an actual RWJUH and Saint Peter's quarterly staffing report and preserve unit definitions, quarter and numerator/denominator. Current collection holds only discovery documentation.
3. Extract local NJ discharge aggregates for admissions/ED visits by diagnosis, age, payer, facility and period. Community prevalence is insufficient to parameterize hospital arrival case mix.
4. Expand payer coverage to dated plan-level benefit and authorization documents; identity, network participation, covered service and paid claim are separate assertions.
5. Resolve campus/building/bed scopes against licensed facility records and current institutional inventory. Public expansion announcements do not establish commissioned staffed capacity.

## Verification performed

Online fetches yielded nonempty NJ-only slices. All modeled confidence intervals enclose their estimates; source IDs are unique. Offline normalization was run successfully and validates source-byte hashes. All acquisition/catalog files parse as JSON, and normalized record counts match their catalog counts. No patient-level records were collected.
