#!/usr/bin/env python3
"""Reproduce selected first-wave observations without turning them into parameters."""
import json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
rows={r['record_id']:r for p in (BASE/'normalized').glob('*.jsonl') for line in p.read_text().splitlines() if line.strip() for r in [json.loads(line)]}
facts=[]
for rid,r in rows.items():
 d=r['data'];s=r['source_id'];include=False
 if s=='cms-timely-effective-care' and d.get('measure_id')=='OP_18b':include=True
 if s=='cms-hcahps' and d.get('hcahps_measure_id')=='H_COMP_2_A_P':include=True
 if s=='cms-inpatient-provider-service-2024' and d.get('DRG_Cd') in ['871','291']:include=True
 if s in ['local-cdc-places-new-brunswick-2025','local-cdc-places-middlesex-2025'] and d.get('estimate_type')=='Crude prevalence' and any(v in d.get('measure','').lower() for v in ['insurance','food insecurity','transport']):include=True
 if include:facts.append({'record_id':rid,'source_id':s,'data':d,'interpretation_status':'source_observation_not_simulation_parameter'})
(BASE/'analysis/baseline-facts.json').write_text(json.dumps({'scope':'Selected unchanged first-wave observations; exact record IDs resolve to sources/record-citations.jsonl','facts':facts},indent=2)+'\n')
print('Selected',len(facts),'source observations')
