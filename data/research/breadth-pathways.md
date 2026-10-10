# Breadth pathway sources for synthetic encounter design

Six primary, public guidelines/pathways were reviewed on 2026-10-10 for source-verifiable decision points that broaden the encounter scenarios. These records support workflow planning and case authoring; they are not local hospital protocols, patient-specific medical advice, or clinically approved content. A clinician must verify the source version, local applicability, and any proposed case before use.

The JSON file preserves short source-supported workflow extracts, a locator, population/setting limits, role participants, and separate inferred scenario use. Workflow arrays summarize source recommendations; the inferred-use field describes a possible teaching scenario and is not asserted by the guideline. Role participants are proposed simulation assignments inferred from each pathway setting, not role lists asserted by the sources. Values encode no medication doses.

| Pathway | Source and human-verifiable locator | Case design focus | Applicability boundary |
|---|---|---|---|
| Suspected adult wrist fracture | [ACR Acute Hand and Wrist Trauma](https://acsearch.acr.org/docs/69418/narrative/), Variants 1–2 | Initial radiographs; if negative/equivocal with persisting suspicion, consider the listed repeat-radiograph, CT, or MRI options | Broad acute hand/wrist trauma imaging guidance; clinician decides care and referral |
| ED chest pain | [ACC 2022 ED Acute Chest Pain Pathway](https://www.jacc.org/doi/10.1016/j.jacc.2022.08.750), §§5.2.1, 5.3 and pathway figures | ECG, ischemic/nonischemic branch, assay-specific hs-cTn pathway, disposition | Possible ACS in ED; depends on validated local assay pathway |
| Suspected stroke | [AHA/ASA 2026 AIS Guideline](https://doi.org/10.1161/STR.0000000000000513), §§2.7, 3.2 and Figure 2 | Timeline capture, stroke team, emergent imaging, vascular imaging branch | Primarily adult AIS; clinical eligibility and local system matter |
| Pediatric asthma | [GINA 2026 Strategy Report](https://ginasthma.org/wp-content/uploads/2026/05/GINA-2026-Strategy-Report-WMS.pdf), Ch. 9 and Ch. 12 / Box 12-3 | Age-specific severity assessment, reassessment, escalation | Keep under-5 indicators distinct; no dosing extracted |
| Obstetric triage | [ACOG Committee Opinion 667](https://www.acog.org/clinical/clinical-guidance/committee-opinion/articles/2016/07/hospital-based-triage-of-obstetric-patients), Abstract and Recommendations | Collaborative routing and use of a validated local acuity tool | Systems-level guidance; does not specify a universal algorithm or timing rule |
| Behavioral-health crisis | [SAMHSA 2025 Crisis Care Guidelines](https://library.samhsa.gov/sites/default/files/national-guidelines-crisis-care-pep24-01-037.pdf), Executive Summary / essential crisis-system elements | Contact, mobile response, stabilization options | Community crisis-system framework, not an ED risk/disposition algorithm |

## Version notes

The source-period fields record publication/revision information visible in the cited source. ACR labels its narrative “Revised 2018”; the accessed narrative does not establish whether a later reaffirmation or replacement exists. ACOG Committee Opinion No. 667 dates to July 2016; current reaffirmation/update status was not established from the accessed page. The AHA/ASA 2026 stroke guideline describes imaging as rapidly as possible, with “within 25 minutes” as an example; supporting text reports that ≤25-minute door-to-imaging times have been achieved in some settings and says MRI-first hospitals should strive for similar times. This is a process aim, not a universal guarantee. GINA’s under-five immediate-transfer signs are Box 12-3, page 219 (not Box 12-2).

## Evidence and review boundary

These are guideline/pathway recommendations and narrative source extracts, not measured local wait times or operational performance. The supplied role participants are modeling aids inferred from the setting, not necessarily enumerated workflow actors in every source. No dataset or local clinical workflow was acquired. Clinical approval status remains unreviewed.
