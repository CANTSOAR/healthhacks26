# Encounter-model resource and workflow constraints

This evidence supports a discrete-event encounter with acuity-dependent queues, role-specific task requirements, room/equipment pools, task dependencies, interruption states, and explicit handoff ownership. It does not establish any RWJ staffing level, duration, local capacity, interruption probability, or operational policy.

Two ED discrete-event models provide scenario structures rather than direct universal standards. Bedoya-Valencia and Kirac represent nurse-first then physician/PA evaluation, ordered tests, result-ready gating, repeat evaluations, acuity-specific staff/test bundles, and one site's rooms/shared diagnostic services. Gabriel et al. encode AND/OR flow logic and mark tasks that require all assigned staff, including nurse+physician procedures and multi-role huddles; their process times are manager/nurse Delphi estimates. Preserve these as candidate constraints and separate modeled values from observed events.

A prospective time-motion cohort observed interruptions during triage and associated greater interruption frequency with more errors and longer triage. It supports allowing task switches, an unfinished-task marker, and a recheck/rework branch, but does not establish interruption priority or forced preemption. The ESI-based model offers acuity ordering as a local model choice; no source reviewed here specifies a universal queue tie-breaker or preemption algorithm.

NHS England guidance prescribes clinical ownership from ambulance arrival, immediate receipt for pre-alerted patients requiring a clinical team, and a 15-minute handover target for non-pre-alerted arrivals. This is policy, not compliance data, and is not RWJ policy. Model clinical acceptance separately from registration and label the target as an external scenario parameter.

## Sources inspected

- Bedoya-Valencia & Kirac, 2016, [Evaluating alternative resource allocation in an emergency department using discrete event simulation](https://doi.org/10.1177/0037549716673150). Primary full text inspected. Single US ED; local model specification and resource inventory.
- Gabriel et al., 2020, [Lean thinking by integrating with discrete event simulation and design of experiments: an emergency department expansion](https://doi.org/10.7717/peerj-cs.284). Primary full text inspected. Canadian ED expansion; historical data and expert Delphi model inputs.
- Johnson et al., 2021, [Interruption of initial patient assessment in the emergency department and its effect on patient perception of care quality](https://doi.org/10.1093/intqhc/mzab146). Primary full text inspected. Observational cohort of 178 assessments; excludes ESI 1.
- NHS England, [Guidance for emergency departments: initial assessment](https://www.england.nhs.uk/guidance-for-emergency-departments-initial-assessment/). Official operational guidance page inspected; England-specific prescribed handover workflow.

No local rate or duration is inferred. No staffing ratio is transferred. Transferable values must remain external scenario parameters with local replacement criteria; room/equipment counts and rules require RWJ evidence and faculty validation before representing the real hospital.
