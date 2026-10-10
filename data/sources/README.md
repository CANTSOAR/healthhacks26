# Source and record citation index

Generated offline by `python3 data/scripts/build_citations.py` from **19 catalogs and 3,136 records**. All paths in the index are repository-relative. The builder accepts both `data/...` and data-root-relative catalog paths and rejects paths outside the workspace.

- `bibliography.bib`: one stable citation key per dataset/source. Retrieval dates are not publication years. Authors and publication years are omitted when no explicit suitable metadata exists.
- `source-register.json`: source URLs, exact API requests, acquisition status, rights, source dates/versions, catalog and normalized hashes, and stored source artifact hashes.
- `record-citations.jsonl`: one citation per record ID, its source record identifier, exact retrieval URL, available source field locators/periods, normalized line, matching source hash and review status. The source ID joins to rights and other dataset-level details in the register.

## Interpretation

JSON pointers identify exact fields in the supplied record or catalog. Preserved dates include measurement periods, provider update dates, upstream release dates and retrieval times; these have distinct meanings. Null/absent fields are unknown and are not filled from filename guesses. Dataset titles can contain a release year even when no separate publication date is available.

`original_downloaded_response_bytes` follows the verified acquisition-script storage contract for CMS, CDC, RxNorm and the pinned synthetic teaching source. NPPES stores a **minimized projection**, so its hash identifies the saved projection, not the original HTTP body. Generated CDC receipts are also distinguished from source bytes. Manually paraphrased hospital/CHNA assertions have source URLs and locators but **no archived raw source**; the index does not claim byte-verifiable evidence for them. New source families default to originality not declared until their acquisition contract is reviewed.

A raw hash match verifies saved bytes, not the truth, clinical approval, representativeness or current validity of a claim. `source_record_id` may be a constructed composite or parser ordinal rather than an upstream-assigned identifier; exact source fields and parser provenance remain available. Normalized file/line locators refer to this generated snapshot and change if normalization changes.

## Refresh and verification

Run the builder after acquisition or normalization changes. It checks all catalog counts, global record-ID uniqueness, source IDs, raw-path/hash alignment and every available record source hash. It fails on missing files or hash mismatches. Generation is deterministic and introduces no current timestamp; running twice without input changes produces identical files. Full query URLs remain in the machine-readable indexes; bibliographic entries prefer a supplied landing URL where available.
