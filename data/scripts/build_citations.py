#!/usr/bin/env python3
"""Build deterministic offline source/record citation indexes from catalog + JSONL evidence."""
import gzip
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
REPO = DATA.parent
OUT = DATA / 'sources'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(value):
    """Catalogs currently use both data-root and repo-root relative paths."""
    p = Path(value)
    if p.is_absolute():
        raise ValueError('Expected portable relative path: ' + value)
    result = (REPO / p if p.parts and p.parts[0] == 'data' else DATA / p).resolve()
    if not result.is_relative_to(DATA.resolve()):
        raise ValueError('Path escapes data workspace: ' + value)
    if not result.is_file():
        raise FileNotFoundError(result)
    return result


def rel(path):
    return str(path.relative_to(REPO))


def fields(value, names, prefix=''):
    """Retain exact supplied values and JSON pointers; do not synthesize missing dates."""
    found=[]
    if isinstance(value, dict):
        for key,item in value.items():
            pointer=prefix+'/'+key.replace('~','~0').replace('/','~1')
            if key.lower() in names and item is not None:
                found.append({'pointer':pointer,'value':item})
            if isinstance(item,dict):
                found.extend(fields(item,names,pointer))
    return found


DATE_KEYS={'period','year','start_date','end_date','data_period','upstream_modified','upstream_released','last_updated','retrieved_at','opened_period','revision','version','release_year','reference_period','report_date','publication_date'}
LOCATOR_KEYS={'locator','measure_id','measureid','hcahps_measure_id','facility_id','rndrng_prvdr_ccn','drg_cd','npi','fips','queried_name','rxnorm_ids','datavaluetypeid','year'}


def storage_kind(sid,path,cat):
    # Verified acquisition-script contracts; unknown future sources are explicitly unclassified.
    if sid=='nppes-new-brunswick-practitioners':
        return 'projected_response_not_original_bytes'
    if path.name=='receipt.json':
        return 'generated_retrieval_receipt'
    if sid.startswith('cms-') or sid.startswith('local-cdc-') or sid in {'nlm-rxnorm-seed-terms','twinverse-patient-profiles'}:
        return 'original_downloaded_response_bytes'
    declared=cat.get('provenance',{}).get('raw_artifact_kind')
    return declared if isinstance(declared,str) else 'stored_artifact_originality_not_declared'


def bib_escape(value):
    return str(value).replace('\\','\\textbackslash{}').replace('{','\\{').replace('}','\\}').replace('&','\\&').replace('%','\\%').replace('_','\\_').replace('#','\\#')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    sources=[]; citations=[]; bib=[]; seen=set()
    for catalog_path in sorted((DATA/'catalog').glob('*.json')):
        cat=json.loads(catalog_path.read_text())
        sid=cat['source_id']
        if sid!=cat['dataset_id']:
            raise ValueError('Dataset/source mismatch: '+sid)
        normalized=resolve(cat['normalized_path'])
        normalized_digest=digest(normalized)
        rows=[json.loads(line) for line in normalized.read_text().splitlines() if line.strip()]
        if len(rows)!=cat['record_count']:
            raise ValueError('Record count mismatch: '+sid)
        assets=[]; hashes={}
        for name in cat.get('raw_paths',[]):
            path=resolve(name);sha=digest(path);hashes.setdefault(sha,[]).append(rel(path))
            expected=cat.get('raw_sha256',{}).get(name) if isinstance(cat.get('raw_sha256'),dict) else None
            if expected and expected!=sha:
                raise ValueError('Catalog artifact hash mismatch: '+name)
            assets.append({'path':rel(path),'sha256':sha,'bytes':path.stat().st_size,'storage_kind':storage_kind(sid,path,cat)})
        for line_number,row in enumerate(rows,1):
            if row['record_id'] in seen or row['source_id']!=sid:
                raise ValueError('Duplicate record ID or wrong source')
            seen.add(row['record_id']);prov=row.get('provenance',{});sha=prov.get('raw_sha256')
            matches=hashes.get(sha,[]) if sha else []
            if sha and not matches:
                raise ValueError('Record hash does not match stored artifact: '+row['record_id'])
            if prov.get('raw_path') and rel(resolve(prov['raw_path'])) not in matches:
                raise ValueError('Record raw path/hash mismatch')
            citation={'record_id':row['record_id'],'source_id':sid,'bibtex_key':sid,'source_record_id':row.get('source_record_id'),'source_url':prov.get('source_url',cat.get('source_url')),'retrieved_at':prov.get('retrieved_at',cat.get('retrieved_at',cat.get('provenance',{}).get('retrieved_at'))),'source_locators':fields(row.get('data',{}),LOCATOR_KEYS,'/data'),'reported_temporal_fields':fields(row.get('data',{}),DATE_KEYS,'/data'),'source_version_and_dates':fields(cat,DATE_KEYS),'normalized_locator':{'path':rel(normalized),'line':line_number,'file_sha256':normalized_digest},'raw_sha256':sha,'matching_raw_paths':matches,'raw_evidence_status':'projected_response_not_original_bytes' if sid=='nppes-new-brunswick-practitioners' else ('stored_hash_verified' if matches else 'no_raw_source_available'),'evidence_kind':row.get('evidence_kind'),'review_status':row.get('review_status'),'provenance_as_recorded':prov}
            citations.append(citation)
        provenance=cat.get('provenance',{})
        source={'source_id':sid,'bibtex_key':sid,'title':cat['title'],'source_url':cat.get('source_url'),'source_urls':cat.get('source_urls',[]),'query_requests':cat.get('queries',[]),'landing_url':cat.get('landing_url'),'upstream_dataset_id':cat.get('upstream_dataset_id'),'rights_as_recorded':cat.get('rights'),'scope_as_recorded':cat.get('scope'),'limits_as_recorded':cat.get('limits',[]),'acquisition_status':cat.get('acquisition_status'),'provenance_as_recorded':provenance,'reported_temporal_fields':fields(cat,DATE_KEYS),'catalog_path':rel(catalog_path),'catalog_sha256':digest(catalog_path),'normalized_path':rel(normalized),'normalized_sha256':normalized_digest,'record_count':len(rows),'stored_artifacts':assets,'raw_availability':'available' if assets else 'no_raw_source_available'}
        sources.append(source)
        retrieved=cat.get('retrieved_at',provenance.get('retrieved_at'))
        parts=[f'@misc{{{sid},', '  title = {'+bib_escape(cat['title'])+'},', '  url = {'+cat.get('landing_url',cat.get('source_url',''))+'},']
        if provenance.get('doi'):
            parts.append('  doi = {'+bib_escape(provenance['doi'])+'},')
        if retrieved:
            parts.append('  urldate = {'+retrieved[:10]+'},')
        if cat.get('rights',{}).get('attribution'):
            parts.append('  author = {{'+bib_escape(cat['rights']['attribution'])+'}},')
        parts.append('  note = {'+bib_escape('Dataset ID: '+sid+'. See source-register.json for exact queries, rights, versions and record-level periods.')+'}')
        parts.append('}')
        bib.append('\n'.join(parts))
    register={'schema_version':'1.0.0','generation':'Deterministic offline derivation; no source refetch and no inferred publication date or author','source_count':len(sources),'record_count':len(citations),'sources':sources}
    (OUT/'source-register.json').write_text(json.dumps(register,indent=2,ensure_ascii=False)+'\n')
    large_ids={s['source_id'] for s in sources if s['record_count']>5000}
    (OUT/'record-citations.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in citations if c['source_id'] not in large_ids))
    large=[c for c in citations if c['source_id'] in large_ids]
    if large:
        (OUT/'record-citations-large.jsonl.gz').write_bytes(gzip.compress((''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in large)).encode(),mtime=0))
    (OUT/'bibliography.bib').write_text('\n\n'.join(bib)+'\n')
    (OUT/'README.md').write_text(f'''# Source and record citation index

Generated offline by `python3 data/scripts/build_citations.py` from **{len(sources)} catalogs and {len(citations):,} records**. All paths in the index are repository-relative. The builder accepts both `data/...` and data-root-relative catalog paths and rejects paths outside the workspace.

- `bibliography.bib`: one stable citation key per dataset/source. Retrieval dates are not publication years. Authors and publication years are omitted when no explicit suitable metadata exists.
- `source-register.json`: source URLs, exact API requests, acquisition status, rights, source dates/versions, catalog and normalized hashes, and stored source artifact hashes.
- `record-citations.jsonl` plus `record-citations-large.jsonl.gz` (when present, catalogs with more than 5,000 records): one citation per record ID across the two indexes, its source record identifier, exact retrieval URL, available source field locators/periods, normalized line, matching source hash and review status. The source ID joins to rights and other dataset-level details in the register.

## Interpretation

JSON pointers identify exact fields in the supplied record or catalog. Preserved dates include measurement periods, provider update dates, upstream release dates and retrieval times; these have distinct meanings. Null/absent fields are unknown and are not filled from filename guesses. Dataset titles can contain a release year even when no separate publication date is available.

`original_downloaded_response_bytes` follows the verified acquisition-script storage contract for CMS, CDC, RxNorm and the pinned synthetic teaching source. NPPES stores a **minimized projection**, so its hash identifies the saved projection, not the original HTTP body. Generated CDC receipts are also distinguished from source bytes. Manually paraphrased hospital/CHNA assertions have source URLs and locators but **no archived raw source**; the index does not claim byte-verifiable evidence for them. New source families default to originality not declared until their acquisition contract is reviewed.

A raw hash match verifies saved bytes, not the truth, clinical approval, representativeness or current validity of a claim. `source_record_id` may be a constructed composite or parser ordinal rather than an upstream-assigned identifier; exact source fields and parser provenance remain available. Normalized file/line locators refer to this generated snapshot and change if normalization changes.

## Refresh and verification

Run the builder after acquisition or normalization changes. It checks all catalog counts, global record-ID uniqueness, source IDs, raw-path/hash alignment and every available record source hash. It fails on missing files or hash mismatches. Generation is deterministic and introduces no current timestamp; running twice without input changes produces identical files. Full query URLs remain in the machine-readable indexes; bibliographic entries prefer a supplied landing URL where available.
''')
    print(f'Indexed {len(sources)} sources and {len(citations)} records; all record source hashes verified when supplied.')

if __name__=='__main__':
    main()
