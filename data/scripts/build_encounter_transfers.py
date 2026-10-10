#!/usr/bin/env python3
"""Build proposals separately from literature evidence; assign no local numerical values."""
import json
from pathlib import Path
D=Path(__file__).resolve().parents[1]
transfers=[]
for p in sorted((D/'research').glob('encounter-*.json')):
 for r in json.loads(p.read_text()):
  if r.get('source_access')=='search_index_only_pending_primary_inspection':continue
  transfers.append({'id':'transfer-'+r['id'],'source_record_ids':[r['id']],'target_scope':'Proposed RWJUH New Brunswick hospital simulation; not observed RWJ practice','status':'inferred_candidate_not_activated','proposal':r['inferred_scenario_use'],'source_basis':r['evidence_basis_type'],'quantitative_use_status':r.get('quantitative_use_status','not_approved'),'assumptions':['Comparable endpoint and patient population must be established.','Staffing, equipment, workflow and period differences may dominate transferability.'],'local_parameter_value':None,'sensitivity_range':{'lower':None,'upper':None,'status':'not_established; no distribution inferred from published summaries'},'replacement_criteria':'Replace with locally reviewed workflow and representative event-level data matching the endpoint, cohort, service and period.','human_review_status':'pending'})
(D/'knowledge/encounter-transfer-candidates.json').write_text(json.dumps({'status':'proposals_only','transfers':transfers},indent=2)+'\n')
print(len(transfers),'separate, inactive transfer proposals')
