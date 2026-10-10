#!/usr/bin/env python3
"""Acquire bounded public CMS/NPPES snapshots. Standard library only; no credentials.

Run from any directory. Catalogs report completeness only within their query scope.
NPPES raw snapshots are deliberately projected, not verbatim (contact minimization).
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://data.cms.gov/provider-data/api/1/'
FACILITIES = ('310038', '310070')
DATASETS = (
    ('cms-hospital-general-information', 'xubh-q36u', 'Hospital General Information', 'Facility'),
    ('cms-hcahps', 'dgck-syfz', 'Patient survey (HCAHPS) - Hospital', 'QualityMeasureObservation'),
    ('cms-timely-effective-care', 'yv7e-xc69', 'Timely and Effective Care - Hospital', 'QualityMeasureObservation'),
    ('cms-complications-deaths', 'ynj2-r877', 'Complications and Deaths - Hospital', 'QualityMeasureObservation'),
    ('cms-infections', '77hc-ibv8', 'Healthcare Associated Infections - Hospital', 'QualityMeasureObservation'),
    ('cms-unplanned-visits', '632h-zaca', 'Unplanned Hospital Visits - Hospital', 'QualityMeasureObservation'),
    ('cms-facility-affiliations', '27ea-46a8', 'Facility Affiliation Data', 'PractitionerAffiliation'),
)

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def get(url, max_bytes=12_000_000):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'HealthHacks-public-research/1.0'})
            with urllib.request.urlopen(req, timeout=45) as response:
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError('Response exceeds bounded download limit')
                return json.loads(body), body
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))

def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')

def raw_save(slug, suffix, body):
    p = ROOT / 'raw' / f'{slug}-{suffix}.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    return str(p.relative_to(ROOT.parent)), hashlib.sha256(body).hexdigest()

def envelope(slug, kind, row, source_record_id, url, stamp, path, digest):
    return {'record_id': f'{slug}:{source_record_id}', 'source_id': slug,
            'source_record_id': source_record_id, 'record_type': kind, 'data': row,
            'provenance': {'source_url': url, 'retrieved_at': stamp, 'raw_path': path,
                           'raw_sha256': digest},
            'evidence_kind': 'published_observation', 'review_status': 'unreviewed'}

def finish(slug, catalog, records):
    path = ROOT / 'normalized' / f'{slug}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))
    assert len({r['record_id'] for r in records}) == len(records), 'Duplicate record IDs'
    catalog.update(record_count=len(records), normalized_path=str(path.relative_to(ROOT.parent)))
    save_json(ROOT / 'catalog' / f'{slug}.json', catalog)
    print(json.dumps({'source_id': slug, 'record_count': len(records), 'status': catalog['acquisition_status']}), flush=True)

def cms(spec):
    slug, identifier, title, kind = spec
    stamp = now()
    landing = f'https://data.cms.gov/provider-data/dataset/{identifier}'
    cat = {'dataset_id': slug, 'source_id': slug, 'upstream_dataset_id': identifier,
           'title': title, 'source_url': landing, 'raw_paths': [],
           'scope': 'All API rows for CCNs 310038 and 310070; general inventory uses city New Brunswick, NJ (includes additional hospitals).',
           'access': 'public_no_authentication',
           'rights': {'basis': 'Public US federal CMS factual data', 'redistribution': 'public factual government records with attribution', 'source_url': landing},
           'acquisition_status': 'acquired', 'limits': [
               'Historical publication, not live capacity, privileges, staffing or patient-level records.',
               'Preserve source strings, suppression markers, footnotes and measure periods; not all scores share units.',
               'Quality aggregates are not direct per-patient simulation probabilities.'],
           'provenance': {'retrieved_at': stamp}, 'queries': []}
    records = []
    try:
        meta_url = BASE + 'metastore/schemas/dataset/items/' + identifier
        meta, body = get(meta_url)
        path, _ = raw_save(slug, 'metadata', body)
        cat['raw_paths'].append(path)
        cat['provenance'].update(upstream_modified=meta.get('modified'), upstream_released=meta.get('released'), metadata_url=meta_url)
        conditions = [[('citytown', 'NEW BRUNSWICK'), ('state', 'NJ')]] if identifier == 'xubh-q36u' else [[('facility_affiliations_certification_number' if identifier == '27ea-46a8' else 'facility_id', f)] for f in FACILITIES]
        for qi, cond in enumerate(conditions):
            offset = 0
            for page in range(20):
                params = {'limit': 500, 'offset': offset}
                for i, (key, val) in enumerate(cond):
                    params.update({f'conditions[{i}][property]': key, f'conditions[{i}][value]': val, f'conditions[{i}][operator]': '='})
                url = BASE + f'datastore/query/{identifier}/0?' + urllib.parse.urlencode(params)
                result, body = get(url)
                rows = result['results']
                for row in rows:
                    assert all(row[k] == v for k, v in cond), 'API filter not respected'
                path, digest = raw_save(slug, f'query{qi}-page{page}', body)
                cat['raw_paths'].append(path)
                cat['queries'].append({'url': url, 'reported_count': result['count'], 'returned_count': len(rows), 'offset': offset})
                for row in rows:
                    rid = '|'.join(str(row.get(k, '')) for k in ('facility_id', 'npi', 'facility_affiliations_certification_number', 'measure_id', 'hcahps_measure_id', 'start_date', 'end_date'))
                    if rid.strip('|') == '':
                        rid = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:20]
                    records.append(envelope(slug, kind, row, rid, url, stamp, path, digest))
                offset += len(rows)
                if offset >= int(result['count']):
                    break
                if not rows:
                    raise ValueError('Pagination returned empty page before reported count')
            else:
                cat['acquisition_status'] = 'partial'
                cat['limits'].append('20-page cap reached for a facility; not complete.')
    except Exception as exc:
        cat['acquisition_status'] = 'partial' if records else 'failed'
        cat['error'] = str(exc)
    finish(slug, cat, records)

def drg():
    slug = 'cms-inpatient-provider-service-2024'
    stamp = now()
    dataset = 'ca9b5ef0-1386-4759-b2b6-5f9b35116786'
    api = 'https://data.cms.gov/data-api/v1/dataset/' + dataset
    landing = 'https://data.cms.gov/provider-summary-by-type-of-service/medicare-inpatient-hospitals/medicare-inpatient-hospitals-by-provider-and-service'
    cat = {'dataset_id': slug, 'source_id': slug, 'upstream_dataset_id': dataset,
           'title': 'Medicare Inpatient Hospitals - by Provider and Service (2024)', 'source_url': landing,
           'scope': '2024 Original Medicare fee-for-service Part A IPPS discharges; CCNs 310038 and 310070; all publicly released DRGs within this scope.',
           'access': 'public_no_authentication', 'rights': {'basis': 'CMS catalog distribution license', 'source_url': 'https://www.usa.gov/government-works', 'redistribution': 'public US government factual data'},
           'acquisition_status': 'acquired', 'raw_paths': [], 'queries': [],
           'provenance': {'retrieved_at': stamp, 'data_period': {'start': '2024-01-01', 'end': '2024-12-31'}, 'upstream_modified': '2026-04-23'},
           'limits': ['Fee-for-service Medicare Part A IPPS population only; not all-payer case mix or New Brunswick resident prevalence.',
                      'Provider-DRG rows with 10 or fewer discharges are suppressed; retained rows do not sum to total all-hospital demand.',
                      'Charges, total payments and Medicare payments are different quantities, not hospital costs or patient liability.',
                      'DRGs are payment/case groupings, not complete procedure pathways or clinical indications.']}
    records = []
    try:
        dictionary, body = get(api + '/dictionary')
        path, _ = raw_save(slug, 'dictionary', body)
        cat['raw_paths'].append(path)
        for ccn in FACILITIES:
            offset = 0
            for page in range(10):
                url = api + '/data?' + urllib.parse.urlencode({'filter[Rndrng_Prvdr_CCN]': ccn, 'size': 500, 'offset': offset})
                rows, body = get(url)
                assert isinstance(rows, list) and all(r['Rndrng_Prvdr_CCN'] == ccn for r in rows)
                path, digest = raw_save(slug, f'{ccn}-page{page}', body)
                cat['raw_paths'].append(path)
                cat['queries'].append({'url': url, 'returned_count': len(rows), 'offset': offset})
                for row in rows:
                    rid = ccn + '|2024|' + row['DRG_Cd']
                    records.append(envelope(slug, 'UtilizationObservation', row, rid, url, stamp, path, digest))
                if len(rows) < 500:
                    break
                offset += len(rows)
            else:
                cat['acquisition_status'] = 'partial'
                cat['limits'].append('10-page cap reached.')
    except Exception as exc:
        cat.update(acquisition_status='partial' if records else 'failed', error=str(exc))
    finish(slug, cat, records)

def nppes():
    slug = 'nppes-new-brunswick-practitioners'
    stamp = now()
    url = 'https://npiregistry.cms.hhs.gov/api/?' + urllib.parse.urlencode({'version': '2.1', 'city': 'New Brunswick', 'state': 'NJ', 'enumeration_type': 'NPI-1', 'limit': 200, 'skip': 0})
    cat = {'dataset_id': slug, 'source_id': slug, 'title': 'NPPES New Brunswick individual practitioner sample', 'source_url': url,
           'scope': 'First 200 NPI-1 city-search results only; not exhaustive and not hospital affiliation evidence.',
           'access': 'public_no_authentication', 'rights': {'basis': 'CMS public NPI Registry factual records', 'redistribution': 'minimized professional fields only', 'source_url': 'https://npiregistry.cms.hhs.gov/api-page'},
           'acquisition_status': 'partial', 'raw_paths': [],
           'limits': ['API sample capped at 200, not total population.', 'NPI registration is not verification of licensing, credentials, privileges, employment or availability.', 'Raw file is a documented projection: mailing/street addresses, telephone, fax, personal demographics, license numbers and alternate identifiers removed before persistence.'],
           'provenance': {'retrieved_at': stamp}, 'queries': [{'url': url}]}
    records = []
    try:
        response, _ = get(url)
        selected = []
        for r in response['results']:
            basic = r.get('basic', {})
            selected.append({'npi': r['number'], 'enumeration_type': r['enumeration_type'],
                'name': {k: basic[k] for k in ('first_name', 'middle_name', 'last_name', 'name_prefix', 'name_suffix', 'credential') if k in basic},
                'status': basic.get('status'), 'last_updated': basic.get('last_updated'),
                'taxonomies': [{k:t[k] for k in ('code','desc','primary') if k in t} for t in r.get('taxonomies', [])],
                'practice_locations': [{k:a[k] for k in ('city','state','country_code') if k in a} for a in r.get('addresses', []) if a.get('address_purpose') == 'LOCATION']})
        projection = {'source_url': url, 'retrieved_at': stamp, 'transformation': 'professional identity/taxonomy/city projection; not a verbatim response', 'result_count': response['result_count'], 'results': selected}
        body = (json.dumps(projection, indent=2) + '\n').encode()
        path, digest = raw_save(slug, 'projected-response', body)
        cat['raw_paths'].append(path)
        cat['returned_count'] = len(selected)
        records = [envelope(slug, 'Practitioner', r, r['npi'], url, stamp, path, digest) for r in selected]
    except Exception as exc:
        cat.update(acquisition_status='failed', error=str(exc))
    finish(slug, cat, records)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=[d[0] for d in DATASETS] + ['nppes-new-brunswick-practitioners', 'cms-inpatient-provider-service-2024'])
    args = parser.parse_args()
    for spec in DATASETS:
        if args.only is None or args.only == spec[0]:
            cms(spec)
    if args.only is None or args.only == 'nppes-new-brunswick-practitioners':
        nppes()
    if args.only is None or args.only == 'cms-inpatient-provider-service-2024':
        drg()

    selected = [args.only] if args.only else [d[0] for d in DATASETS] + ["nppes-new-brunswick-practitioners", "cms-inpatient-provider-service-2024"]
    failures = [sid for sid in selected if (lambda m: m.get("error") or m.get("acquisition_status") == "failed")(json.loads((ROOT / "catalog" / (sid + ".json")).read_text()))]
    if failures:
        raise SystemExit("Acquisition incomplete: " + ", ".join(failures))
