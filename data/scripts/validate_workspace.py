#!/usr/bin/env python3
"""Check acquired evidence, source integrity and candidate citation closure offline."""
import hashlib,json
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from jsonschema import Draft202012Validator, FormatChecker
BASE=Path(__file__).resolve().parents[1]
def check(ok,message):
    if not ok: raise ValueError(message)
def resolve(path):
    p=(BASE.parent/path if path.startswith('data/') else BASE/path).resolve()
    check(p.is_relative_to(BASE.resolve()), f'Path escapes workspace: {path}')
    return p
def rows(p): return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def main():
    schema=json.loads((BASE/'ontology/schemas/normalized-record.schema.json').read_text())
    validator=Draft202012Validator(schema,format_checker=FormatChecker())
    ids=set();counts={};no_snapshot=0;raw_count=0
    for p in sorted((BASE/'catalog').glob('*.json')):
        m=json.loads(p.read_text());sid=m['source_id'];rs=rows(resolve(m['normalized_path']))
        check(not m.get('error') and m.get('acquisition_status') != 'failed', f'{sid}: acquisition failed')
        check(len(rs)==m['record_count'], f'{sid}: count mismatch')
        check(m.get('rights') and m.get('limits'), f'{sid}: missing rights/limits')
        hashes={}
        for raw in m['raw_paths']:
            digest=hashlib.sha256(resolve(raw).read_bytes()).hexdigest();hashes[raw]=digest;raw_count+=1
            expected=m.get('raw_sha256',{}).get(raw)
            if expected: check(digest==expected,f'{raw}: manifest hash mismatch')
        for r in rs:
            validator.validate(r);rid=r['record_id'];check(rid not in ids,f'Duplicate ID: {rid}');ids.add(rid)
            check(r['source_id']==sid,f'{rid}: wrong source')
            prov=r['provenance'];check(urlparse(prov['source_url']).scheme in ('https','http'),f'{rid}: bad URL')
            check(datetime.fromisoformat(prov['retrieved_at'].replace('Z','+00:00')).tzinfo is not None,f'{rid}: missing timezone')
            if prov['raw_sha256'] is None:
                no_snapshot+=1
                check('paraphrase' in prov.get('acquisition_method',''),f'{rid}: undocumented missing snapshot')
                check(bool(r['data'].get('locator') or prov.get('locator')),f'{rid}: missing source locator')
            else: check(prov['raw_sha256'] in hashes.values(),f'{rid}: source hash does not resolve to acquired snapshot')
        counts[sid]=len(rs)
    citations=BASE/'sources/record-citations.jsonl'
    if citations.exists():
        indexed={r['record_id'] for r in rows(citations)}
        check(indexed==ids,'Citation index stale or incomplete')
    runs=0
    for p in (BASE/'runs').glob('*/receipt.json'):
        receipt=json.loads(p.read_text())
        if receipt.get('status')!='completed':continue
        candidate=json.loads((p.parent/'candidate.json').read_text())
        Draft202012Validator(json.loads((BASE/'workflows/response.schema.json').read_text())).validate(candidate)
        packet=json.loads((p.parent/'packet.json').read_text())
        check(hashlib.sha256((p.parent/'packet.json').read_bytes()).hexdigest()==receipt['packet_sha256'], 'Run input packet hash mismatch')
        supplied={r['record_id'] for r in packet['records']}
        check(supplied==set(receipt['input_record_ids']), 'Run input ID receipt mismatch')
        for finding in candidate['findings']:
            for rid in finding['source_record_ids']:
                check(rid in ids and rid in supplied,f'Candidate cites unknown or unsupplied record: {rid}')
        runs+=1
    print(json.dumps({'status':'passed','datasets':len(counts),'records':sum(counts.values()),'raw_files':raw_count,'limited_paraphrases_without_raw':no_snapshot,'completed_luna_runs':runs,'counts':counts},indent=2))
if __name__=='__main__':main()
