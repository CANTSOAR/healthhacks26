---
title: Wave2 Clinical
kind: research
topics: [hospital, evidence]
---

# Wave 2 clinical terminology acquisition

Retrieved 2026-10-10. These are reusable public terminology references for an educational hospital simulation, not evidence of local hospital operations or patient outcomes.

## Acquired snapshots

| Dataset | Normalized records | Source snapshot and rights | Intended use |
| --- | ---: | --- | --- |
| [FY2027 ICD-10-CM selected diagnoses](../catalog/w2-clinical-icd10cm-dx-2027.json) | 415 | CDC/NCHS code-description ZIP, FY2027. CDC says most agency materials are public domain, with agency attribution; check third-party exceptions before reuse. | Search and display selected acute-care diagnosis labels, including chest pain, MI, heart failure, arrhythmia, sepsis, pneumonia, respiratory failure, AKI, syncope, stroke, GI hemorrhage, shock, and hypoxemia. |
| [FY2027 ICD-10-PCS selected procedures](../catalog/w2-clinical-icd10pcs-proc-2027.json) | 444 | CMS code-file ZIP, FY2027. CMS release page identifies this code file as the official annual procedure release; retain CMS attribution and check its reuse terms. | Balanced sample of titles containing coronary, transfusion, ventilation, endotracheal, dialysis, extirpation, thrombolytic, and pacemaker terms. Extirpation is an operation title, not proof that a code means thrombectomy. |
| [RxNorm drug forms](../catalog/w2-clinical-rxnorm-forms.json) | 312 | Five NLM RxNav drugs.json query responses (aspirin, nitroglycerin, heparin, metoprolol, furosemide). NLM states these APIs may be used free of charge; API terms and third-party drug-name rights still apply. | Display/search RxNorm concept names, RxCUIs, term types, forms, and strengths; these records do not specify what should be ordered or administered. |

Raw downloaded bytes are retained under raw/w2-clinical-*. Every normalized envelope points to the specific source response or release ZIP with its SHA-256, retrieval timestamp, source URL, source locator, and a deterministic parsing note. The ICD normalizations retain a bounded subset selected from source titles while the original ZIPs preserve the complete official source snapshot. The script is [acquire_clinical_wave2.py](../scripts/acquire_clinical_wave2.py).

Primary sources:

- CDC, [FY2027 ICD-10-CM files](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2027/icd10cm-code-descriptions-2027.zip); release listings and applicability dates are on the [CDC ICD-10-CM files page](https://www.cdc.gov/nchs/icd/icd-10-cm/files.html).
- CMS, [FY2027 ICD-10-PCS code file](https://www.cms.gov/files/zip/2027-icd-10-pcs-codes-file.zip); annual release index and official guidelines are on the [CMS ICD-10 page](https://www.cms.gov/medicare/coding-billing/icd-10-codes).
- NLM, [RxNorm API](https://rxnav.nlm.nih.gov/REST/drugs.json?name=aspirin) and [RxNav terms of service](https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html).
- CDC, [agency-material use and public-domain attribution guidance](https://www.cdc.gov/other/agencymaterials.html).

## Interpretation and remaining evidence gaps

ICD-10-CM descriptions and ICD-10-PCS code titles support vocabulary lookup and case authoring. They do not include all tabular notes, coding conventions, sequencing rules, definitions, clinical criteria, or an approved care pathway. Check the code version for the simulated date and have a coding/clinical educator verify any code used in a learner-facing case. PCS is principally an inpatient procedure classification; it is not a complete inventory of ED actions.

RxNorm results are identity candidates. TTY indicates the returned RxNorm concept type; the wide name-search may surface multiple branded, generic, dose-form, strength, pack, or legacy concepts. No dose, route choice, timing, indication, contraindication, order, formulary availability, or care recommendation was inferred or authored.

These references cannot establish which services RWJBarnabas/RWJUH staffs or offers at a given site, actual capacity, referral routing, equipment, lab panels, vital-sign acquisition, units used locally, clinical thresholds, durations, treatment sequence, or outcomes. For a truthful scenario, those facts need attributable current local sources and faculty review. This wave also did not acquire a licensed synthetic longitudinal FHIR bundle or validated lab-observation/value/unit examples; do not use the current terminologies to fabricate patient trajectories, laboratory values, treatment response, or pathway timing.

## Reproduction and checks

Run python3 data/scripts/acquire_clinical_wave2.py to download and rebuild these bounded catalogs and JSONL envelopes. Source downloads are capped at 25 MB each and transfers time out after 90 seconds. The normalizer is deterministic apart from retrieval timestamps and the upstream RxNav response snapshot.
