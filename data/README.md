# Hospital ontology and evidence workspace

A first version of the whole-hospital knowledge system, grounded in New Brunswick, New Jersey. This repository contains the acquired data, provenance, ontology and reproducible research workflows. The database and live scenario engine are later work.

**Snapshot: 2026-10-10. 89 source catalogs and 84,159 normalized record envelopes.** This includes the full 79,256-code CMS inpatient procedure reference and an overlapping earlier subset; it is not a count of unique hospital activities. Public evidence, terminology, synthetic profiles and analyst proposals remain separately labeled. See the [latest procedures, equipment and RWJ expansion](research/inventory-summary.md) and [human verification guide](review/README.md). Coverage remains partial for hospital operations and local assets.

## Start here

- [Ontology design](docs/ontology.md), [domain context](CONTEXT.md), [machine vocabulary](ontology/vocabulary.json) and [schemas](ontology/schemas/).
- [Source citations and bibliography](sources/README.md): every acquired record has a citation ID and lineage.
- [Hospital/provider/quality findings](research/hospital-provider-quality.md) and [community/insurance findings](research/local-community-insurance.md).
- [Acquisition roadmap](docs/acquisition-roadmap.md) and [machine backlog](workflows/acquisition-backlog.json).
- [Knowledge-base entry point](knowledge/README.md) and [workflow instructions](workflows/README.md).
- [Prior project research](../research/README.md) and [whole-hospital rationale](../research/whole-hospital-data-blueprint.md).

## What is actually collected

The first collection below contains 3,136 records. The second wave adds 1,644 records across 11 datasets; source/definition samples are not patients or calibrated simulation parameters.

| Collection | Records | Scope |
|---|---:|---|
| CMS hospital identities | 3 | New Brunswick city inventory |
| CMS hospital quality and patient experience | 336 | RWJUH and Saint Peter's, multiple reporting periods |
| CMS clinician–facility affiliations | 2,142 | Published affiliation rows, not shifts or privileges |
| NPPES practitioner sample | 200 | First bounded public sample; minimized professional fields |
| CMS 2024 Medicare DRG utilization/payment | 241 | Published FFS Part A provider-service rows; small cells suppressed |
| CDC PLACES | 160 | City/county, crude and age-adjusted estimates; release 2025 |
| CDC-hosted historical ACS factors | 18 | 2017–2021 city/county estimates, not current ACS |
| CHNA, services, insurance and staffing documentation | 20 | Limited sourced facts; no actual staffing values |
| NLM RxNorm identity lookups | 8 | Identifier matches, not medication instructions |
| Rutgers VHS teaching profiles | 8 | CC-BY-4.0 synthetic profiles at pinned source revision |

| Second-wave collection | Records | Scope |
|---|---:|---|
| NJ acute-care licensing inventory | 69 | Selected facility and reported bed fields; not available capacity |
| NJ quarterly staffing | 19 | Q2 2026, unit ratios and ED/PACU daily summaries for two hospitals |
| CMS annual cost reports | 2 | 2023 provider reports, beds/FTE/utilization/accounting fields |
| Middlesex Medicare enrollment | 175 | Monthly and annual aggregates; not hospital payer mix |
| Middlesex SVI | 193 | County plus 192 tracts; national rankings, ACS2018–2022 |
| ICD-10-CM / ICD-10-PCS | 859 | FY2027 selected code descriptions; full source ZIPs retained |
| RxNorm drug concepts | 312 | Five ingredient queries, terminology only |
| Qualitative interaction dimensions | 15 | Limited AHRQ-derived topic paraphrases; no local behavioral observations |

Read the [simulation usefulness assessment](docs/simulation-readiness.md), [input contract](specs/simulation-input-contract.json), and [27-job research campaign report](research/avenues-campaign.md). All 27 live-web GPT-6 Luna jobs completed, yielding76 candidate source entries (72 distinct URLs), separately from acquired datasets. Detailed new findings: [operations](research/wave2-operations.md), [clinical terminology](research/wave2-clinical.md), [community/enrollment](research/wave2-context.md), [qualitative dimensions](research/wave2-behavior.md).

`raw/` retains permitted source bytes or explicitly marked minimized projections. `normalized/` contains source-shaped JSONL records. `catalog/` records scope, acquisition state, rights and limitations. `ontology/examples/` contains invented structural fixtures and is excluded from acquired-record totals. Source paths may be repository-relative (`data/...`) or workspace-relative; the resolver accepts both only within this workspace.

## Reproduce and validate

Python 3.10+ is required. Install `requirements.txt` in a virtual environment. KRAIL's wrapper requires `uv` and pins KRAIL 1.1.13. The optional model workflow requires an authenticated Codex CLI with GPT-6 Luna access.

```sh
cd data
python3 scripts/build_citations.py
bash scripts/run-verification.sh
./scripts/krail --local --path . workflow validate coverage-audit
./scripts/krail --local --path . workflow execute coverage-audit
python3 scripts/run_luna.py baseline-evidence-review            # prepare only
python3 scripts/run_luna.py baseline-evidence-review --execute  # one bounded model call
```

One actual GPT-6 Luna review completed in [the saved run](runs/20261010T150413Z-baseline-evidence-review/). It reviewed a 32-record packet and returned eight candidate findings with source-record references. This verifies the local CLI workflow, not clinical validity. [Review notes](knowledge/luna-review.md) record interpretation limits.

## Boundaries and remaining evidence

The ontology models the broad system but public evidence does not yet calibrate it. Quarterly unit staffing summaries and annual provider FTE/bed reports are now acquired. Actual shift availability, staffed capacity over time, arrival/transfer timestamps, service durations, operational pathways and dependencies, patient-level trajectories, and plan-specific coverage rules remain missing. Medicare rows do not establish all-payer case mix; community prevalence does not establish hospital patient prevalence. Published affiliation does not establish employment, privileges, schedules or availability. Insurance participation does not establish individual benefits. No real patient records or private clinical notes are included.

Preserve missing/suppressed source values. Promote a source record into a typed entity or simulation parameter only through an explicit mapping and review. Faculty approval applies to a specific case version; model output cannot grant it. See [AGENTS.md](AGENTS.md) for research and contribution rules.

## Literature-derived provisional inputs

The literature extension brings the catalog to **38 datasets and 4,819 records**. Eight papers contribute 39 records, with three explicitly inferred process parameters. See [how external evidence fills local gaps](docs/literature-proxies.md). These extend the earlier acquisition counts above; they do not establish local calibration.

## Hospital-wide expansion and human review

Current totals: **48 catalogs / 4,844 records** after a three-agent Luna pass added 25 findings from 10 papers. See [expansion and remaining gaps](research/expansion-summary.md). **[Start human verification here](review/README.md)** or open `review/index.html` in your browser. Source links, locators, evidence, and exportable review decisions are provided for every record.

## Encounter and role coverage

Latest totals: **74 catalogs / 4,872 records**. The [new breadth report](research/breadth-summary.md) adds clinical pathways, support-role workflows, EHR/training evidence and Aetna/emergency-access distinctions. The [coverage map](knowledge/encounter-coverage.json) tracks 22 encounter families and 46 planning roles without claiming complete coverage. Review new records through `review/index.html`.
