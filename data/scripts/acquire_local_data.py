#!/usr/bin/env python3
"""Fetch bounded public CDC community slices. No credentials, full-US downloads or hospital PDF copies.
Run from any directory: python3 data/scripts/acquire_local_data.py
Use --offline to regenerate from checked-in source bytes and original retrieval metadata.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ('local-cdc-places-new-brunswick-2025', 'eav7-hnsx', '3451210', 'place', 'model'),
    ('local-cdc-places-middlesex-2025', 'swc5-untb', '34023', 'county', 'model'),
    ('local-cdc-acs-new-brunswick-2017-2021', 'edkk-ze78', '3451210', 'place', 'survey'),
    ('local-cdc-acs-middlesex-2017-2021', 'i6u4-y3g4', '34023', 'county', 'survey'),
]

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'healthhacks26-public-data-research/0.1'})
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Bounded response exceeds 2MB; refusing to save')
    return raw, json.loads(raw)

def number(value):
    return None if value in (None, '') else float(value)

def acquire(spec, offline=False):
    sid, api_id, fips, level, kind = spec
    directory = ROOT / 'raw' / sid
    source_url = 'https://data.cdc.gov/resource/' + api_id + '.json?' + urllib.parse.urlencode({'locationid':fips, '$limit':500, '$order':'year,measureid,datavaluetypeid'})
    metadata_url = 'https://data.cdc.gov/api/views/' + api_id + '.json'
    if offline:
        body = (directory / 'records.json').read_bytes()
        values = json.loads(body)
        metadata = json.loads((directory / 'metadata.json').read_bytes())
        receipt = json.loads((directory / 'receipt.json').read_bytes())
        assert receipt['sha256'] == hashlib.sha256(body).hexdigest()
    else:
        body, values = fetch(source_url)
        meta_body, metadata = fetch(metadata_url)
        if metadata.get('licenseId') != 'PUBLIC_DOMAIN':
            raise ValueError('Rights metadata changed; review before storing')
        assert isinstance(values, list) and 0 < len(values) < 500, 'Missing or possibly truncated slice'
        assert all(row['locationid'] == fips and row['stateabbr'] == 'NJ' for row in values)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'records.json').write_bytes(body)
        (directory / 'metadata.json').write_bytes(meta_body)
        receipt = {'source_url':source_url, 'metadata_url':metadata_url, 'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(), 'sha256':hashlib.sha256(body).hexdigest(), 'metadata_sha256':hashlib.sha256(meta_body).hexdigest(), 'row_count':len(values)}
        dump(directory / 'receipt.json', receipt)
    rows=[]
    columns={c['fieldName']:c.get('description') for c in metadata['columns']}
    for row in values:
        rid=':'.join([fips,row['year'],row['measureid'],row['datavaluetypeid']])
        estimate=number(row.get('data_value'))
        lower,upper=number(row.get('low_confidence_limit')),number(row.get('high_confidence_limit'))
        if lower is not None and upper is not None and estimate is not None:
            assert lower <= estimate <= upper
        data={
            'geography':{'fips':fips,'level':level,'name':row['locationname'],'state':'NJ'},
            'measure_id':row['measureid'],'measure':row['measure'],'category':row['category'],
            'period':row['year'],'estimate':estimate,'unit':row['data_value_unit'],
            'estimate_type':row['data_value_type'],'population_scope':'See full measure text; measures have different age/universe restrictions',
            'uncertainty':{'method':'95% model-based confidence interval' if kind=='model' else 'ACS margin of error (source field; confidence level not supplied in this dataset metadata)', 'lower':lower,'upper':upper,'margin_of_error':number(row.get('moe'))},
            'geographic_population_context':{'total':number(row.get('totalpopulation')),'adults':number(row.get('totalpop18plus')), 'total_reference':columns.get('totalpopulation'), 'adult_reference':columns.get('totalpop18plus'), 'warning':'Geographic context counts are not necessarily the measure denominator.'},
            'source_fields':row,
            'allowed_use':['community_context','hypothesis_generation'],
            'not_validated_for':['hospital_case_mix','individual_patient_sampling','causal_policy_evaluation','local_queue_calibration']
        }
        rows.append({'record_id':sid+':'+rid,'source_id':sid,'source_record_id':rid,'record_type':'PopulationEstimate','data':data,'provenance':{'source_url':receipt['source_url'],'retrieved_at':receipt['retrieved_at'],'raw_sha256':receipt['sha256']},'evidence_kind':'published_local_modeled_estimate' if kind=='model' else 'published_local_survey_estimate','review_status':'source_extracted_not_domain_reviewed'})
    assert len({x['record_id'] for x in rows}) == len(rows)
    out=ROOT/'normalized'/f'{sid}.jsonl'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    catalog={'dataset_id':sid,'source_id':sid,'title':metadata['name'],'source_url':receipt['source_url'],'landing_url':f'https://data.cdc.gov/d/{api_id}','record_count':len(rows),'raw_paths':[str((directory/p).relative_to(ROOT.parent)) for p in ['records.json','metadata.json','receipt.json']],'normalized_path':str(out.relative_to(ROOT.parent)),'scope':{'geography_level':level,'fips':fips,'periods':sorted({r['year'] for r in values}),'measure_count':len({r['measureid'] for r in values})},'access':'public_unauthenticated','rights':{'license_id':metadata.get('licenseId'),'evidence_url':metadata_url,'redistribution':'source metadata PUBLIC_DOMAIN; attribution retained'},'acquisition_status':'acquired_bounded_geographic_slice','limits':['Not hospital utilization or arrivals.','Age-adjusted prevalence must not be multiplied by local population to construct case counts.','Measures are marginals; joint dependence is unobserved.','Historical ACS 2017-2021 factors are not current ACS 2024 estimates.' if kind=='survey' else 'Release year differs from row reference year; small-area models cannot establish policy effects.'],'provenance':receipt}
    dump(ROOT/'catalog'/f'{sid}.json',catalog)
    print(f'{sid}: {len(rows)} rows, {catalog["scope"]["measure_count"]} measures')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args()
    for source in SOURCES:
        acquire(source,args.offline)
