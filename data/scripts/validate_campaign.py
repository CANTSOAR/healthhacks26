#!/usr/bin/env python3
"""Verify finite discovery run receipts, saved prompts, schema and observed web activity."""
import hashlib,json
from pathlib import Path
from jsonschema import Draft202012Validator
BASE=Path(__file__).resolve().parents[1]
def require(ok,msg):
 if not ok:raise ValueError(msg)
def main():
 schema=Draft202012Validator(json.loads((BASE/'workflows/campaigns/avenues.schema.json').read_text()))
 totals={'campaigns':0,'jobs':0,'completed':0,'source_candidates':0,'candidate_urls_not_observed_in_web_results':0}
 for root in sorted((BASE/'runs').glob('avenues-*')):
  manifest=json.loads((root/'manifest.json').read_text());summary=json.loads((root/'summary.json').read_text());index=json.loads((root/'discovery-index.json').read_text())
  jobs=manifest['jobs'];require(summary['jobs_finished']==len(jobs),'Campaign still unfinished')
  require(len(index['jobs'])==len(jobs),'Discovery index missing jobs')
  completed=0
  for job in jobs:
   d=root/job['domain_id'];r=json.loads((d/'receipt.json').read_text())
   require(r['status'] in ['completed','failed','timed_out'],'Job still active')
   require(hashlib.sha256((d/'prompt.txt').read_bytes()).hexdigest()==r['prompt_sha256'],'Prompt hash mismatch')
   require(r['model']=='gpt-6-luna','Unexpected requested model')
   if r['status']=='completed':
    completed+=1;c=json.loads((d/'candidate.json').read_text());schema.validate(c)
    require(c['domain_id']==job['domain_id'],'Wrong result domain')
    evidence=json.loads((d/'web-evidence.json').read_text())
    require(bool(evidence['events']),'Completed source-research job has no web-tool evidence')
  require(completed==summary['completed'],'Summary count mismatch')
  totals['campaigns']+=1;totals['jobs']+=len(jobs);totals['completed']+=completed;totals['source_candidates']+=len(index['source_candidates'])
  totals['candidate_urls_not_observed_in_web_results']+=sum(not s['url_observed_in_web_results'] for s in index['source_candidates'])
 print(json.dumps({'status':'passed','scope':'Execution and citation discovery traceability only; no claim entailment or data acquisition approval',**totals},indent=2))
if __name__=='__main__':main()
