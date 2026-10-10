#!/usr/bin/env python3
"""Publish a source-discovery index and tool activity metadata, never acquired claims."""
import argparse,json,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('run');args=ap.parse_args();root=(BASE/args.run).resolve()
 if not root.is_relative_to((BASE/'runs').resolve()):raise ValueError('Run must be within data/runs')
 entries=[];sources=[]
 for d in sorted(root.iterdir()):
  if not d.is_dir() or not (d/'receipt.json').exists():continue
  receipt=json.loads((d/'receipt.json').read_text());trail=[]
  trace=BASE/'runs/private'/root.name/(d.name+'.jsonl')
  if trace.exists():
   for line in trace.read_text().splitlines():
    try:event=json.loads(line)
    except json.JSONDecodeError:continue
    item=event.get('item',{})
    if event.get('type')=='item.completed' and item.get('type')=='web_search':
     trail.append({'action':item.get('action',{}),'results':[{'url':r.get('url'),'title':r.get('title'),'reference_id':r.get('ref_id')} for r in item.get('results',[]) if r.get('url')]})
  (d/'web-evidence.json').write_text(json.dumps({'meaning':'Observed native web-tool activity. Search result or page URL is not proof of successful data acquisition, rights or factual entailment. Source text and private diagnostics excluded.','events':trail},indent=2)+'\n')
  value=json.loads((d/'candidate.json').read_text()) if receipt['status']=='completed' else {}
  observed={r['url'] for e in trail for r in e['results']}
  for i,s in enumerate(value.get('sources',[])):
   sources.append({'candidate_id':d.name+':'+str(i+1),'domain_id':d.name,'review_status':'unreviewed_discovery','dataset_acquired':False,'url_observed_in_web_results':s['url'] in observed,**s})
  entries.append({'domain_id':d.name,'status':receipt['status'],'candidate_sources':len(value.get('sources',[])),'completed_web_tool_calls':len(trail),'receipt':str((d/'receipt.json').relative_to(BASE)),'candidate':str((d/'candidate.json').relative_to(BASE)) if value else None})
 report={'scope':'GPT-6 Luna primary-source discovery only; independent collectors maintain catalog/ and normalized/','run':str(root.relative_to(BASE)),'jobs':entries,'source_candidates':sources}
 (root/'discovery-index.json').write_text(json.dumps(report,indent=2)+'\n')
 lines=['# Hospital research avenues campaign','','Finite GPT-6 Luna campaign: **'+str(len(entries))+' jobs**, **'+str(sum(r['status']=='completed' for r in entries))+' completed**, **'+str(len(sources))+' source candidates**. These candidates are source-discovery results, not additional acquired datasets or reviewed simulation parameters.','','Machine results, each exact prompt, receipts, candidate reports and sanitized web-tool URL evidence are saved in [`'+root.name+'`](../runs/'+root.name+'/). Failed/time-limited jobs, if any, remain explicit.','','| Domain | Status | Source candidates | Completed web calls |','|---|---|---:|---:|']
 for e in entries:lines.append('| '+e['domain_id']+' | '+e['status']+' | '+str(e['candidate_sources'])+' | '+str(e['completed_web_tool_calls'])+' |')
 lines+=['','Three parallel acquisition workers separately pursued operational, clinical and community/insurance inputs. Their actual acquired records and source snapshots are in `catalog/`, `normalized/`, `raw/` and the canonical citation index. See [operations](wave2-operations.md), [clinical](wave2-clinical.md), and [community/insurance](wave2-context.md) for counts, methods and failures.','','Discovery does not eliminate the need for direct operational inputs. Public reports usually provide marginal or historical aggregates. They do not reveal all shift availability, queue/service decomposition, conditional transition rules, clinical truth or causal effects. No source agreement was accepted and no outreach was sent.','','The campaign runner caps parallelism and runtime, validates each output schema and separates results from the acquired catalog. The web evidence ledger retains observed URLs and tool actions without republishing source text. An observed URL can be a search result rather than an opened/downloaded dataset. Every candidate still needs scope, access, rights and content verification before acquisition or use.']
 (BASE/'research/avenues-campaign.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps({'jobs':len(entries),'completed':sum(e['status']=='completed' for e in entries),'source_candidates':len(sources),'web_calls':sum(e['completed_web_tool_calls'] for e in entries)}))
if __name__=='__main__':main()
