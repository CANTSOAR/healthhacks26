#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
D=Path(__file__).resolve().parents[1]
html=(D/'review/index.html').read_text();payload=re.search(r'<script id="evidence" type="application/json">(.*?)</script>',html,re.S).group(1);rows=json.loads(payload)
expected={}
for p in (D/'normalized').glob('*.jsonl'):
 for s in p.read_text().splitlines():
  if s.strip():expected[json.loads(s)['record_id']]=hashlib.sha256(s.encode()).hexdigest()
external=json.loads(re.search(r'<script id="external" type="application/json">(.*?)</script>',html,re.S).group(1))
external_ids=set()
for e in external:
 p=(D/'review'/e['normalized_path']).resolve();assert hashlib.sha256(p.read_bytes()).hexdigest()==e['normalized_sha256']
 erows=[json.loads(line) for line in p.read_text().splitlines() if line.strip()]
 assert len(erows)==e['record_count']
 external_ids.update(r['record_id'] for r in erows)
assert len(rows)+len(external_ids)==len(expected)
assert {r['record_id'] for r in rows}|external_ids==set(expected)
for r in rows:
 assert r['_review']['record_sha256']==expected[r['record_id']]
 for k in ['catalog_path','normalized_path']:
  assert (D/'review'/r['_review'][k]).resolve().is_file()
for name in ['expansion-receipt.json','breadth-receipt.json','inventory-receipt.json','gaps-receipt.json']:
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
transfers=json.loads((D/'knowledge/gap-transfer-candidates.json').read_text())['transfers']
for t in transfers:
 assert t['status']=='inferred_candidate_not_activated'
 assert t['local_parameter_value'] is None
 assert t['human_review_status']=='pending'
 assert all(rid in expected for rid in t['source_record_ids'])
 assert t['sensitivity_range']['lower'] is None and t['sensitivity_range']['upper'] is None
print(f'PASS: {len(rows)} embedded plus {len(external_ids)} on-demand review records match normalized evidence and file links; Luna extract receipt hashes match')
