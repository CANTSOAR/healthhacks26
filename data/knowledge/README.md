---
title: Hospital evidence knowledge base
kind: research
topics: [hospital, evidence]
---

# Evidence-backed knowledge base

The first knowledge layer is the 3,136 source-normalized records in [normalized](../normalized/), each resolvable through [record citations](../sources/record-citations.jsonl). Source-aware findings live in [hospital research](../research/hospital-provider-quality.md) and [community research](../research/local-community-insurance.md). These documents are indexed by the native KRAIL Markdown graph.

The [ontology](../docs/ontology.md) defines canonical entity contracts. Acquired source rows remain in their original observational scope; they have not been silently converted to hospital state, clinical truth or simulation probabilities. The canonical graph example is explicitly synthetic. This separation lets us add explicit identity reconciliation and reviewed entity projection without losing original evidence.

A useful query can start with a CCN (310038 RWJUH or 310070 Saint Peter's), a dataset source ID, geographic FIPS (3451210 New Brunswick; 34023 Middlesex), or an exact record ID. Preserve identifier namespaces and reporting periods when joining. NPI matching across CMS and NPPES is an identity join, not proof of current privileges.

[The first Luna review](luna-review.md) demonstrates bounded synthesis with citation closure. It is a candidate analysis layer and is not part of an approved scenario or operational model.
