# Hospital-wide evidence expansion — October 10, 2026

Three GPT-6 Luna agents inspected primary papers across diagnostics, inpatient flow and perioperative/support services. This finite pass adds **10 paper catalogs and 25 source records**, bringing the workspace to **48 catalogs and 4,844 records**. These are acquired factual extracts, not newly calibrated local simulation parameters. No new human approvals are claimed.

| Area | New evidence | What it enables | Remaining gap |
|---|---|---|---|
| Lab | POCT and central-lab timing, draw-to-all-results and decision intervals | Separate analytical work from complete-result availability | Test-specific local routing, batching, transport and joint timestamps |
| Radiology | Overall, CT and plain-film report turnaround before/after workflow change | Compare reporting bottlenecks and workflow variants | Scanner service time, modality queues, priority rules, day/night schedules |
| Pharmacy | Stat/urgent dispensing timing and threshold shares | Explore priority classes and dispensing workload | Ward delivery, administration timing, stockouts and verification steps |
| ICU / transfers | Readiness-to-departure distributions and morning request clustering | Represent clinically ready patients still occupying beds | Destination availability, competing transfers, transport/cleaning timestamps |
| Inpatient staffing | Admissions/discharges/transfers, daily and shift-level turnover | Model event workload in addition to census | Skill mix, task durations, breaks, roster and acuity dependencies |
| OR / cleaning | Cleaning, turnover and robotic task timing | Distinguish cleaning from the complete turnover process | Specialty-specific distributions, parallel tasks, cancellations, room calendars |
| PACU | Stay duration, prolonged stays and ward-handover delays | Link recovery beds to ward capacity and handover | Acuity-specific care requirements and discharge-ready timestamps |
| Sterile processing | Case-cart interruptions and tray defect reports | Add upstream instrument availability and coordination scenarios | Reprocessing cycle times, inventory, rework paths, demand correlations |

## What the evidence tells us

Hospital flow depends on linked services, not just encounters and bed counts. A delay after discharge readiness continues occupying a bed; a lab's analytical time is not necessarily complete-result availability; cleaning is only part of OR turnover. These are modeling interpretations of the cited source-specific endpoints, not estimates of local effects. Each underlying finding and its proposed scenario use are in the domain extracts below.

- [Diagnostics: sources and interpretations](expansion-diagnostics.md)
- [Inpatient: sources and interpretations](expansion-inpatient.md)
- [Perioperative: sources and interpretations](expansion-perioperative.md)

Do not sum component medians to manufacture a total-time distribution, pool pre/post cohorts, or fit a distribution from a median alone. Interventions in other hospitals do not establish effects here. No additional operational proxies were automatically activated in this pass; inspect and choose them separately from acquired findings.

## Verification performed

Root review checked all submitted structures and selected primary-source values. Independent XML comparison confirmed the lab timing rows and radiology table/99 missing observations. Primary publisher PDF confirmed the OR cleaning/turnover summary. Agent follow-up clarified ICU article-versus-supplement provenance and flagged unstated/inconsistent denominators. Source sites sometimes block retrieval; alternate inspected URLs and the absence of saved snapshots are recorded. This is a sample-based agent check, not a complete independent human audit.

Discrepancies remain visible: the pharmacy paper prints 28/30 as 90% (arithmetic 93.3%); the inpatient paper's reported 9.95 events/day cannot be reproduced from 3,562 events divided by 365 without knowing its included-day denominator. Do not silently normalize either into a supposed corrected source statistic.

## Human review and next acquisition priorities

Use [the human review guide](../review/README.md) and [interactive index](../review/index.html). Prioritize any finding proposed for use as an active model parameter, then records with conflicts or conditional populations. Source verification and transfer suitability are different decisions.

Next breadth priorities remain insurer authorization/denial and discharge-placement delays; blood bank, dialysis and respiratory therapy; inpatient rehabilitation and social work; environmental services beyond ORs; facilities/equipment downtime; food/laundry/supply-chain capacity; and emergency surge staffing. Prioritize papers reporting definitions, denominators and event distributions over isolated averages. The collected external estimates can support explicitly provisional scenarios while local evidence remains incomplete.
