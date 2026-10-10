---
title: Wave2 Operations
kind: research
topics: [hospital, evidence]
---

# Wave 2: New Jersey hospital operations data

Retrieved 2026-10-10 UTC using public, unauthenticated sources. These are historical/reporting inputs for research and simulation context; none describe live bed availability or a current roster.

## Acquired datasets

| Dataset | Acquired scope | Useful observations | Main limits |
|---|---|---:|---|
| [NJ general acute-care facilities](https://data.nj.gov/Health/Search-for-Hospitals-Ambulatory-Care-and-other-Acu/9aig-5kq7) | All 69 rows with `facility_type=GENERAL ACUTE CARE HOSPITAL`; retained license/location/bed-total fields only | RWJUH New Brunswick (license 11202) reports `hospbedtotal=1196`; Saint Peter’s (11205) reports `478` | State source does not define this field as staffed, open, occupied or available beds. License status/expiry must be interpreted from the state source. Contact and owner fields were excluded from the saved projection. Source license is unspecified. |
| [NJ Hospital Patient Care Staffing Quarterly Reports](https://healthapps.nj.gov/nursestaffing/quarterly.aspx) | Q2 2026, ended June 30, 2026; two named New Brunswick hospitals; 19 unit/area observations retained | 15 average patient-to-staff unit ratios and four daily staffing summaries (ED and PACU for each hospital). RWJUH ED reports 227.5 patients/day and 23.3 RNs/day; Saint Peter’s reports 172.5 patients/day and 14.9 RNs/day. The ratio tables include Med-Surg, critical care, pediatric, neonatal and postpartum areas where reported. | State DOH says these reports should not be used to compare hospitals or state averages because patient needs, policies and layout differ. They are reported quarterly averages, omit many care roles and do not give current or shift-level availability. Only selected Q2 values were retained; source page history and other report areas were not copied. Source reuse license was not established. |
| [CMS Hospital Provider Cost Report, 2023 release](https://data.cms.gov/provider-compliance/cost-reports/hospital-provider-cost-report) | CMS API records filtered to CCN 310038 and 310070; one matching report each; report periods 2023-01-01 through 2023-12-31 | RWJUH: report 826028, 3,943.46 employees-on-payroll FTE, 283.13 intern/resident FTE, 630 beds, 229,950 total bed-days available, 201,119 total days and 34,646 discharges. Saint Peter’s: report 825599, 2,692 employee FTE, 126.67 intern/resident FTE, 352 beds, 128,480 total bed-days available, 92,935 total days and 17,709 discharges. Adult/pediatric beds are separately reported as 483 and 262. | Annual retrospective provider cost reports; source values are retained as strings and empty fields remain empty. They do not measure today’s staffing or availability. The bed and FTE definitions/reporting scope differ from NJ licensure fields and must not be merged as interchangeable counts. Expenses, costs, charges, revenues and payments are distinct accounting values. |

The state inventory and CMS cost reports report materially different bed totals for the two providers. This is a scope/definition reconciliation question, not evidence that one value is current staffed capacity: keep the source and field identity attached to every value. The NJ licensing field is `hospbedtotal`; the CMS report has both `Number of Beds` and `Hospital Number of Beds For Adults & Peds`.

The staffing source’s public form returns historical report HTML even when year/quarter filters are submitted. The acquisition script selects the section explicitly headed “Staffing for Quarter Ending June 30, 2026” for each selected hospital and saves projections instead of the full multi-year page. It checks the returned hospital heading against the requested facility, and fails if the target date or expected identity is absent. Ratios and daily staffing values retain source strings. ED and PACU daily-staff counts are labeled separately from unit patient-to-staff ratios.

## CMS API and other avenues checked

The CMS API documentation identifies annual cost-report data, including CCN, fiscal period, FTE, beds, bed-days, days and discharges, but its displayed 2023 version identifier (`cb8d0018-1bbe-4559-91bf-9429ac344b48`) returned HTTP 404 from the data endpoint during acquisition. Refreshing CMS’s official [data.json catalog](https://data.cms.gov/data.json) exposed the currently published 2023 release (`f08d4c46-c0e4-4bcb-a54a-c62c87d59251`), which returned one matching API record per CCN. The catalog lists that release modified 2026-10-05 and describes its temporal coverage as calendar 2023. The live API query URLs and counts are in the dataset manifest.

NJDOH describes quarterly hospital utilization (B-2) reports and says approved/processed public submissions may be available through the Office of Health Care Financing. The official [financial-report overview](https://www.nj.gov/health/hcf/financial-reports/) lists those reports but did not expose a direct machine-readable file URL in the retrieved page, so no B-2 row values were claimed or acquired. NJDOH’s [hospital discharge data page](https://www.nj.gov/health/healthcarequality/health-care-professionals/njddcs/) describes all-payer billing/utilization submissions; it points to non-confidential data through HCUP. No HCUP microdata or restricted record-level files were acquired. The NJ staffing form did yield report values through ordinary public form submission, so no outreach or agreement was needed.

## Reproduction and evidence

Run `python3 data/scripts/acquire_ops_wave2.py` to refresh all three bounded acquisitions. Raw saved artifacts are explicit: NJ facility inventory is a field projection, NJ staffing files are selected-quarter projections, and CMS API rows retain all returned fields after JSON reserialization. SHA-256 digests and record-level provenance are in the normalized envelopes. Catalog manifests list scope, counts, rights/access notes and source limitations.

Primary documentation: [CMS cost report API documentation](https://data.cms.gov/provider-compliance/cost-reports/hospital-provider-cost-report/api-docs), [CMS cost report methodology](https://data.cms.gov/sites/default/files/2024-10/aba118b3-4f1f-45a4-8c61-b392d96b1b12/Hospital%20Provider%20Cost%20Report%20Methodology_2024_508%20Approved.pdf), and [NJ staffing-report description and cautions](https://healthapps.nj.gov/nursestaffing/quarterly.aspx).

Do not divide reported daily patient averages by daily RN/staff averages to infer a concurrent patient-to-staff ratio; these data do not provide time-aligned census and staffing observations.
