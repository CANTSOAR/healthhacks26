# Filling missing data with cited external evidence

The user explicitly authorizes using research papers and other hospitals when local data is unavailable, with the transfer labeled as inferred. This enables a provisional exploratory simulation before local calibration. It does not establish actual RWJUH or Saint Peter's behavior.

## Acquired evidence

Eight papers add 39 normalized records: 29 staff-estimated activity durations from a Canadian ED simulation study, six flow findings from three US studies, and four communication findings. Start with [flow benchmarks](../research/literature-flow-benchmarks.md), [communication benchmarks](../research/literature-interaction-benchmarks.md), and [provisional parameters](../knowledge/provisional-parameters.json). Each normalized record links to a primary source and table or section. Catalog manifests record rights; the CC BY article XML is retained, while the other sources use limited factual paraphrases.

Gabriel and colleagues' [2020 PeerJ study](https://doi.org/10.7717/peerj-cs.284) supplies process timing estimates elicited from hospital staff. These are expert estimates, not observed time-motion measurements. Three source notations—triage T(4,7,10), physician assessment T(7,12,15), and specimen collection T(4,6,15), in minutes—are provisionally interpreted as triangular minimum/mode/maximum parameters. That interpretation and the transfer across hospitals are explicitly analyst assumptions; the inspected text does not define T's parameterization. Table resource markings and footnotes are retained without silently deciding that every multi-role marking means simultaneous resource seizure. CTAS acuity is not automatically equivalent to US ESI.

The other studies provide historical single-site arrival/admission inputs, observed waiting and boarding comparisons, and examples of handoff, interruption, and interpreter communication. They support plausible scenario variation and broad comparisons. They do not determine a present-day local joint distribution. Source discrepancies (including an inconsistent question-count mean) remain visible.

## Evidence-to-parameter workflow

1. Acquire a primary source and preserve setting, period, population, denominator, units, aggregation and source evidence basis.
2. Store its finding unchanged as source evidence. Distinguish measured observations, authors' model inputs, expert estimates, and qualitative findings.
3. Create a separate provisional parameter with source record IDs, target scope, transformation, transfer rationale, uncertainty and replacement criteria.
4. Prefer matched local observations; otherwise compare context-matched external studies before broader external priors. Explicit assumptions are allowed when evidence remains insufficient.
5. Run sensitivity analyses. The current 0.5/1/2 duration multipliers are analyst-selected stress tests, not confidence bounds.
6. Replace proxies when local evidence arrives; preserve old versions and provenance. Report outputs as exploratory until validated against held-out local observations.

Do not add observed queue waits as service times in a queue model. Do not convert a qualitative pattern or small observational rate into an automatic event probability. Keep per-day aggregate statistics separate from individual patient distributions. Link any hospital-inspired synthetic staff behavior to its fictional persona, not a real clinician.

## What remains most valuable

Obtain hourly/day-of-week arrivals by acuity and disposition; conditional service and diagnostic turnaround distributions; staffed bed and roster schedules; admission/transfer dependencies; equipment and room constraints; and workflow observations/interviews. Additional external studies can provisionally cover each gap, but study-to-study variability and correlations matter more than simply collecting more point estimates. This release supplies a small initial set of process inputs, not a complete runnable or calibrated hospital simulator.

## Rebuild and verify

`python3 data/scripts/build_literature_priors.py` rebuilds the envelopes and proxy registry offline from the retained licensed XML and inspected research extracts. It does not refresh the sources. Then run `python3 data/scripts/build_citations.py` and `bash data/scripts/run-verification.sh`. Original XML retrieval endpoint: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7924453/fullTextXML .
