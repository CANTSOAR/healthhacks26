# Verify the extraction yourself

Open **[the review page](index.html)** in a browser. GitHub displays HTML source; use a local checkout for the interactive page. It embeds smaller catalogs and loads the large procedure reference from the local checkout on demand, with no external scripts or model calls.

From the repository root:

```sh
python3 -m http.server 8767 --bind 127.0.0.1
```

Visit http://127.0.0.1:8767/data/review/index.html . Use the local server for full-reference loading. Opening the HTML directly supports embedded records only; relative artifact links require the surrounding checkout.

1. Search for a record or choose its source. Start with `harhay`, `chaisirin`, `jerico`, or `w2-ops-nj-staffing`.
2. Click **Open primary source** and use **Find the source location** to locate the table/section. Open any verification copy when supplied. DOI links are retained in the extracted data/catalog. Publisher access may differ; select `source_unavailable` if you cannot inspect it.
3. Compare **extracted data** against the source: numerical value, unit, denominator, cohort, study period, endpoint definition, observed versus modeled basis, and any footnotes. For APIs, match source-record ID and measure/hospital identifiers. Not every source has a page number; do not claim verification based on title alone.
4. Check that `inferred_scenario_use` is a proposed transfer rather than a claim from the paper. A correct extraction may still be unsuitable for our hospital model.
5. Choose **verified extraction**, **needs correction**, or **source unavailable**, add your name and notes, then **Export review decisions**. No decision is written to the repository automatically. Reloading loses unexported decisions.

Each exported decision includes the record ID and SHA-256 of the exact normalized line you reviewed. Save it under `data/review/decisions/` and ask Codex to reconcile the corrections, recheck the source, rebuild the indexes, and commit. Review files should contain only relevant factual notes, no personal patient information. This workflow intentionally does not treat extraction verification as clinical approval.

## Files for direct inspection

- `data/research/expansion-*.md`: short narratives and unresolved gaps.
- `data/research/expansion-*.json`: structured paper findings, including explicit inferred uses.
- `data/normalized/*.jsonl`: canonical source-record envelopes.
- `data/catalog/*.json`: acquisition, access, scope and rights metadata.
- `data/sources/record-citations.jsonl`: record-to-source mappings and artifact hashes.
- `data/raw/`: saved shareable source responses. Some are projections; many paper findings have no full article retained. The page states this explicitly.
- `data/knowledge/provisional-parameters.json`: earlier adopted exploratory parameters, separate from new external findings.

## Regeneration

Run `python3 data/scripts/build_expansion_evidence.py`, `python3 data/scripts/build_citations.py`, then `python3 data/scripts/build_review_index.py`. Regeneration does not refresh source websites or erase exported decision files. The generated HTML duplicates evidence for portability; edit source data, never the embedded copy. `template.html` is the UI template, not the populated review page.

### Encounter/role expansion

New records are in `data/research/breadth-*.json`. Rebuild with `python3 data/scripts/build_breadth_evidence.py` and `python3 data/scripts/build_encounter_coverage.py`, followed by the citation and review-index builders above. Search `rwjuh-ed-`, `acr-`, `aarc-`, `ehrgym-`, or `admin-aetna-`. Export any current browser decisions before reloading to see newly added records.

### Full procedure reference

Choose `cms-icd10pcs-2027-full (load full reference)` in the Source selector. This 79,256-code reference loads on demand from its normalized JSONL; use the localhost server above (direct file opening cannot fetch it). Search applies to currently loaded records. Loading verifies the full file checksum; exported decisions contain the exact reviewed line checksum. Large-catalog citations are stored in `data/sources/record-citations-large.jsonl.gz`; the ordinary JSONL retains other sources. The full reference overlaps the older 444-code subset and is not a count of unique clinical facts or performed procedures.

## Operational gap expansion

Search `gap-` for the new external literature and guidance extracts. The [expansion report](../research/operations-gap-expansion.md) explains coverage and remaining gaps. Each record retains access scope; the uninspected CT candidate appears only in the pending-source file. [Transfer proposals](../knowledge/gap-transfer-candidates.json) remain inactive and require local validation.

## Specialty and insurance expansion

Search `specialty-` for behavioral health, maternity/NICU, outpatient scheduling, rehab and insurance. Start with [the expansion report](../research/specialty-gap-expansion.md). Two conflicting published figures are blocked from quantitative adoption. Source extraction verification and review of an inferred simulation use are separate decisions.

## Full encounter expansion

Search `encounter-` for arrival, treatment/reassessment, discharge communication and pending-result evidence. See [the report](../research/full-encounter-gap-expansion.md) and [ten-stage readiness map](../knowledge/full-encounter-readiness.json). Each stage lists proposed fields, evidence candidates and unresolved local requirements; it is not an approved protocol.
