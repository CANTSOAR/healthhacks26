# Specialty and insurance evidence expansion

This pass extends the hospital evidence base into behavioral health, maternity/NICU, outpatient scheduling, rehabilitation and insurance. Source findings retain their original institution, country, cohort, period and endpoint. None establishes measured RWJ performance or a validated local pathway.

**Batch: 33 acquired evidence records in 18 source catalogs, with 33 separate inactive transfer proposals.** The workspace now contains 126 source catalogs and 84,225 record envelopes, including overlapping terminology references and extracts from previously used studies. These totals do not measure independent datasets or validated simulation parameters.

## How to use the evidence

| Domain | Evidence report | Proposed simulation structure | Local data still needed |
|---|---|---|---|
| Behavioral health | [Studies and guidance](specialty-behavioral-health.md) | Assessment, observation resources, boarding, placement acceptance and follow-up linkage | Actual safety/observation policy, trained staffing, crisis-service availability, boarding and disposition logs |
| Maternity/NICU | [Studies and guidance](specialty-maternity-nicu.md) | Obstetric triage and transitions; neonatal acuity, staffing, transfer and discharge; caregiver participation | Local acuity definitions, staffed beds, neonatal transport constraints, delivery and neonatal workflows |
| Outpatient scheduling | [Studies](specialty-outpatient.md) | Referral receipt, scheduling attempts, offered slot, booking, cancellation, attendance and rescheduling | Specialty-specific queues, visit types, slots, lead times, cancellations and no-shows |
| Rehabilitation | [Studies and guidance](specialty-rehab.md) | Multidisciplinary assessment, therapy resources, functional goals, placement and discharge coordination | Therapy access/capacity, eligibility, local assessment tools, post-acute availability and patient goals |
| Insurance | [Payer metrics and guidance](specialty-insurance.md) | Eligibility inquiry, notification, coverage review, appeal and payment as separate states | Actual product/benefits, network, service-specific rules, authorization and claim event traces |

The proposed structure is an inference. The papers do not provide an executable whole-hospital protocol. Relative effects, odds ratios, policy limits, staffing recommendations, cohort percentages and observed elapsed times have different meanings and must not be interchanged.

## Transfer controls

[Specialty transfer proposals](../knowledge/specialty-transfer-candidates.json) link proposed uses to the acquired record IDs. All remain inactive and pending human review. Local values and sensitivity bounds are null. No probabilities or duration distributions are fitted from summary statistics. Correlations with insurance or appointment wait time are not automatic causal effects or patient-level prediction rules.

The insurance sample is specific to an identified Medicare Advantage contract and reporting year; it is not a statement about every Aetna member. Regulatory decision deadlines are not observed service times. Emergency screening/treatment must not be blocked by administrative simulation tasks. Policy applicability must match jurisdiction, product, service and effective date.

## Human verification

Use [the review page](../review/index.html) with the [review guide](../review/README.md), export decisions before refreshing, then search `specialty-`. Follow the primary link and `inspected_source_url`; compare the exact `locator`, denominator, value, unit and study setting. Abstract-only and official-guidance records are labeled. Missing counts or unit definitions are retained as unknown. Inspect the transfer proposal separately from whether the extraction is correct.

[Pending source candidates](../workflows/specialty-pending-sources.json) are excluded from acquired evidence if only search-index text was accessible. No restricted patient records, insurer logins or private hospital documentation were obtained. Source URLs and limited factual extracts are retained; full copyrighted papers are not republished.

## What remains unresolved

This is a bounded research pass, not completion of the five domains. Major remaining gaps are local patient mix, event sequences and timing distributions; changing capacity and staffing; site-specific safety and clinical policies; payer product and service rules; and validation with clinicians, operations staff, scheduling teams and financial counselors. Public findings can guide what to measure and provide external comparators, but cannot establish these local values.

The [finite research plan](../workflows/specialty-research-plan.json) lists rebuild commands and scope. Source extraction receipts and the insurance audit describe execution, not human approval.

## Extraction quality findings

Two original articles contain count/percentage inconsistencies: psychiatric emergency-service disposition and rehabilitation screening timing. Both preserve the published statements and have `quantitative_use_status: blocked_source_internal_inconsistency`. The outpatient GI abstract omits the wait-time increment and regression sample size; these remain unknown, and the odds ratio cannot be used as a per-day coefficient. [Parent spot checks](../workflows/specialty-parent-review.json) and the [Luna insurance audit](../workflows/specialty-insurance-audit.json) record limited verification scope.

## Verification outcome

Final workspace checks passed with 126 source catalogs and 84,225 normalized record envelopes. Checks covered citation closure, retained-source hashes where available, ontology envelopes, evidence review hashes, extraction/audit receipts and transfer references. Additional checks confirmed all 33 new records have explicit access/applicability labels and all 33 transfer candidates remain inactive, with two explicit quantitative-use blocks. These structural checks and selected source spot checks do not establish clinical validity or local transferability.
