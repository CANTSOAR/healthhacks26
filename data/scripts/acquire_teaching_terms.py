#!/usr/bin/env python3
"""Acquire CC-BY synthetic teaching profiles and small NLM drug-identity responses."""
import argparse, hashlib, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
REV='ee5c260a6e24cd9d6baf5c0ab7ec636788c64c70'
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'HealthHacksResearch/0.1 (bounded academic data acquisition)'})
    with urllib.request.urlopen(req,timeout=40) as response:
        content=response.read(5_000_001)
    if len(content)>5_000_000: raise ValueError('Source exceeds bounded 5MB limit')
    return content

def save(slug,title,urls,objects,raw,rights,scope,record_type,evidence_kind):
    now=datetime.now(timezone.utc).isoformat(); paths=[]
    for filename,content in raw.items():
        p=BASE/'raw'/slug/filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content);paths.append(str(p.relative_to(BASE)))
    records=[]
    primary=next(iter(raw.values()));digest=hashlib.sha256(primary).hexdigest()
    for i,obj in enumerate(objects):
        records.append({'record_id':f'{slug}:{i+1:04d}','source_id':slug,'source_record_id':str(i+1),'record_type':record_type,'data':obj,'provenance':{'source_url':urls[0],'retrieved_at':now,'raw_sha256':digest},'evidence_kind':evidence_kind,'review_status':'unreviewed'})
    p=BASE/'normalized'/f'{slug}.jsonl';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
    manifest={'dataset_id':slug,'source_id':slug,'title':title,'source_url':urls[0],'source_urls':urls,'record_count':len(records),'raw_paths':paths,'raw_sha256':{f:hashlib.sha256((BASE/f).read_bytes()).hexdigest() for f in paths},'normalized_path':str(p.relative_to(BASE)),'scope':scope,'access':'public','rights':rights,'acquisition_status':'acquired','retrieved_at':now,'limits':['Identity or synthetic teaching data only; not clinical approval, prescribing guidance or hospital calibration.'],'provenance':{'method':'HTTP source download; deterministic normalization','script':'scripts/acquire_teaching_terms.py'}}
    p=BASE/'catalog'/f'{slug}.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    return len(records)

def profiles():
    base=f'https://huggingface.co/datasets/joeljames270/virtual-patient-profiles-sample/resolve/{REV}/'
    card=fetch(base+'README.md')
    if b'license: cc-by-4.0' not in card:raise ValueError('Expected explicit CC-BY-4.0 dataset license absent')
    raw=fetch(base+'patients.jsonl');text=raw.decode();decoder=json.JSONDecoder();items=[];pos=0
    while pos<len(text):
        while pos<len(text) and text[pos].isspace():pos+=1
        if pos==len(text):break
        obj,pos=decoder.raw_decode(text,pos);items.append(obj)
    assert len(items)==8
    return save('twinverse-patient-profiles','Rutgers VHS synthetic nutrition patient profiles',[base+'patients.jsonl',base+'README.md'],items,{'patients.source.jsonl':raw,'README.source.md':card}, {'license':'CC-BY-4.0','attribution':'VHS (Virtual Human Simulation) project at Rutgers University, joeljames270/virtual-patient-profiles-sample','revision':REV,'changes':'Concatenated pretty-printed JSON decoded into one-record-per-line envelopes; clinical content unmodified.'},'Eight synthetic teaching profiles; generated inconsistencies and faculty review pending.','SyntheticPatientProfile','synthetic')

def terms():
    names=['metformin','lisinopril','atorvastatin','furosemide','insulin glargine','albuterol','aspirin','acetaminophen']
    from urllib.parse import urlencode
    now=datetime.now(timezone.utc).isoformat();records=[];raw={};urls=[]
    for name in names:
        url='https://rxnav.nlm.nih.gov/REST/rxcui.json?'+urlencode({'name':name,'search':2})
        content=fetch(url);value=json.loads(content);filename=name.replace(' ','-')+'.json';raw[filename]=content;urls.append(url)
        records.append({'queried_name':name,'rxnorm_ids':value.get('idGroup',{}).get('rxnormId',[]),'match_method':'RxNorm search=2 (exact then normalized); inspect concepts before clinical use'})
    count=save('nlm-rxnorm-seed-terms','NLM RxNorm preliminary drug identity lookup',urls,records,raw,{'license':'NLM RxNorm API public access','terms_url':'https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html','scope':'Bounded NLM identifier lookup responses; no proprietary third-party drug vocabulary content requested.'},'Eight teaching-relevant name queries; not a formulary, medication order or interaction dataset.','TerminologyLookup','published_reference')
    p=BASE/'normalized'/'nlm-rxnorm-seed-terms.jsonl'
    output=[]
    for i,line in enumerate(p.read_text().splitlines()):
        r=json.loads(line);content=list(raw.values())[i];r['provenance']['source_url']=urls[i];r['provenance']['raw_sha256']=hashlib.sha256(content).hexdigest();output.append(r)
    p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in output));return count
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--only',choices=['profiles','terms','all'],default='all');args=parser.parse_args()
    for key,fn in [('profiles',profiles),('terms',terms)]:
        if args.only in ('all',key):
            try:print(json.dumps({'dataset':key,'record_count':fn(),'status':'acquired'}))
            except Exception as e:print(json.dumps({'dataset':key,'status':'failed','error':str(e)}));raise
