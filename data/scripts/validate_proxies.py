#!/usr/bin/env python3
"""Check that adopted external parameters have evidence and explicit transfer semantics."""
import json
from pathlib import Path
D=Path(__file__).resolve().parents[1]
records={r['record_id']:r for p in (D/'normalized').glob('*.jsonl') for s in p.read_text().splitlines() if s.strip() for r in [json.loads(s)]}
x=json.loads((D/'knowledge/provisional-parameters.json').read_text())
assert len({p['parameter_id'] for p in x['parameters']})==len(x['parameters'])
for p in x['parameters']:
    assert p['status']=='provisional_external_proxy' and p['inference'] and p['replace_when']
    assert p['role']=='process_input' and p['unit']=='minutes'
    assert p['permitted_use']=='exploratory simulation only'
    for rid in p['source_record_ids']:
        assert rid in records and records[rid]['evidence_kind']==p['source_evidence_basis']
        assert rid not in x['output_comparator_record_ids']
    m=p['model'];assert 0<=m['minimum']<=m['mode']<=m['maximum']
    assert 'not confidence' in p['uncertainty']['basis']
for rid in x['output_comparator_record_ids']:assert rid in records
print(f"Passed: {len(x['parameters'])} explicit external proxies and {len(x['output_comparator_record_ids'])} separate output comparators")
