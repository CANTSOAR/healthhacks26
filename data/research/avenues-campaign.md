# Hospital research avenues campaign

Finite GPT-6 Luna campaign: **27 jobs**, **27 completed**, **76 source candidates**. These candidates are source-discovery results, not additional acquired datasets or reviewed simulation parameters.

Machine results, each exact prompt, receipts, candidate reports and sanitized web-tool URL evidence are saved in [`avenues-20261010T151704Z`](../runs/avenues-20261010T151704Z/). Failed/time-limited jobs, if any, remain explicit.

| Domain | Status | Source candidates | Completed web calls |
|---|---|---:|---:|
| authority-credentials | completed | 3 | 2 |
| authorization-claims | completed | 3 | 2 |
| blood-supplies-equipment | completed | 3 | 3 |
| calibration-causality | completed | 3 | 2 |
| costs-finance | completed | 3 | 2 |
| demand-case-mix | completed | 3 | 2 |
| diagnostics-consults | completed | 3 | 2 |
| discharge-community | completed | 3 | 2 |
| facilities-topology | completed | 3 | 2 |
| fairness-access | completed | 3 | 2 |
| flow-capacity | completed | 3 | 2 |
| geography-demographics | completed | 1 | 2 |
| insurance-coverage | completed | 3 | 2 |
| nursing-allied-health | completed | 3 | 2 |
| pathways-procedures | completed | 3 | 3 |
| patient-experience | completed | 3 | 2 |
| pharmacy-medication | completed | 3 | 2 |
| population-health | completed | 2 | 2 |
| practitioner-identity | completed | 3 | 2 |
| prices-payments | completed | 3 | 3 |
| provenance-governance | completed | 2 | 2 |
| resilience-facilities | completed | 3 | 3 |
| safety-quality | completed | 2 | 2 |
| staffing-availability | completed | 3 | 2 |
| teaching-scenarios | completed | 3 | 2 |
| terminology-identifiers | completed | 3 | 2 |
| workflow-culture | completed | 3 | 2 |

Three parallel acquisition workers separately pursued operational, clinical and community/insurance inputs. Their actual acquired records and source snapshots are in `catalog/`, `normalized/`, `raw/` and the canonical citation index. See [operations](wave2-operations.md), [clinical](wave2-clinical.md), and [community/insurance](wave2-context.md) for counts, methods and failures.

Discovery does not eliminate the need for direct operational inputs. Public reports usually provide marginal or historical aggregates. They do not reveal all shift availability, queue/service decomposition, conditional transition rules, clinical truth or causal effects. No source agreement was accepted and no outreach was sent.

The campaign runner caps parallelism and runtime, validates each output schema and separates results from the acquired catalog. The web evidence ledger retains observed URLs and tool actions without republishing source text. An observed URL can be a search result rather than an opened/downloaded dataset. Every candidate still needs scope, access, rights and content verification before acquisition or use.
