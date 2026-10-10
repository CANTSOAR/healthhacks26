# Evidence needed for a complete patient encounter

This research pass prioritizes missing links between patient arrival and follow-up over adding more terminology entries. The previous fracture example was explicitly partial. New evidence expands arrival/handoff, treatment and reassessment, communication and post-discharge ownership. The scope remains research and design, not an implemented or clinically approved simulator.

**Batch: 24 acquired records in 19 source catalogs, 24 inactive transfer proposals and a ten-stage proposed encounter coverage map.** Workspace totals are 145 catalogs and 84,249 record envelopes, including overlapping terminology and studies; these are not counts of independent datasets or approved parameters.

## Prioritized evidence

| Priority | Research pack | Why it matters | Remaining local requirement |
|---|---|---|---|
| P0 | [Arrival and waiting](encounter-arrival.md) | Someone must own identity, handoff, acuity assessment and deterioration while a patient waits | Local patient identification, triage and reassessment policies; staff/resource availability and event timestamps |
| P0 | [Adult wrist/distal-radius treatment example](encounter-treatment.md) | A suspected fracture requires evaluated findings, a reviewed treatment decision, reassessment and disposition | A clinician-authored case and injury-specific branches, local orthopedic access, role permissions and complication logic |
| P0 | [Communication and closure](encounter-communication.md) | Orders and notes alone do not establish comprehension, safe discharge or follow-up | Reviewed consent/capacity content, interpreter access, accessible instructions, result-owner escalation and callback workflow |

These priorities are analyst judgments based on the gaps in our current encounter contract. References in each pack support individual source findings; proposed simulation uses remain separate in [the transfer registry](../knowledge/encounter-transfer-candidates.json).

## Proposed encounter coverage map

[Full encounter readiness](../knowledge/full-encounter-readiness.json) links ten stages to existing evidence and new source candidates. The map describes proposed roles and state fields, explicitly unknown timing models, and unresolved local requirements. Candidate lists are discovery aids, not proof that every source supports every field. The map includes:

1. Arrival, identity and accepted handoff.
2. Urgency assessment and ownership while waiting.
3. History, examination and communication needs.
4. Orders, acceptance and actual performance.
5. Results and clinician review.
6. Treatment, consent and reassessment.
7. Disposition, receiving-team acceptance and transfer.
8. Discharge plan and understanding.
9. Pending results, callbacks and follow-up resolution.
10. Administrative work running alongside the clinical encounter.

This is not a universal linear pathway. Some tasks run in parallel, recur or are skipped by a reviewed branch. Admission, transfer, leaving before assessment, failed contact, declined care and unresolved uncertainty need explicit authored handling. Demographic or payer group associations do not define a patient's personality, preferences or outcome.

## What the earlier Aetna/fracture example can now support

The source packs can inform an authored adult wrist-injury teaching encounter: arrival and assessment; injury-specific examination and escalation considerations; imaging and result review; selected treatment decision factors; reassessment; disposition and follow-up communication. They do not determine what happened to a particular synthetic patient. Clinical findings and responses must come from approved case data. Adult distal-radius findings must not silently generalize to pediatric fractures, every arm injury, or every mechanism.

The insurance track still needs the actual plan/product, service, network and benefit snapshot. Existing insurance sources do not establish an individual member's coverage or payment. Emergency screening/treatment must not be gated by invented authorization steps. Claims, payment and administrative closure have separate unresolved inputs.

## Highest-value next inputs

- **Clinical reviewer:** approve a bounded case truth set, possible diagnostic/treatment/disposition branches and expected reassessments; resolve conflicting guidance and population exclusions.
- **Local operations reviewer:** map who accepts each task, required resources and permissions, local handoffs, reassessment/escalation ownership and workarounds.
- **Data owner:** provide representative de-identified event definitions and timing/resource data with setting and priority strata. Separate waiting, active work and documentation time; preserve repeated tasks and correlations.
- **Patient communication reviewer:** review interpreter/consent/capacity branches, plain-language discharge content, understanding checks, practical access barriers and failed-contact escalation.
- **Simulation author:** implement versioned state transitions and exceptions only after choosing a reviewed source or explicitly labeled synthetic assumption for each adopted rule.

Public papers can specify useful comparisons and measurement targets, but do not supply the entire local model. All transfer proposals remain inactive with local numerical values unset. Source targets, summary statistics and intervention effects are not fitted service-time distributions.

## Human review

Use the [review guide](../review/README.md), export existing decisions before reloading the [review page](../review/index.html), then search `encounter-`. Follow each source locator and inspected URL. Check whether a number describes patients, visits, tests, documents, staff labor or elapsed time; inspect subgroup denominators and missing values. A correct extraction is separate from approval to use it in the simulation. [Pending sources](../workflows/encounter-pending-sources.json) stay outside acquired evidence if the primary text could not be inspected.

## Source conflicts and applicability

The radiology acknowledgment study reports a percentage change inconsistent with its stated before/after rates; the extract retains both and blocks quantitative adoption. A waiting-area monitoring unit error was caught against the original source and corrected before normalization. NSW and UK fracture follow-up recommendations differ in scope/timing and remain separate; neither is an observed RWJ appointment time. The deployed-care neurovascular reassessment source is an explicitly limited workflow proxy. Selected referral criteria are not a complete treatment pathway. See [parent review notes](../workflows/encounter-parent-review.json).

## Verification outcome

Final workspace verification passed for 145 catalogs and 84,249 record envelopes. Checks covered provenance/citation closure, retained-source hashes where available, ontology envelopes, receipt hashes, review records and source-linked transfer/readiness maps. Targeted checks enforce the corrected monitoring unit and propagation of the radiology quantitative-use block. All 24 new transfer proposals remain inactive and all ten readiness stages retain unknown local timing distributions. These checks do not establish clinical validity or completeness.
