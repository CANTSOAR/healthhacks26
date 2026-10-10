#!/usr/bin/env python3
"""Rebuild source envelopes and explicit provisional transfers from retained evidence."""
import hashlib,json,re,xml.etree.ElementTree as ET
from pathlib import Path
D=Path(__file__).resolve().parents[1]
STAMP='2026-10-10T16:00:17.079781+00:00'  # Initial extraction timestamp; offline rebuild preserves it.
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def emit(sid,title,url,items,raw=None,rights=None,doi=None):
    records=[]
    for key,data,kind,locator in items:
        prov={'source_url':url,'retrieved_at':STAMP,'raw_sha256':hashlib.sha256(raw.read_bytes()).hexdigest() if raw else None,'locator':locator,'acquisition_method':'licensed fulltext table extraction' if raw else 'limited factual paraphrase of primary paper inspected by research agent'}
        if raw:prov['raw_path']=str(raw.relative_to(D.parent))
        records.append({'record_id':key,'source_id':sid,'source_record_id':key,'record_type':'LiteratureEvidence','data':data,'provenance':prov,'evidence_kind':kind,'review_status':'source_extracted_not_locally_validated'})
    path=D/'normalized'/f'{sid}.jsonl';path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
    write(D/'catalog'/f'{sid}.json',{'dataset_id':sid,'source_id':sid,'title':title,'source_url':url,'scope':'External hospital literature; not New Brunswick observations','access':'public','rights':rights or {'redistribution':'Limited factual paraphrases only; full article not redistributed','source_license':'not assessed for full-text redistribution'},'acquisition_status':'acquired','raw_paths':[str(raw.relative_to(D.parent))] if raw else [],'normalized_path':str(path.relative_to(D.parent)),'record_count':len(records),'limits':['External setting and historical period; transfer to target simulation requires an explicit inference.','Published estimates and observed outcomes retain their distinct evidence basis.'],'provenance':{'retrieved_at':STAMP,'doi':doi,'raw_artifact_kind':'original_downloaded_response_bytes' if raw else 'no_raw_limited_paraphrase'}})
    return records
raw=D/'raw/lit-gabriel-2020/article.xml'
r=ET.fromstring(raw.read_bytes());table=r.find(".//table-wrap[@id='table-2']")
roles=['triage_nurse','registration','ed_nurse','physician','admin','porter'];items=[]
for tr in table.findall('.//tr')[2:]:
    cells=[''.join(c.itertext()) for c in tr];name=cells[0];key='gabriel-2020-'+re.sub('[^a-z0-9]+','-',name.lower()).strip('-')
    items.append((key,{'task':name,'process_time_notation':cells[1],'unit':'minutes','staff_markings':dict(zip(roles,cells[2:])),'table_notes':' '.join(table.find('table-wrap-foot').itertext()) if table.find('table-wrap-foot') is not None else None,'source_setting':'Cape Breton Regional Hospital, Canada','source_period':'Arrival database April 2017–March 2018; process timing elicitation dates not separately established','source_evidence_basis':'Delphi estimates from ED manager and nurses; not fitted observed service-time distributions','doi':'10.7717/peerj-cs.284'},'published_expert_estimate','Table 2: '+name))
title='Lean thinking by integrating with discrete event simulation and design of experiments: an emergency department expansion'
authors=[' '.join(x.itertext()) for x in r.findall('.//contrib-group/contrib/name')]
records=emit('lit-gabriel-2020',title,'https://doi.org/10.7717/peerj-cs.284',items,raw,{'source_license':'CC BY 4.0','attribution':'; '.join(authors)+'. '+title+'. PeerJ Computer Science 6:e284 (2020). https://doi.org/10.7717/peerj-cs.284','redistribution':'Licensed article XML retained; normalized table is an adaptation'},'10.7717/peerj-cs.284')
for name in ['flow','interaction']:
    extracts=json.loads((D/'research'/f'literature-{name}-extracts.json').read_text());groups={}
    for x in extracts:groups.setdefault(x['source_url'],[]).append(x)
    for url,xs in groups.items():
        sid='lit-'+xs[0]['id'].split('-')[0]+'-'+xs[0]['id'].split('-')[1]
        emit(sid,xs[0]['source_title'],url,[(x['id'],x,'external_published_finding',x['locator']) for x in xs],doi=xs[0]['doi'])
proxies=[]
for task in ['Triage','Physician Assessment','Take Specimen']:
    src=next(x for x in records if x['data']['task']==task);nums=list(map(float,re.findall(r'[\d.]+',src['data']['process_time_notation'])))
    proxies.append({'parameter_id':'proxy-'+src['record_id'],'quantity':task+' service duration','unit':'minutes','source_record_ids':[src['record_id']],'source_evidence_basis':'published_expert_estimate','role':'process_input','status':'provisional_external_proxy','target_scope':'Generic exploratory ED, potentially New Brunswick-inspired; not a measured local model','model':{'family':'triangular','minimum':nums[0],'mode':nums[1],'maximum':nums[2]},'inference':'Analyst interprets T(a,b,c) as triangular(minimum, mode, maximum); that parameterization was not explicitly defined in inspected article text. Transfers Canadian staff estimates to an illustrative ED; not a fitted local duration.','uncertainty':{'sensitivity_multipliers':[0.5,1,2],'basis':'Analyst-chosen stress tests, not confidence intervals or published uncertainty'},'replace_when':'Local time-motion observations or better context-matched duration distributions are available','permitted_use':'exploratory simulation only'})
write(D/'knowledge/provisional-parameters.json',{'version':1,'parameters':proxies,'output_comparator_record_ids':['jones-evans-2008-observed-door-provider','krall-2014-door-room-and-throughput','krall-2014-admit-decision-to-depart','houston-2015-arrival-triage'],'comparator_rule':'Waiting and boarding times are outcomes for comparison, not service durations to add to queues. Preserve conditional populations and daily versus patient aggregation.','scenario_evidence_path':'data/research/literature-interaction-extracts.json','scenario_rule':'Communication findings motivate authored variations; prevalence is not automatically a scenario probability.'})
print('Built',len(items),'timing rows, 10 literature findings, 3 provisional parameters')
