# Operational evidence from other hospitals

This pass supplements RWJ public data with primary studies and official guidance. Its source findings are external references, not measured RWJ performance. Structured extracts retain setting, period, cohort, endpoint, units, source location, access scope and limitations. Human source verification remains pending.

**Batch: 33 acquired extracts in 19 source catalogs, plus one pending CT source candidate. Three GPT-6 Luna agents supplied 29 acquired extracts; parent research added four guidance extracts.** These are facts and workflow descriptions, not 33 independent datasets or approved model parameters.

## What this adds to the simulation

| Area | Evidence report | Proposed behavior | Still missing locally |
|---|---|---|---|
| Diagnostics and blood bank | [Extracts and sources](gaps-diagnostics.md) | Specimen acceptance/rejection, recollection, transport, analysis/reporting, emergency versus crossmatched blood | Test-specific event traces, local rejection mix, priority rules and blood issue endpoints |
| Pharmacy and supplies | [Extracts and sources](gaps-medication-supply.md) | Verification, dispensing, administration, reconciliation, reusable-instrument readiness | Formulary, medication workflow, stock levels, tray contents and processing queues |
| Patient flow | [Extracts and sources](gaps-patient-flow.md) | Admission, bed cleaning/readiness, transport, discharge dependencies | Staffed bed capacity, queue discipline, shift staffing, placement availability and discharge barriers |
| EHR resilience | [Extracts and sources](gaps-resilience.md) | Independent downtime communications and recovery documentation backlog | Actual downtime policy, drill outcomes and recovery workload |

The behavior column is an analyst proposal. Sources motivate the concepts; they do not establish implementation at RWJ. External time summaries can help evaluate plausibility and design sensitivity studies once the target endpoints are aligned. They cannot independently calibrate the whole hospital.

## Transfer and uncertainty

[Separate transfer candidates](../knowledge/gap-transfer-candidates.json) link each proposed use to source record IDs. Every candidate is inactive and pending human review. Local parameter values and sensitivity bounds remain null until a defensible selection is made. A mean or median does not determine a service-time distribution; before/after outcomes do not isolate a single intervention's causal effect. End-to-end elapsed time includes waiting and must not automatically become active staff service time.

[Pending sources](../workflows/gaps-pending-sources.json) retain leads whose primary text was not inspected. These are excluded from acquired normalized records and transfer candidates. We preserve article links and short factual paraphrases, not entire articles. Where only an abstract was inspected, that limit remains visible. No new patient-level dataset was acquired in this pass.

## Human verification

Open the [review page](../review/index.html) using the [local review guide](../review/README.md), export existing decisions before refreshing, and search `gap-`. Compare each record's value, denominator, source setting, period and exact endpoint with its `locator`. Follow `inspected_source_url` when it identifies a publisher or original-paper mirror. A correct published number may still be unsuitable for RWJ.

Review numerical records first, especially ambiguous collection-to-result versus order-to-report versus arrival-to-transfusion endpoints. Mark an inaccessible article `source unavailable`; do not approve from a paper title alone. Exported decisions bind to the exact normalized line hash. A verified extraction does not activate a simulation parameter or grant clinical approval.

## Next acquisition priorities

1. Match representative local event timestamps to the proposed task states, with department and priority strata; derive queues and service distributions separately.
2. Obtain local workflow review for emergency release, specimen rejection, medication administration, sterile processing and discharge exceptions.
3. Expand still-thin domains: outpatient scheduling/no-shows, rehabilitation and post-acute placement, behavioral health boarding, maternity/NICU, patient communication needs, interpreter access, nutrition, facilities/utilities, and insurer product-specific authorization and payment.
4. Validate correlations and shared-resource constraints across departments. Independent timing samples can miss congestion, repeated tests and shift effects.

The finite [research plan](../workflows/gaps-research-plan.json) and [execution receipt](../workflows/gaps-receipt.json) record this pass. Rebuild commands are listed in the plan; future runs remain unscheduled.

## Verification outcome

The final workspace verification suite passed for 108 source catalogs and 84,192 record envelopes. Citation closure, source-byte checks where snapshots exist, ontology envelopes, separate transfer references, review-index hashes and Luna extract receipts passed. The parent performed [selected source spot checks](../workflows/gaps-parent-review.json); this is not an exhaustive factual audit. Local clinical validity and cross-hospital transferability remain unapproved.
