# data/ — public data behind the catalog

Everything here is public, aggregate data. `data/raw/` is gitignored (downloads); `data/processed/` holds the small tracked
extracts (about 0.4 MB) that catalog attributes cite in their `file:` field. Full source notes, terms and caveats:
`research/operations-data-sources.md`.

## Layout

| Path | What |
|---|---|
| `fetch/_common.py` | download helper (records URL, size, sha256, time in `data/raw/<dir>/SOURCES.jsonl`) |
| `fetch/_catalog_edit.py` | `set_attr(file, path, fields)`: replaces ONE attribute block of a catalog YAML as text; refuses to change a value's shape |
| `fetch/<source>.py` | fetch + process one source into `data/processed/` |
| `fetch/apply_<source>.py` | write that source's values into `catalog/` (value, unit, source, citation, url, file, note) |
| `fetch/build_validation_targets.py` | regenerates `catalog/validation_targets.yaml` |
| `fetch/coverage.py` | counts attributes by source tag -> `processed/catalog_coverage.json` |
| `adapters/` | data-service interface: `PublicExtracts` (offline) and `Vlada` (online, chosen only by `VLADA_API_KEY`) |

## Re-running (from `data/fetch/`, with `../../.venv/bin/python`)

```
care_compare.py        # local, ~60 MB download            -> care_compare_ed_*.{json,csv}
nhamcs.py              # heavy (8 Stata files) - deepstack  -> nhamcs_ed_*.{json,csv}
cms_facility.py        # heavy (HCRIS 135 MB) - deepstack   -> cms_pos_310038.json, cms_cost_report_summary_310038.json, hcris_310038_fy2024*
cms_rates.py           # ~4.5 MB, slow xlsx parse           -> ipps_fy2027_*, opps_2026jul_selected_codes.csv
bls_oews.py            # 4 BLS API calls (25/day unkeyed)   -> bls_oews_staff_wages.csv
fluview.py             # Delphi Epidata mirror of ILINet    -> fluview_ili_*.{csv,json}
apply_care_compare.py; apply_nhamcs.py; apply_cms_facility.py; apply_cms_rates.py; apply_bls.py; apply_bls_absence.py; apply_fluview.py
build_validation_targets.py; coverage.py
```

On deepstack the same scripts were run from `~/projects/hospitalgym_aryan/data_work/data/fetch/` (the scripts resolve
`data/raw` and `data/processed` relative to themselves) and `data/processed/` was copied back with rsync. The NHAMCS 2019,
2021 and 2022 zips were fetched with curl before the script existed, so `processed/nhamcs_download_log.jsonl` lists only the
five older years; the URL pattern is the same (`.../nhamcs/stata/<ED|ed><year>-stata.zip`).

`bls_cps_absences_table47_2025.json` is the one extract not produced by a script: www.bls.gov returns 403 to scripted
clients, so the table was read through a fetch tool (twice, matching) and transcribed. Its catalog tag is `literature`.

## Adapter

```python
from data.adapters import get_data_service
svc = get_data_service()                       # PublicExtracts unless VLADA_API_KEY is set
svc.get_table("nhamcs_ed_by_acuity", subset="metro_teaching", acuity="3")
svc.status()
```

`Vlada` is an MCP-over-HTTP client for `https://mcp.vladahealth.com/mcp` (tools `find_data_sources`, `describe_data_source`,
`query_substrate`, 200-row cap) written from the organizer guide. It has never been run against the real service: the tool
argument names, bearer-token auth and Vlada's table names are unverified, and the logical-table -> SQL map
(`adapters/vlada_tables.json`) does not exist yet. Until it does, every call falls back to the public extract and
`status()` reports the fallback. Tests: `.venv/bin/python -m pytest data/adapters -q` (5 tests, faked HTTP).
