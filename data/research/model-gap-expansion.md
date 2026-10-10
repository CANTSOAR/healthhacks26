# Case branches, workflow constraints and timing evidence

This pass used three GPT-6 Luna agents and added **22 acquired evidence records in 10 campaign source catalogs**, plus one pending source candidate. These are external references, not RWJUH New Brunswick observations. Some sources repeat earlier campaigns: catalog counts are not unique studies. All extractions still await human review.

## What this makes possible

| Area | Added evidence | Simulation use and remaining limit |
|---|---|---|
| Case branches | Five records: unresolved injury after negative films, scaphoid suspicion, reporting before discharge and distinct return-advice routes | Supports a richer adult wrist-injury example. Does not supply branch probabilities or a complete approved treatment protocol. [Branch details and citations](model-branches.md). |
| Workflow and resources | Eight records: repeated clinician contacts, result gates, joint role requirements, room/equipment categories, interruptions and ambulance handover | Supports explicit task and resource models. Published model assumptions and policy targets remain distinct from observed behavior. No local roster, preemption policy or available capacity is established. [Resource details and citations](model-resources.md). |
| Timing | Nine records: stage means, reported simulation inputs and radiology transport benchmarks | Supports comparison and sensitivity research. Two Rio distribution records are blocked because the paper conflicts internally; the Quebec triangular specifications remain model inputs. [Timing details and citations](model-timing.md). |

[Eight proposed model requirements](../knowledge/model-requirement-candidates.json) link these findings to concrete engineering decisions. They remain inactive; capacities, branch probabilities and duration distributions are null. [Transfer candidates](../knowledge/model-transfer-candidates.json) separately record inference, target setting, assumptions and replacement criteria. None grants clinical approval or establishes RWJ practice.

## Corrections from parent source checks

- The Beirut transport interval follows the Methods definition, cashier processing to radiographer study initiation. The Discussion describes a different endpoint; the discrepancy is retained. It is not total imaging completion time or staff labor time.
- Rio's Table 7 and appendix disagree on a triage expression, and its fit validity is unestablished. The earlier claim of body/appendix disagreement over fit p-values was withdrawn after full PDF review; see the calibration audit. Both distribution candidates remain blocked from quantitative adoption.
- The Canadian expansion model's Table 2 huddle uses five listed roles, excluding porter. Its charting task lists ED nurse and admin; it does not establish a laboratory role for that task.
- NICE recommendations 1.1.9 and 1.2.3 were checked against the original page. NHS initial injury warnings and recovery/cast concerns have different routes and are kept separate.
- The ACEP refusal-policy candidate was available only as indexed text in this pass. It is saved in [pending sources](../workflows/model-pending-sources.json), excluded from acquired records and the review index. This leaves a primary-source verification gap for the proposed refusal branch.

These are source spot checks, not an exhaustive clinical or statistical audit. [The audit receipt](../workflows/model-parent-review.json) records scope and locators.

## Highest-priority remaining work

1. **Complete one approved encounter:** a clinician must reconcile competing guidance, define emergency escalation, treatment/reassessment, discharge and follow-up branches, and identify exceptions. Begin with the existing adult wrist case before generalizing to pediatrics or other injuries.
2. **Resolve timing before sampling:** verify distribution conventions and fit conflicts. Obtain event-level or published quantile evidence with clear endpoints, censoring, case mix, shifts and sample sizes. Means and confidence intervals are insufficient to calibrate patient trajectories.
3. **Model real contention:** acquire task-level simultaneous-resource requirements, release points, actual staffed capacity, breaks, room cleaning, equipment downtime and task interruption policies. Licensed beds and staff affiliations cannot substitute for availability.
4. **Calibrate branch likelihoods and dependencies:** imaging escalation, consultations, return visits, admission and refusal need conditional denominators. Do not combine unrelated hospital probabilities or assume durations are independent.
5. **Close encounter ownership:** verify who accepts handovers, acknowledges results, contacts patients, books follow-up and handles failed contact. Insurance needs actual product/network/benefit rules; a carrier name alone does not define coverage or payment.

The [next research jobs](../workflows/model-next-jobs.json) are bounded drafts, not scheduled or automatically running workflows.

## Human verification

Open [the review interface](../review/index.html) and search **`model-`** (or a full record ID). For each finding, compare the value, unit, cohort, dates and endpoint with its source URL and locator. Inspect `source_access` and use `inspected_source_url` when it differs from the canonical citation. Review the proposed use separately from whether extraction is accurate. Export decisions before refreshing an already-open review page; source spot checks have not marked any record human-approved.

For example, search `model-timing-rio-simulation-triage-fit` and compare Table 7 with the appendix, then search `model-timing-aub-radiology-transport` and compare Methods with Discussion. The original extraction JSON files remain beside these reports; the normalized envelopes and citations are regenerated by `build_model_evidence.py`, `build_model_transfers.py`, `build_citations.py` and `build_review_index.py`.
