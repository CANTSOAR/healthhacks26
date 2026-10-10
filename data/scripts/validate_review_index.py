#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
D=Path(__file__).resolve().parents[1]
html=(D/'review/index.html').read_text();payload=re.search(r'<script id="evidence" type="application/json">(.*?)</script>',html,re.S).group(1);rows=json.loads(payload)
expected={}
for p in (D/'normalized').glob('*.jsonl'):
 for s in p.read_text().splitlines():
  if s.strip():expected[json.loads(s)['record_id']]=hashlib.sha256(s.encode()).hexdigest()
assert len(rows)==len(expected)
for r in rows:
 assert r['_review']['record_sha256']==expected[r['record_id']]
 for k in ['catalog_path','normalized_path']:
  assert (D/'review'/r['_review'][k]).resolve().is_file()
for name in ['expansion-receipt.json','breadth-receipt.json']:
 receipt=json.loads((D/'workflows'/name).read_text())
 for j in receipt['jobs']:
  assert hashlib.sha256((D.parent/j['extract_path']).read_bytes()).hexdigest()==j['extract_sha256']
coverage=json.loads((D/'knowledge/encounter-coverage.json').read_text())
for family in coverage['families']:
 assert family['local_validation']=='not_established'
 assert all(rid in expected for rid in family['source_record_ids'])
assert all(rid in expected for rid in coverage['role_evidence_record_ids'])
contract=json.loads((D/'specs/encounter-evidence-contract.json').read_text())
assert all(rid in expected for rid in contract['fracture_example']['source_record_ids'])
print(f'PASS: {len(rows)} review records match normalized evidence and file links; Luna extract receipt hashes match')
