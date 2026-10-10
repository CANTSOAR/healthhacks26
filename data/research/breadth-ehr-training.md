# EHR training systems and evidence: breadth scan

Snapshot: 2026-10-10. This scan follows the user-provided lead to investigate an “EHRGym/EpicGym”-like open-source EHR, Epic’s official sandbox, RWJBarnabas/RWJMS training context, and evidence that simulation training improves outcomes. The verified repository name is **EHRGym**, at [adtserapio/EHRGym](https://github.com/adtserapio/EHRGym); the evidence checked here does not substantiate a separate “EpicGym” repository.

## Findings

EHRGym’s public GitHub README describes a synthetic-data, Epic-like browser EHR and OpenEnv/FastAPI/Playwright interface for computer-use-agent training, with chart review, note authoring, order signing, and encounter closure. It documents an Apache-2.0 license and a 25-task library. These are repository/documentation claims. The repository was not installed or run for this scan, so source existence and quickstart instructions are not proof of a reproducible build, hosted service reliability, workflow fidelity, or validated human training. The UI is explicitly Epic-like and the project says it is not affiliated with Epic; it should not be represented as Epic software.

Epic’s public FHIR Sandbox serves developer API proof-of-concept/testing. Epic distinguishes this from customer-specific training and test environments, and says the shared sandbox is refreshed weekly, erasing previous-week written data. The open.epic terms say to use only sample/synthetic data and not to use it for performance, scalability, or security testing. Therefore it is not evidence of a general-purpose Epic clinician-training playground or RWJBH’s configured workflow. Epic also says direct Epic software access requires approval by both a customer and Epic.

RWJMS publicly describes a three-week emergency medicine clerkship with supervised shifts, asynchronous lectures, high-fidelity simulation, and tabletop exercises. RWJBarnabas Health publicly describes high-fidelity simulation and structured debriefing in its Institute for Nursing Excellence and an ED nursing foundations course covering cardiac, neurologic, respiratory/medical, trauma, pediatric, and behavioral-health topics. These document training modalities and subject matter; they do not document the local Epic build, detailed EHR tasks, learner denominators, evaluation results, or actual patient outcomes. Local educator confirmation would be needed before translating these descriptions into a RWJBH-specific EHR workflow.

A directly relevant 2026 randomized study is Malin et al., a prospective, parallel, non-blinded, single-center trial with 32 first-year pediatric residents randomized 16:16; 28 (14/group) completed follow-up at 3–6 months. The intervention added EMR-specific training after debriefing; the control had the same debriefing without EMR training. Intervention residents improved more on the sepsis-case EMR checklist (change 2.9 points, 95% CI 1.6–4.2) than controls (0.8, 95% CI −0.4–2.1; interaction p=.02). Outcomes were EMR proficiency and clinical performance in simulated cases. The authors explicitly identify actual clinical-setting improvement as untested. This supports an educational hypothesis, not a patient-outcome claim and not EHRGym validation.

## Evidence boundary and practical implication

The cited material provides evidence of (1) a public codebase and its documented intended features, (2) official sandbox purpose and restrictions, (3) public local-area ED/simulation education context, and (4) a small randomized effect on a learner checklist in simulated cases. It does **not** establish that game/agent performance predicts clinical competence, that training on EHRGym improves clinicians’ real-world workflows, or that the training improves actual patient outcomes. A claim about patient outcomes would require prospective clinical transfer evidence with a defined cohort, comparator, outcomes, and adequate power; those elements are absent from the cited EHR-training trial.

For a prototype, EHRGym could be considered a candidate synthetic sandbox for chart-navigation/documentation/order-entry task design. Keep learner evaluation separate from agent reward scores, have local educators/clinicians validate cases and rubrics, and label any outcomes as simulated until an authorized prospective clinical evaluation establishes transfer. Do not infer RWJBH workflows from Epic’s public FHIR sandbox or generic program pages.

## Sources

- [EHRGym GitHub repository](https://github.com/adtserapio/EHRGym) — README, documented tasks, setup, license, synthetic-data statement.
- [Epic on FHIR Developer Testing Guide](https://fhir.epic.com/Documentation?docId=patientfacingfhirapps&section=AutomaticClientDistribution) — customer environments, sandbox refresh and API-testing scope.
- [open.epic Terms of Use](https://open.epic.com/Home/TermsOfUse) — synthetic/sample-data and testing restrictions.
- [Rutgers RWJMS Emergency Medicine: About](https://rwjms.rutgers.edu/department/emergency-medicine/about) — clerkship, simulations, clinical service and observation-unit descriptions.
- [RWJBarnabas Simulation Program](https://www.rwjbh.org/for-health-care-professionals/nursing/the-institute-for-nursing-excellence/simulation-program/) — high-fidelity simulation and structured debriefing program description.
- [RWJBarnabas Foundations of Nursing Specialty Programs](https://www.rwjbh.org/for-health-care-professionals/nursing/the-institute-for-nursing-excellence/foundations-of-nursing-specialty-programs/) — ED nursing course methods and topic areas.
- Malin S, Centers G, Pearson K, et al. [Impact of Electronic Medical Record Training on Pediatric Residents’ Learning Outcomes: A Simulation-Based Study](https://doi.org/10.7759/cureus.103149). *Cureus*. 2026;18(2):e103149. DOI: 10.7759/cureus.103149.

Structured records, including setting, denominator, outcome, evidence basis, limits, and scenario-use caveats, are in [breadth-ehr-training.json](breadth-ehr-training.json).
