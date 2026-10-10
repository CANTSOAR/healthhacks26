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
for name in ['expansion-receipt.json','breadth-receipt.json','inventory-receipt.json','gaps-receipt.json','specialty-receipt.json','encounter-receipt.json','model-receipt.json','calibration-receipt.json']:
 receipt=json.loads((D/'workflows'/name).read_text())
 for j in receipt['jobs']:
  assert hashlib.sha256((D.parent/j['extract_path']).read_bytes()).hexdigest()==j['extract_sha256']
audit=json.loads((D/'workflows/specialty-receipt.json').read_text())['insurance_audit']
assert hashlib.sha256((D.parent/audit['path']).read_bytes()).hexdigest()==audit['sha256']
coverage=json.loads((D/'knowledge/encounter-coverage.json').read_text())
for family in coverage['families']:
 assert family['local_validation']=='not_established'
 assert all(rid in expected for rid in family['source_record_ids'])
assert all(rid in expected for rid in coverage['role_evidence_record_ids'])
contract=json.loads((D/'specs/encounter-evidence-contract.json').read_text())
assert all(rid in expected for rid in contract['fracture_example']['source_record_ids'])
for transfer_path in ['gap-transfer-candidates.json','specialty-transfer-candidates.json','encounter-transfer-candidates.json','model-transfer-candidates.json','calibration-transfer-candidates.json']:
 transfers=json.loads((D/'knowledge'/transfer_path).read_text())['transfers']
 for t in transfers:
  assert t['status']=='inferred_candidate_not_activated'
  assert t['local_parameter_value'] is None
  assert t['human_review_status']=='pending'
  assert all(rid in expected for rid in t['source_record_ids'])
  assert t['sensitivity_range']['lower'] is None and t['sensitivity_range']['upper'] is None
readiness=json.loads((D/'knowledge/full-encounter-readiness.json').read_text())
assert readiness['status']=='proposed_encounter_coverage_not_runnable_or_clinically_approved'
assert len(readiness['stages'])==10
for stage in readiness['stages']:
 assert stage['duration_distribution'] is None
 assert stage['local_validation']=='not_established'
 assert all(rid in expected for rid in stage['source_record_ids'])
encounter_transfers=json.loads((D/'knowledge/encounter-transfer-candidates.json').read_text())['transfers']
conflict=next(t for t in encounter_transfers if t['source_record_ids']==['encounter-communication-radiology-acknowledgement'])
assert conflict['quantitative_use_status'].startswith('blocked_source_internal_inconsistency')
arrival=json.loads((D/'research/encounter-arrival.json').read_text())
monitor=next(r for r in arrival if r['id']=='encounter-arrival-waiting-area-monitoring-feasibility')
assert monitor['value']['median_monitoring_minutes_per_patient']==178
assert 'median_monitoring_hours_per_patient' not in monitor['value']
print(f'PASS: {len(rows)} embedded plus {len(external_ids)} on-demand review records match normalized evidence and file links; Luna extract receipt hashes match')

requirements=json.loads((D/'knowledge/model-requirement-candidates.json').read_text())
assert requirements['status']=='proposed_requirements_not_executable_simulation'
for r in requirements['requirements']:
 assert all(i in expected for i in r['source_record_ids'])
 assert r['activation_status']=='blocked_pending_human_and_local_review'
 assert all(r[k] is None for k in ['local_capacity','duration_distribution','branch_probability'])
model_transfers=json.loads((D/'knowledge/model-transfer-candidates.json').read_text())['transfers']
for rid in ['model-timing-rio-simulation-triage-fit','model-timing-rio-simulation-consultation-fit']:
 assert next(t for t in model_transfers if t['source_record_ids']==[rid])['quantitative_use_status'].startswith('blocked_')
assert 'model-branches-capable-adult-declines-recommendation' not in expected
print('PASS: inactive model requirements, source links, unresolved timing blocks and pending-source exclusion')

calibration=[]
for p in (D/'research').glob('calibration-*.json'):
 calibration.extend(json.loads(p.read_text()))
byid={r['id']:r for r in calibration}
assert all(r['applicability_label']=='external_reference_not_RWJ' for r in calibration)
assert all('index' not in r['source_access'].lower() or r['source_access']=='search_index_only_pending_primary_inspection' for r in calibration)
def validate_counts(value):
 if isinstance(value,dict):
  n,N=value.get('numerator'),value.get('denominator')
  if isinstance(n,(int,float)) and isinstance(N,(int,float)):assert 0 <= n <= N and N > 0
  for x in value.values():validate_counts(x)
 elif isinstance(value,list):
  for x in value:validate_counts(x)
for r in calibration:validate_counts(r['value'])
completion=byid['calibration-branches-mri-completion']['value']
assert sum(x['numerator'] for x in completion.values())==258
assert all(x['denominator']==258 for x in completion.values())
assert byid['calibration-branches-negative-xray-ct-negative-mri-yield']['quantitative_use_status'].startswith('blocked_')
assert byid['calibration-timing-rio-triage-expression-conflict']['quantitative_use_status'].startswith('blocked_')
for r in json.loads((D/'research/model-timing.json').read_text()):
 for rid in r.get('correction_record_ids',[]):assert rid in expected
print('PASS: calibration count bounds, access status, source corrections and unresolved quantitative blocks')

transfers=json.loads((D/'knowledge/calibration-transfer-candidates.json').read_text())['transfers']
for r in calibration:
 if r.get('quantitative_use_status','').startswith('blocked_'):
  assert next(t for t in transfers if t['source_record_ids']==[r['id']])['quantitative_use_status']==r['quantitative_use_status']
print('PASS: all calibration quantitative blocks propagate into transfer proposals')
