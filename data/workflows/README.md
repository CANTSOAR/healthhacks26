# Bounded research workflows

All commands below run from `data/`. Python dependencies are pinned in `requirements.txt`; native workflows use `scripts/python` through `uv run` so KRAIL's own isolated interpreter cannot hide dependencies. `scripts/krail` pins KRAIL 1.1.13 through `uvx`; use `--local --path .` for this workspace.

## Deterministic collection and provenance

- `python3 scripts/acquire_hospital_data.py`: nine bounded CMS/NPPES datasets. Network refresh overwrites that source's current snapshot; Git preserves committed earlier versions.
- `python3 scripts/acquire_local_data.py`: CDC public data plus curated, located primary-source facts. `--offline` rebuilds from saved CDC bundles without claiming a new retrieval date. Manually curated facts require human refresh when their source changes.
- `python3 scripts/acquire_teaching_terms.py`: pinned eight-profile CC-BY dataset and eight RxNorm identity queries. `--only profiles` or `--only terms` narrows collection.
- `python3 scripts/build_citations.py`: rebuilds source/record citation indexes and bibliography.
- `bash scripts/run-verification.sh`: verifies source bytes, provenance, counts, candidate references, schemas and domain invariants offline.

Native KRAIL workflows are in [research_plan/workflows](../research_plan/workflows/): `coverage-audit`, `public-data-refresh`, `luna-evidence-review`.

```sh
./scripts/krail --local --path . workflow validate coverage-audit
./scripts/krail --local --path . workflow execute coverage-audit --dry-run
./scripts/krail --local --path . workflow execute coverage-audit
```

Refresh downloads the current bounded public subsets; it does not acquire every hospital in the country or bypass restricted access. Treat a failed run as incomplete, repair the specific source, then rebuild citations and validate before commit. Never interpret a prior successful snapshot as proof that the refresh succeeded.

## GPT-6 Luna research

`python3 scripts/run_luna.py JOB` prepares a review packet; add `--execute --timeout 240` to run it. Jobs and source filters are defined in [luna-jobs.json](luna-jobs.json). Each call caps the record packet, output schema and execution time. It uses the existing authenticated Codex CLI with `--model gpt-6-luna`, ephemeral context, user config disabled, and read-only sandbox. No credentials are stored here.

The model receives public evidence, not arbitrary research permissions. Output must cite supplied record IDs. Saved packet, candidate and receipt are review artifacts under `runs/`; diagnostic traces are ignored under `runs/private/`. The workflow does not promote claims, mutate clinical state, publish changes or schedule recurring work. A completed run proves provider execution and structural output validation, not factual entailment.

Use the acquisition backlog to choose the next bounded domain. Add its official source, rights/access status, scope and retrieval method first; acquire a small verifiable subset; normalize without erasing missingness; then rebuild citations. Expansion to restricted datasets requires the appropriate agreement through its legitimate process. Keep unavailable sources explicitly pending.
