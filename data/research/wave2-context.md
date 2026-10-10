---
title: Wave 2 community context acquisition
kind: research
topics: [hospital, evidence, community]
---

# Wave 2 community context acquisition

Acquired 2026-10-10 from the CDC/ATSDR SVI 2022 ArcGIS service: **193 area records** for Middlesex County, New Jersey (one county record and 192 census tracts). Also acquired **175 CMS Medicare enrollment aggregates** for Middlesex County, spanning annual rows 2013–2025 and monthly rows January 2013–June 2026. Original JSON responses, service metadata, retrieval receipts, SHA-256 hashes, and normalized source-record envelopes are retained under `data/raw/w2-context-svi2022-middlesex-*`, `data/catalog/`, and `data/normalized/`. The county and tract layers are separate catalog datasets because they have different geographic units. Geometry was not requested or retained.

## What the records represent

SVI provides area-level social vulnerability metrics; its 2022 data use ACS 2018-2022 estimates. The U.S. county layer reports a population estimate (`E_TOTPOP`) of 860,147, overall percentile ranking (`RPL_THEMES`) 0.6647, and theme percentile rankings (`RPL_THEME1`–`RPL_THEME4`) of 0.4960, 0.2361, 0.9201, and 0.9198. The population value is copied directly from the county row; it was not calculated by summing the tract records. These values are U.S.-database rankings: the source documentation says the U.S. database ranks areas against one another nationally. State-specific rankings can differ. They are relative rankings, not probability or patient-level risk. Across 192 Middlesex tracts, the source returns population estimate and margin-of-error fields, social vulnerability estimates, flags, and overall/theme rankings. Use the per-tract source attributes for detail; source values of `-999` are preserved as supplied; CDC documentation defines `-999` as unavailable in the source or not calculable due to unavailable Census data. The retained SVI responses contain 95 such numeric sentinel fields across the tract slice, and zero JSON nulls. No values were imputed or rewritten as null.

This information can support community-context exploration. It does not describe RWJUH admissions, actual service access, payer enrollment, an individual patient's characteristics, or causal effects. The 2018-2022 ACS reference period should remain explicit in any downstream use. Do not use the county and tract rows as separate populations to sum; the county value aggregates tract geography.

## Acquisition details and sources

- [CDC/ATSDR SVI data and documentation download page](https://atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html)
- [SVI 2022 documentation](https://atsdr.cdc.gov/place-health/media/pdfs/2025/01/SVI2022Documentation.pdf)
- [CDC ArcGIS FeatureServer, layer list](https://onemap.cdc.gov/onemapservices/rest/services/SVI/CDC_ATSDR_Social_Vulnerability_Index_2022_USA/FeatureServer?f=pjson)
- [County layer (layer 1)](https://onemap.cdc.gov/onemapservices/rest/services/SVI/CDC_ATSDR_Social_Vulnerability_Index_2022_USA/FeatureServer/1)
- [Tract layer (layer 2)](https://onemap.cdc.gov/onemapservices/rest/services/SVI/CDC_ATSDR_Social_Vulnerability_Index_2022_USA/FeatureServer/2)

The query was restricted to `STCNTY='34023'` and returned source attributes without geometry. Both responses were nonempty; the tract slice has 192 unique 11-digit FIPS identifiers, all beginning `34023`, and all records were checked for NJ and Middlesex county codes. The county slice has one row with county FIPS `34023`. Attribution is retained as CDC/ATSDR GRASP. The service metadata identifies CDC/ATSDR GRASP as the source. CDC policy says most agency website information is public domain unless otherwise noted; the catalog records that source basis, preserves attribution, and retains the service copyright text. [CDC use of agency materials](https://www.cdc.gov/other/agencymaterials.html).

## Additional attempt and remaining gap

An official Census Bureau ACS 2023 five-year API request for Middlesex County census-tract language and health-insurance totals returned the Census API's `Missing Key` HTML response. No ACS row was acquired, retained, normalized, or inferred. The blocked attempt is recorded under `data/research/access-attempts/w2-context-acs2023-language-insurance-middlesex.json` with zero records; unsuccessful requests do not appear in the acquired-dataset catalog. The Census Bureau describes the ACS API and 2023 five-year data on its [official API data page](https://www.census.gov/data/developers/data-sets/acs-5year/2023.html). An authorized API key or an official key-free bulk endpoint is needed to retry; no key was requested or registered.

This wave adds three acquired quantitative datasets with 368 records total: 193 SVI area records and 175 CMS enrollment aggregates. The Census API attempt did not acquire direct ACS table rows for detailed language or insurance characteristics. SVI does contain area-level language and insurance-related indicators among its inputs, but those are not a substitute for the requested direct ACS table observations. Public leads or source URLs alone are not treated as acquired data.


## CMS Medicare enrollment aggregate

The [CMS Medicare Monthly Enrollment dataset](https://data.cms.gov/summary-statistics-on-beneficiary-enrollment/medicare-and-medicaid-reports/medicare-monthly-enrollment) was queried through its official [CMS Data API](https://data.cms.gov/api-docs) using an exact county FIPS filter (`BENE_FIPS_CD=34023`). All 175 returned rows were checked for Middlesex County, NJ, county geography, and unique year/month keys. The slice contains annual rows from 2013 through 2025 and monthly rows from January 2013 through June 2026. The latest monthly source row reports 158,096 total Medicare beneficiaries in June 2026; this is a county-level administrative enrollment count, not the number of people treated at a local hospital. Source fields and string-valued counts are preserved in each normalized record.

The API response metadata had no specific license field. The catalog records the federal dataset source, CMS attribution, and that limitation rather than asserting an unlisted license. CMS methodology and the [data dictionary](https://data.cms.gov/sites/default/files/2024-06/1f010bf1-b0c2-4cac-b9d3-322feb840598/Medicare%20Monthly%20Enrollment_Data_Dictionary%2020240612.pdf) should be consulted before interpreting individual enrollment fields. This aggregate does not establish hospital payer mix, individual eligibility, network participation, reimbursement, or service use.
