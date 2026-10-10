# Hospital procedures, equipment and RWJ inventory research

The catalog now contains **89 source catalogs and 84,159 record envelopes**. This includes **79,256 unique FY2027 ICD-10-PCS codes** and the earlier 444-code subset, so the total is not a count of unique procedures, unique clinical facts or RWJ activities.

## Acquired and organized

- [Complete inpatient procedure reference](full-procedure-reference.md): all code/title rows in the retained CMS release, not merely selected examples. Exact ZIP hash and source line are retained. CMS lists the release for discharges October 1, 2026–March 31, 2027. This does not cover every professional/outpatient billing system or replace a clinical procedure manual.
- [RWJUH-specific inventory](inventory-rwj.md): 18 sourced capability/count/menu statements for trauma, cath/EP, robotic surgery, diagnostic imaging, proton therapy, brachytherapy, transplantation and pediatric intensive care. Main hospital, BMSCH, outpatient imaging and proton-center scopes are kept explicit.
- [Equipment guidance and candidate resource fields](inventory-equipment.md): 13 records connecting WHO/CDC inventory, maintenance and reprocessing guidance to candidate equipment families. Family-specific fields are analyst proposals where indicated, not observed asset data. They cover ventilators, monitors, infusion pumps, defibrillators, anesthesia systems, ultrasound, CT/MRI, dialysis, sterile processing and blood storage.
- [Hospital resource contract](../specs/hospital-resource-contract.json): a proposed distinction between code, procedure definition, procedure occurrence, equipment family, device model, physical asset and site capability. Includes the data required to model readiness, cleaning, maintenance, reservations, consumables and operators.

## Local facts versus unresolved conflicts

[RWJUH cardiac services](https://www.rwjbh.org/rwj-university-hospital-new-brunswick/treatment-care/heart-and-vascular-care/cardiac-services/) lists seven adult cath labs including two EP labs. Another local program page lists eight; the extracts retain the disagreement rather than choose one. The quoted annual procedure volumes are undated website claims, not a 2026 activity census. Pediatric trauma designations also conflict between pages; local verification remains necessary.

[RWJUH robotic surgery](https://www.rwjbh.org/rwj-university-hospital-new-brunswick/treatment-care/robotic-surgery/) names da Vinci Xi technology and specialties. That does not reveal device quantity, present condition, booking capacity, operator credentialing or available consumables. A general equipment family does not imply local ownership.

## What “all hospital data” still requires

Public references cannot establish RWJ's complete asset register, room-by-room equipment, instrument trays, materials master, maintenance/repair history, live staffing, local order sets, clinical protocols, Epic configuration or task event logs. These remain explicit gaps. The next useful authorized local inputs would be a de-identified asset/equipment export, procedure/service master, staff-role and resource constraints, and a supervised workflow walkthrough. No private records, employee replicas or access requests were obtained or sent.

Other data categories needing fuller coverage include outpatient/professional procedure terminology and permitted reuse, lab test catalogs, medication formulary, supply and implant catalogs, inpatient/outpatient case mix, scheduling and cancellations, referral/discharge networks, insurer product rules, physical layout and utilities, IT downtime, emergency preparedness, and patient-experience outcomes. The existing files provide portions of these; none is marked universally complete.

The new attachment's separation between chart interface and workflow engine is reflected in the resource contract: requested, accepted, performed and documented are distinct concepts. Its claims about particular repositories and training outcomes remain linked to the earlier research report or future verification tasks; the attachment itself is not treated as proof or republished.

## Verify it yourself

Use [the review guide](../review/README.md). Search `rwjnb-` for local assertions or `equipment-` for candidate resource fields. Select **cms-icd10pcs-2027-full (load full reference)** to load all codes, then search a code or title. Source ZIP/line locators, rights, scope and review controls remain available. Loading checks the normalized file hash. Export review decisions before refreshing an existing tab.

The large code-reference citation index is compressed at `sources/record-citations-large.jsonl.gz`; other citations stay in `sources/record-citations.jsonl`. Together they cover every record. Rebuild with `scripts/acquire_full_pcs.py`, `scripts/build_inventory_evidence.py`, `scripts/build_citations.py` and `scripts/build_review_index.py` from the data directory using its pinned Python wrapper as needed.

## Verification

The workspace verification suite passed with 84,159 acquisition envelopes, complete citation coverage, matching source hashes and matching Luna extraction receipts. Browser verification loaded the full reference, found code `0JH60DZ` at normalized line 37,882, and exported a test decision whose SHA-256 matched that exact line. The test decision was not imported as human review. These checks establish structural traceability and UI behavior, not clinical validity or completeness.
