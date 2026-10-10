# How useful is the evidence for our simulation?

Assessment date: 2026-10-10. Scope: educational patient encounters first, an explorable hospital world, and later a quantitative hospital operations simulation. This is an engineering assessment of the collected evidence, not clinical validation.

**The first collection supports believable context and historical benchmarks. It does not identify the operational mechanisms needed for a calibrated hospital simulation.** Most of its 3,136 rows are clinician affiliations (2,142) and a practitioner sample (200); row count is not a measure of scenario coverage or simulation readiness. Eight teaching profiles are synthetic source material, not eight faculty-approved cases.

## What we can build from the first collection

| Part of the experience | Current usefulness | Supported use | Still missing |
|---|---|---|---|
| Hospital setting and navigation | Useful foundation | Named institutions, public services and affiliations | Verified campus → building → wing → unit hierarchy, capabilities, physical layout and actual capacity |
| Patient conversation and social context | Useful foundation | Teach communication, financial access and follow-up barriers in authored cases | Reviewed patient goals, symptom narratives, disclosure triggers, culturally appropriate responses and interpreter workflows |
| Clinical chart and decision progression | Limited | Seed case families, identifiers and synthetic profiles | Consistent clinical facts, timeline, orders/results, clinical transitions, contraindications, review and scoring rubric |
| Staffing, queues and resource contention | Insufficient for calibrated predictions | Identify resource types and compare selected output benchmarks | Arrivals, service times, transfers, available resources, schedules, joint dependencies and escalation rules |
| Insurance and financial decisions | Limited | Separate insurer identity, facility participation, charges and historical payment averages | Plan/product/network/date-specific rules, patient cost-sharing, authorizations and resource costs |
| Evaluation | Useful external anchors | Compare like-for-like reported duration/experience measures | Independent event-level or aggregate validation period, predefined acceptance criteria and sensitivity analysis |

A simplified operational sandbox can still be built with explicitly labeled assumptions. Its output must say “under these assumptions,” not claim a forecast of RWJUH. A more detailed ontology does not itself supply numerical parameters.

## What the existing data tells us

1. **Local access barriers belong in scenarios.** The collected 2023 CDC modeled crude estimates put lack of insurance among adults 18–64 at 24.7% in New Brunswick versus 10.8% in Middlesex County; adult food insecurity at 33.9% versus 13.7%; unreliable transport at 17.3% versus 7.0%. The stored confidence intervals and measure populations matter. These observations justify exploring affordability, transport and discharge follow-up in authored scenarios; they do not justify drawing independent patient attributes at those rates. [Collected estimates and uncertainty](../research/local-community-insurance.md), [CDC methodology](https://www.cdc.gov/places/methodology/index.html).
2. **Sepsis and heart-failure case families deserve examination.** In the acquired 2024 Medicare provider/DRG rows, sepsis DRG 871 has 588 RWJUH and 164 Saint Peter's discharges; heart-failure/shock DRG 291 has 278 and 121. These are published Original Medicare fee-for-service inpatient cells, with small-cell suppression, rather than all-payer ED arrivals or incidence. This can guide faculty selection of candidate case families; it cannot set our general patient-arrival probabilities. [Evidence and scope](../research/hospital-provider-quality.md), [source catalog](../catalog/cms-inpatient-provider-service-2024.json).
3. **We have a duration benchmark, not a queue model.** CMS OP_18b reports 206 and 208 median ED minutes for the two facilities, for October 2024–September 2025 and the source's eligible population. This excludes transfers and psychiatric/mental-health patients. The same median could arise from different arrival patterns, staffing bottlenecks and service times. We cannot infer one from the other. [Source records](../normalized/cms-timely-effective-care.jsonl).
4. **Communication needs both quantitative and qualitative evidence.** Reported HCAHPS doctor “always communicated well” percentages are 77% and 76%, with response rates 17% and 15%. Those are survey outcomes, not a model of any named doctor's behavior. Combine such measurement definitions with independently reviewed scenario dialogue and participant-reported themes. [Source records](../normalized/cms-hcahps.jsonl).
5. **We can represent a real institutional network without pretending it is a schedule.** Public NPI/CCN affiliations help connect practitioners and facilities. They cannot establish employment, current competence, privileges, shifts, role authority or availability. Use real identities only for factual directory context; make behavioral agents fictional or explicitly synthetic.

Each numerical claim is traced to exact normalized IDs in [baseline-facts.json](../analysis/baseline-facts.json), which join to [record citations](../sources/record-citations.jsonl). The second acquisition wave is reported separately so these first-collection observations remain reproducible.

## What we need next, in priority order

**For the educational encounter:** faculty-reviewed CaseVersions with chief complaint, history, timeline, examination, observations, orders/results, unknowns, permitted actions, disclosure rules and decision-dependent changes; learner objectives and an evidence-linked rubric; qualitative patient goals, concerns and communication preferences. Build several internally coherent cases before generating unlimited variations. Clinical variation must stay within reviewed constraints.

**For a credible one-unit flow simulation:** a time-stamped arrival profile by hour/day and relevant acuity/complaint groups; unit-specific staffed capacity and resources by shift; routing and admission/discharge/transfer frequencies; conditional durations for triage, clinician contact, tests, consults, procedures, boarding and bed turnover; rules defining who can do what and which resources must be available simultaneously. Capture weekends, peaks and missing/censored events. A proposed starting extraction is 8–12 weeks for an initial narrow ED model, extended for seasonality and low-frequency pathways; this is a project design choice, not a guarantee of sufficiency.

**For qualitative hospital behavior:** consented and appropriately deidentified observations of handoffs, escalation, interruptions, patient explanations, interpreter use, teamwork and discharge coordination. Ask domain experts to review authored workflow narratives when direct observations are unavailable. Public satisfaction percentages cannot reconstruct these conversations.

**For finance and access:** dated plan-level benefit and prior-authorization rules; inpatient/outpatient and facility/professional distinctions; negotiated allowed amounts where available; patient share and charity-care rules; resource costs with period and accounting definitions. Never substitute a chargemaster value for a cost or a received payment.

**For validation:** reserve a different reporting period or independent source for testing; compare arrival volume, throughput, duration quantiles/tails, occupancy, boarding, abandonment and subgroup outcomes using matching definitions. Matching one median is underdetermined. Track parameter uncertainty, dependence, missingness and local applicability. Public national benchmarks are useful as explicitly labeled priors or sensitivity ranges, not local truth.

The [input contract](../specs/simulation-input-contract.json) gives a concrete data request for each of these categories. No individual identifiers are needed for most initial operational calibration: aggregates and pseudonymous event linkage may suffice, subject to legitimate access and review. No external requests have been sent.

## How the expanded campaign is organized

Twenty-seven bounded GPT-6 Luna discovery jobs cover the backlog's domains. They inspect primary-source avenues and return structured candidates; separate collection workers acquire useful data with source bytes and provenance. A source found, a source fetched, normalized data, reviewed knowledge and a calibrated parameter are distinct states. Access failures stay visible instead of being filled with invented values.

See [campaign report](../research/avenues-campaign.md) for actual completion and acquisition outcomes, and [the acquisition roadmap](acquisition-roadmap.md) for the larger coverage map.

## What the second wave changes

We now have actual Q2 2026 NJ staffing observations for the two hospitals, a state acute-care facility inventory and 2023 CMS cost reports with beds, FTE and utilization fields. These strengthen unit/resource definitions and historical volume constraints, but quarterly ratios and annual FTE still cannot reconstruct hourly resource availability. Source bed counts conflict in scope and definition and must be reconciled, not averaged.

Additional SVI county/tract data adds finer geographic context; Medicare enrollment adds a county coverage denominator; diagnosis/procedure terminology and RxNorm concepts support consistent identifiers. None of those automatically supplies care pathways. Fifteen AHRQ-derived topic descriptions add concrete qualitative dimensions for handoffs, escalation, teamwork and workload, but are not local behavioral observations or a validated derivative scoring instrument.

The next highest-value acquisition is now within-unit temporal detail and reviewed clinical/interaction content, rather than more unconnected provider identities. See the separate wave2 source reports for exact counts, definitions, dates and access limits.

Do not divide reported daily patient averages by daily RN/staff averages to infer a concurrent patient-to-staff ratio; these data do not provide time-aligned census and staffing observations.
