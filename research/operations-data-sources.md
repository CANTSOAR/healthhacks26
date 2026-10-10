# Operations data sources actually obtained (data workstream, 2026-10-10)

Scope: the public datasets behind `catalog/` values. For each: what it really contains, URL, access date, data year, terms,
what was extracted, caveats. Scripts are in `data/fetch/`, extracts in `data/processed/`. All access dates are 2026-10-10.
Nothing here is the hospital's own operational data.

## 1. CDC/NCHS NHAMCS Emergency Department public-use microdata — obtained

- URL: https://ftp.cdc.gov/pub/Health_Statistics/NCHS/dataset_documentation/nhamcs/stata/ (Stata files `ed<year>-stata.zip`);
  documentation https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHAMCS/doc22-ed-508.pdf
- What it is: a national probability sample of ED visits. One record per sampled visit, about 910 variables, anonymous
  hospitals. Latest file on the server: 2022 (posted July 2024). No 2023+ file exists there.
- Years and rows used: 2019 (19,481 visits, 210 hospitals), 2021 (16,207; 186), 2022 (16,025; 188) pooled = 51,713 visits
  for everything except the month profile; 2020 left out as a pandemic outlier. Month profile also read 2014-2018.
- Terms: public-use file; NCHS data use restrictions (statistical reporting only, no re-identification, no linkage to
  identifiable data). Only weighted aggregates are kept in the repo.
- Weights: `PATWT` on every estimate. No standard errors were computed; unweighted cell sizes are in the extracts.
- Subsets: `all_hospitals`, and `metro_teaching` = `MSA==1 & EMEDRES==1` (metropolitan hospital with an emergency medicine
  residency; 19,992 visits). Catalog rule: metro_teaching when the cell has at least 100 sampled visits, else all hospitals;
  hour and weekday profiles use all hospitals.
- Extracted: arrival hour (`ARRTIME`) and weekday (`VDAYR`) profiles; triage mix (`IMMEDR`); condition mix (`RFV13D`);
  arrival mode (`ARREMS`, `AMBTRANSFER`); age (`AGE`); payer (`PAYTYPER`); per triage level: imaging, X-ray, CT, MRI,
  ultrasound, lab, admission, ICU share of admissions, LWBS, wait to provider (`WAITTIME`), length of visit (`LOV`),
  boarding (`BOARDED`); inpatient stay of ED admissions (`LOS`); a regression that separates test-attributable time.
- Caveats that matter:
  - **Triage level is not imputed and is missing for about 31% of weighted visits** (unknown, blank, "no triage", or an ED
    without nursing triage). The acuity mix is among visits with a level 1-5; the rest are assumed to have the same mix.
  - NHAMCS rescales 3- and 4-level triage scales to five levels, so "level 1" is not a clean ESI 1: its admission share is
    0.40 (teaching) / 0.29 (all), far below single-site ESI 1 figures, and its ambulance share is 0.57.
  - Level 5 is not lower than level 4 for admission (0.056 vs 0.020) or ambulance share: a small, mixed cell (516 visits).
  - **The month profile is unusable.** Each hospital reports one 4-week period; the 8-year pooled estimate has a
    between-year SD of 0.13-0.41 per month. `arrival_month_profile` therefore stays assumed.
  - `treatment_min` is model-derived: weighted least squares of (LOV - WAITTIME - BOARDED) on level dummies and X-ray, CT,
    MRI, ultrasound, lab, admission indicators (R2 0.17, outcome winsorized at the 99th percentile). The level coefficient
    is "minutes after first provider contact with no tests"; it still contains re-evaluation and discharge processing.
  - "Lab" = any of 22 blood/urine/culture/toxicology items; rapid flu/COVID/pregnancy/HIV tests are not counted.
- Condition mapping (ours, on the 4-digit Reason for Visit code; first match wins; ranges checked against appendix II of
  the 2022 documentation):

  | condition_group | RVC codes |
  |---|---|
  | mental_health_substance | 1100-1199, 2300-2349, 5818-5829, 5910-5916 |
  | chest_pain | 1050, 1260-1274 |
  | respiratory | 1400-1499, 2600-2649 |
  | abdominal_pain | 1500-1639, 2650-2699 |
  | neuro | 1200-1259, 2350-2399, 1030, 5840-5842 |
  | infection_fever | 1005-1012, 2001-2099, 5935 |
  | injury_trauma | 5001-5817, 5830 |
  | musculoskeletal | 1900-1999, 2900-2949 |
  | other_medical | everything else, including blank |

## 2. CMS Care Compare, "Timely and Effective Care - Hospital" and "Hospital General Information" — obtained

- URLs: https://data.cms.gov/provider-data/dataset/yv7e-xc69 and https://data.cms.gov/provider-data/dataset/xubh-q36u
  (CSV URL resolved through the Provider Data Catalog metastore API). Release 2026-08-13. US government work, public.
- Hospital: Facility ID (CCN) **310038**, "ROBERT WOOD JOHNSON UNIVERSITY HOSPITAL", ONE ROBERT WOOD JOHNSON PLACE, NEW
  BRUNSWICK, NJ 08901 — matched on name and city, address checked. (310024 Rahway, 310048 Somerset, 310110 Hamilton are
  different hospitals.)
- Values: OP-18b 206 minutes (408 sampled visits, Oct 2024-Sep 2025); OP-18c 156 minutes (21 visits); OP-22 1% of 81,126
  ED visits (calendar 2024); ED volume category "very high".
- Peer groups computed from the hospital-level file (4,081 hospitals with OP-18b): very high volume n=702, median 192.5,
  10th-90th percentile 133-269; OP-22 median 2%, 1-5%. NJ very-high-volume hospitals n=24: 194.5, 143-224.
- Caveats: OP-18b covers discharged patients only (no admitted, transferred or psychiatric patients) and is a sample.
  OP-22 is a whole-number percent. The 81,126 denominator is lower than the hospital's "more than 95,000 emergency and
  trauma patients a year"; `patient.shared.arrivals_per_day` now uses 81,126/366 = 222 with 260 as the top of its range.

## 3. CMS Provider of Services file, Hospital Provider Cost Report, raw HCRIS — obtained

- POS (QIES, hospitals and other facilities, 2026 Q2): https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/provider-of-services-file-quality-improvement-and-evaluation-system
  — one row by API filter `PRVDR_NUM=310038`. Contains certified beds (610), operating rooms (30), cath rooms (8), service
  flags, hospital-wide FTE by profession. It has **no bed counts by unit type** and nothing ED-specific.
- Hospital Provider Cost Report (CMS's summary of HCRIS): https://data.cms.gov/provider-compliance/cost-report/hospital-provider-cost-report
  — FY2023 and FY2024 rows for the CCN.
- Raw HCRIS form CMS-2552-10: https://downloads.cms.gov/FILES/HCRIS/HOSP10FY2024.ZIP (135 MB; file dated 2026-10-05).
  Report 811005, fiscal year 2024-01-01 to 2024-12-31, status code 1 (as submitted), 6,934 numeric cells for this hospital.
- Extracted: Worksheet S-3 Part I beds/days/discharges by unit (625 beds: 487 adults & pediatrics, 16 ICU, 14 coronary
  care, 51 surgical ICU, 37 neonatal ICU, 20 pediatric ICU; 211,651 days; 36,561 discharges; occupancy 0.925; mean stay
  5.79 days); Worksheets A / B Part I / C Part I by cost centre (Emergency: direct 32.4M, after overhead 70.2M, charges
  842.6M; adults & pediatrics 305.5M; adult ICUs 88.1M; operating room 74.6M; CT 6.4M; laboratory 88.5M); G-3.
- Derived: ED cost per visit 865 usd; routine cost per patient-day 1,783; ICU 3,503; fixed cost per hour for ward unit
  (24 beds) 1,713.7, ICU bed 123.8, operating room 283.1.
- Caveats: "beds" are beds available on the cost report, not the state licence. The report is as-submitted, not audited.
  It covers the whole CMS number, including the children's hospital. Cost-centre totals include that unit's staff
  salaries, so ward/ICU/OR fixed costs are fully loaded. **ED space fixed costs remain `assumed`**: the annual ED overhead
  (37.8M) is measured but its split across space types uses the Wave 0 relative weights.

## 4. BLS OEWS wages — obtained through the API; bulk files blocked

- https://www.bls.gov/oes/ — the bulk zips (`oesm25st.zip`, `oesm25ma.zip`) and `download.bls.gov` return **HTTP 403** to
  scripted clients from both machines. The BLS public API v1 (https://api.bls.gov/publicAPI/v1/timeseries/data/, no key,
  25 queries/day) works: 88 series, May 2025 estimates, New Jersey statewide and New York-Newark-Jersey City metro, all
  industries. Catalog values use New Jersey statewide; the metro value is in each note.
- Role -> SOC mapping (ours): attending 29-1214 (median 151.60; the mean 126.00 is pulled down by a 25th percentile of
  38.18, apparently trainees); app = mean of 29-1171 and 29-1071; rn 29-1141; charge_rn = RN 75th percentile (no code
  exists); tech = mean of 29-2042 and 31-1131; registration 43-4111; pharmacist 29-1051; imaging_tech 29-2034; transport
  31-1132; evs 37-2011. Residents have no usable OEWS code: `resident.wage_per_hour` stays assumed.
- Caveats: all industries and all settings, not hospital- or ED-specific; base wage without benefits or differentials.

## 5. BLS CPS absences (Table 47) — transcribed, not downloaded

- https://www.bls.gov/cps/cpsaat47.htm, annual averages 2025 (11 months; October not collected). 403 to scripts; read twice
  through a fetch tool with identical figures and typed into `data/processed/bls_cps_absences_table47_2025.json`.
  Healthcare practitioners and technical occupations: absence rate 3.7%, lost worktime rate 2.1%; healthcare support 4.1%
  and 2.2%. `staff.shared.absence_rate` = 0.021, tagged `literature`. **Re-verify in a browser.**

## 6. CMS IPPS FY2027 and OPPS July 2026 — obtained

- IPPS: https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/fy-2027-ipps-final-rule-home-page
  — Table 5 (768 MS-DRGs: weight, geometric and arithmetic mean stay), Tables 1A-1E (standardized amounts 4,519.68 labor +
  2,328.32 nonlabor, capital 539.95), Impact File row for 310038 (wage index 1.2727, teaching factor 0.18135, DSH 0.04234,
  case-mix index 2.461, uncompensated-care amount 1,847.02 per claim). Correction-notice sheets used.
- `inpatient_revenue` = 28,045 usd = (operating 9,888 + capital 757) x case-mix 2.461 + 1,847. **Base-rate assumption:** an
  ED admission is paid at the hospital's all-case Medicare case-mix index; this overstates ordinary medical admissions.
  A weight of 1.0 gives 12,492 (lower end of `range`). Outliers and quality adjustments ignored. Table 5 has no case
  counts, so no volume-weighted mean stay could be taken from it; `inpatient_los_days` uses NHAMCS instead.
- OPPS Addendum B: https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient/addendum-a-b-updates
  (`july-2026-opps-addendum-b.zip`). National unadjusted rates, wage-adjusted as rate x (0.6 x 1.2727 + 0.4) = x1.1636.
  The file's descriptor column is AMA CPT text and is not copied into the repo (codes, APCs and rates only).
- **ESI -> visit level is an assumption:** level 1 -> 99291 (APC 5041, 982.00), 2 -> 99285 (707.98), 3 -> 99284 (496.05),
  4 -> 99283 (324.52), 5 -> 99282 (182.54). Imaging: CT 232.01 (unweighted mean of 10 codes, 124-415), X-ray 103.46,
  ultrasound 124.29, MRI 283.66. Status Q1 services (most X-rays) are packaged when billed with an ED visit, so these are
  stand-alone rates and upper bounds. Facility payment only; no professional fees.

## 7. CDC ILINet (FluView) — obtained through a mirror

- CDC's download endpoint `gis.cdc.gov/grasp/flu2/PostPhase02DataDownload` returned 404. Series taken from the Delphi
  Epidata API (Carnegie Mellon), which mirrors ILINet: https://api.delphi.cmu.edu/epidata/fluview/ — national and HHS
  Region 2 (NJ, NY, PR, VI), MMWR weeks 2014-40 to 2026-39.
- Nine seasons used (2014-15 to 2018-19, 2022-23 to 2025-26); 2019-20 to 2021-22 excluded. HHS Region 2: wave width at
  half height median 63 days (28-112); mean excess ILI share during the wave 0.041 (0.026-0.100); peak 4.4x baseline.
- Caveat: ILINet is the ILI share of outpatient-provider visits, a proxy for the respiratory share of ED arrivals. It says
  nothing about total ED volume, so `flu_wave.arrival_multiplier` and `staff_absence_multiplier` stay assumed.

## Not obtained

- BLS OEWS bulk files and CPS HTML by script (403) — worked around as above.
- CDC FluView direct download (404) — mirror used.
- NHAMCS beyond 2022: not published on the server.
- Hospital-specific hourly arrivals, rosters, ED room counts by zone, equipment counts, downtime: not in any of these sources.
- Vlada: never called (no credential tonight).
