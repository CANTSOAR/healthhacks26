# Encounter, role and training research expansion

## What this pass adds

Three GPT-6 Luna agents and a root administrative-source pass extracted **28 records from 26 source catalogs**. The cumulative workspace now has **74 catalogs and 4,872 records**. The new evidence includes six clinical/system pathway summaries, nine support-role workflows, eight EHR/training findings, and five administrative/local-workflow findings. These counts measure extracted records, not complete encounters or reviewed clinical protocols.

The [coverage map](../knowledge/encounter-coverage.json) organizes **22 encounter families and 46 planning roles**. It marks dedicated evidence gaps explicitly. The role inventory and mappings are analyst-authored planning constructs; the nine sourced role descriptions do not establish every listed role's permissions or local staffing.

- [Clinical pathways](breadth-pathways.md): wrist injury, acute chest pain, suspected stroke, pediatric asthma, obstetric triage and behavioral crisis. Some guidance is limited to imaging or community system design, rather than an entire ED encounter.
- [Hospital support roles](breadth-roles.md): respiratory therapy, transfusion, dialysis, discharge coordination, interpreters, infection prevention, transport, bed management and environmental services.
- [EHR and training](breadth-ehr-training.md): documented EHRGym capabilities, Epic sandbox limits, local educational programs, and a small simulation-training trial.
- [Administrative evidence](breadth-administration.md): emergency access and Aetna plan-specific rules; the structured file also contains RWJUH's public ED visit components.

## Findings from the attachment, checked against sources

[RWJUH's public ED page](https://www.rwjbh.org/rwj-university-hospital-new-brunswick/treatment-care/emergency-room-services/) supplies a useful local skeleton: triage, clinical examination/testing, bedside registration, admission/discharge. Its introductory ordering and numbered steps disagree about registration versus examination. This supports recording the components, not asserting a strict event order or measured frequencies. Public descriptions cannot reveal informal handoffs, exceptions or shift-level practice.

[EHRGym](https://github.com/adtserapio/EHRGym) documents a provider-focused Epic-like interface and an agent training environment. We verified documentation and license metadata, not a runnable build or learning effectiveness. It does not supply a full hospital EHR or a verified RWJ configuration. Epic's developer sandbox and authorized customer training environments serve different purposes. EpicGym, EHR Go and the Vanderbilt/Iowa materials mentioned in the attachment remain leads requiring separate verification; this pass does not claim a comprehensive product comparison.

The [training evidence record](breadth-ehr-training.json) distinguishes gains on a simulated EMR checklist from actual patient outcomes. It does not establish that our proposed whole-hospital simulation improves safety or onboarding performance. A useful future evaluation would measure task accuracy, appropriate escalation and handoffs, retained performance, and supervised real-work transfer, with baseline/comparator groups and independent assessment. This evaluation design is our proposal.

## How this becomes an encounter

The [encounter evidence contract](../specs/encounter-evidence-contract.json) requires each transition to identify its trigger, actor, information, resource usage, EHR action, timing evidence, exceptions and review status. Clinical, operational, communication and insurance states are separate but linked. This makes a missing transition visible instead of allowing AI to invent it unnoticed.

For the Aetna/wrist-injury example, we now have imaging guidance, an emergency-access constraint, plan-specific authorization distinctions and local ED components. Full treatment/disposition branches, local service availability and an applicable Aetna product snapshot remain missing. That example is a partial design, not a completed simulator.

## Next acquisition queue

The coverage map prioritizes dedicated source packs for sepsis, abdominal pain, major trauma, toxicology, metabolic emergencies, geriatric presentations, neonatal care, oncology, acute dialysis, rehabilitation and palliative care, alongside complete inpatient and elective-surgery pathways. Existing general timing studies remain relevant but do not close those gaps. For every family collect presentation/eligibility, differential and branch conditions, orders/results, task/resource dependencies, consultations, escalation, disposition, follow-up and training evaluation criteria.

Local implementation needs task walkthroughs or approved workflow documents, role permissions, sanitized process timestamps and clinician review. No hospital outreach, restricted Epic access, real patient data or actual-clinician personality modeling was performed. The attached conversation was used as research direction; it was not copied into the public repository or treated as verified source material.

## Human verification

The [review guide](../review/README.md) and regenerated `review/index.html` include all new records. Search `acr-`, `rwjuh-ed-`, `aarc-`, `ehrgym-`, or `admin-aetna-`. Compare source sections to values, then review inference suitability separately. No human decisions are prefilled.
