# Hospital ontology

Start with the [ontology guide](../docs/ontology.md) and [domain glossary](../CONTEXT.md).

- `vocabulary.json`: 63 entity definitions in 11 contexts and 43 relationship types.
- `schemas/`: source acquisition and typed graph contracts.
- `competency-questions.json`: 24 questions with evidence needs and limitations.
- `invariants.json`: 20 declared rules with honest enforcement status.
- `examples/`: 44 explicitly synthetic draft entities and two illustrative edges.
- `project_krail.py`: reproducible projection into `../.ontology/ontology.yaml`.
- `validate.py`: schema/graph checks, negative fixtures, and optional normalized-envelope checks.

Run from the repository root:

```sh
python3 data/ontology/validate.py --normalized-dir data/normalized
```

These artifacts propose the semantics for the knowledge base. Acquired source rows remain separate from the synthetic demonstration; no clinical approval or local simulation calibration is implied.
