#!/usr/bin/env python3
"""Bounded GPT-6 Luna candidate review via authenticated Codex CLI.
No API key is loaded; uses the user's existing Codex authentication.
No output is promoted automatically. Raw CLI traces are ignored by Git.
"""
import argparse, hashlib, json, os, signal, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
import jsonschema
BASE=Path(__file__).resolve().parents[1]
def select_records(job):
    groups=[]
    for p in sorted((BASE/'normalized').glob('*.jsonl')):
        if job['source_prefixes'] and not any(p.stem.startswith(s) for s in job['source_prefixes']):continue
        rows=[json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        if rows:groups.append(rows)
    records=[];index=0;budget=65_000
    while groups and len(records)<job['max_records']:
        progressed=False
        for group in groups:
            if index<len(group):
                row=group[index];size=len(json.dumps(row))
                if size>budget:continue
                records.append(row);budget-=size;progressed=True
                if len(records)>=job['max_records']:break
        if not progressed:break
        index+=1
    if not records:raise ValueError('No acquired records match job')
    return records

def main():
    ap=argparse.ArgumentParser();ap.add_argument('job',nargs='?',default='baseline-evidence-review');ap.add_argument('--execute',action='store_true');ap.add_argument('--timeout',type=int,default=240);args=ap.parse_args()
    if not 10<=args.timeout<=600:ap.error('timeout must be 10..600 seconds')
    spec=json.loads((BASE/'workflows/luna-jobs.json').read_text());job=next((j for j in spec['jobs'] if j['id']==args.job),None)
    if job is None:ap.error('Unknown job')
    records=select_records(job);packet={'job':job,'records':records};packet_text=json.dumps(packet,ensure_ascii=False,indent=2)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');run_id=stamp+'-'+job['id'];out=BASE/'runs'/run_id;out.mkdir(parents=True,exist_ok=False)
    (out/'packet.json').write_text(packet_text+'\n');model=spec['model'];result=out/'candidate.json'
    cmd=['codex','exec','--ignore-user-config','--ephemeral','--sandbox','read-only','--model',model,'-c','model_reasoning_effort="medium"','--json','--output-schema',str(BASE/'workflows/response.schema.json'),'--output-last-message',str(result),'--cd',str(BASE),'-']
    receipt={'run_id':run_id,'job_id':job['id'],'requested_model':model,'runner':'codex_cli','packet_sha256':hashlib.sha256((packet_text+'\n').encode()).hexdigest(),'input_record_ids':[r['record_id'] for r in records],'started_at':datetime.now(timezone.utc).isoformat(),'status':'prepared','candidate_review_status':'unreviewed','command_template':'codex exec --ignore-user-config --ephemeral --sandbox read-only --model gpt-6-luna --output-schema workflows/response.schema.json --output-last-message <candidate> --cd <data> -'}
    def save(): (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    save()
    if not args.execute:print(json.dumps({'status':'prepared','run_path':str(out.relative_to(BASE)),'records':len(records)}));return
    private=BASE/'runs/private';private.mkdir(exist_ok=True);prompt=(BASE/'workflows/prompts/evidence-review.md').read_text()+'\n\nSOURCE PACKET:\n'+packet_text
    start=time.monotonic()
    with (private/(run_id+'.stdout.jsonl')).open('w') as stdout,(private/(run_id+'.stderr.log')).open('w') as stderr:
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,text=True,start_new_session=True)
        try:
            proc.communicate(prompt,timeout=args.timeout);receipt['exit_code']=proc.returncode
            if proc.returncode or not result.exists():
                receipt['status']='failed';receipt['error']='CLI did not produce a candidate; inspect local ignored trace.'
            else:
                data=json.loads(result.read_text());jsonschema.validate(data,json.loads((BASE/'workflows/response.schema.json').read_text()))
                allowed=set(receipt['input_record_ids']);unknown=sorted({rid for f in data['findings'] for rid in f['source_record_ids']} - allowed)
                if unknown:raise ValueError('Candidate cites unknown record IDs: '+','.join(unknown))
                receipt['status']='completed';receipt['validation']={'response_schema':'passed','citation_ids':'passed','semantic_support':'requires human/independent review'}
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            receipt['status']='timed_out';receipt['error']='Bounded runtime exceeded; process group terminated.'
        except Exception as exc:receipt['status']='validation_failed';receipt['error']=str(exc)
    receipt['duration_seconds']=round(time.monotonic()-start,3);receipt['finished_at']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({'status':receipt['status'],'run_path':str(out.relative_to(BASE)),'records':len(records),'duration_seconds':receipt['duration_seconds']}))
    if receipt['status']!='completed':sys.exit(1)
if __name__=='__main__':main()
