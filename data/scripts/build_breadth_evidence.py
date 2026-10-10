#!/usr/bin/env python3
"""Normalize inspected Luna literature extracts, retaining source-specific limitations."""
import hashlib,json
from pathlib import Path
from datetime import datetime
D=Path(__file__).resolve().parents[1]
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
groups={};ids=set();jobs=[]
for domain in ['pathways','roles','ehr-training','administration']:
 p=D/'research'/f'breadth-{domain}.json';xs=json.loads(p.read_text())
 for x in xs:
  for key in ['id','source_title','source_url','locator','source_setting','source_period','source_n','quantity','value','unit','source_evidence_basis','limitations','inferred_scenario_use','retrieved_at']:assert key in x,(p,key)
  assert x['id'] not in ids;ids.add(x['id']);assert datetime.fromisoformat(x['retrieved_at'].replace('Z','+00:00')).tzinfo
  x['research_domain']=domain;groups.setdefault(x['source_url'],[]).append(x)
 jobs.append({'domain':domain,'agent_model':'root' if domain=='administration' else 'gpt-6-luna','status':'completed','extract_path':str(p.relative_to(D.parent)),'extract_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'record_count':len(xs)})
for url,xs in groups.items():
 sid='breadth-'+hashlib.sha256(url.encode()).hexdigest()[:12];rs=[]
 for x in xs:
  rs.append({'record_id':x['id'],'source_id':sid,'source_record_id':x['id'],'record_type':'SourceEvidence','data':x,'provenance':{'source_url':url,'retrieved_at':x['retrieved_at'],'locator':x['locator'],'raw_sha256':None,'acquisition_method':'limited factual paraphrase from primary source inspected by research agent; source location retained'},'evidence_kind':'published_guidance_workflow_or_study','review_status':'agent_extracted_pending_human_review','limitations':[x['limitations'],'Proposed scenario use is an inference; local applicability must be assessed separately from the source finding.']})
 np=D/'normalized'/f'{sid}.jsonl';np.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rs))
 write(D/'catalog'/f'{sid}.json',{'dataset_id':sid,'source_id':sid,'title':xs[0]['source_title'],'source_url':url,'scope':'Primary guidance, workflow, source-code documentation or study; limited factual extracts, not a complete validated pathway','access':'public_primary_article_or_abstract','rights':{'source_license':'not assessed for full-text redistribution','redistribution':'Short factual paraphrases; no full article copied'},'acquisition_status':'acquired','raw_paths':[],'normalized_path':str(np.relative_to(D.parent)),'record_count':len(rs),'limits':['Setting, period, applicability and endpoint are source-specific.','No original snapshot retained; human review should follow source URL and locator.','A role description or guideline does not establish local operational performance.'],'provenance':{'doi':xs[0].get('doi'),'retrieved_at':xs[0]['retrieved_at'],'raw_artifact_kind':'no_raw_limited_paraphrase'}})
write(D/'workflows/breadth-receipt.json',{'campaign':'hospital-encounter-breadth-2026-10-10','execution':'Three requested Luna collaboration agents plus root administrative-source research; finite pass','jobs':jobs,'sources_added':len(groups),'records_added':len(ids),'status':'completed_extraction_not_human_approved','next_step':'Human source comparison in data/review/index.html; priority review all operational parameters before adoption'})
print(len(groups),'sources;',len(ids),'records')
