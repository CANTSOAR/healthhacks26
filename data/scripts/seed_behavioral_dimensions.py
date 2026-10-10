#!/usr/bin/env python3
"""Rebuild limited original factual paraphrases inspected 2026-10-10; no source refresh."""
import json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
RETRIEVED='2026-10-10T15:29:17+00:00'
SOURCES=[('w2-behavior-safety-culture','AHRQ Hospital Survey 2.0 composite topic inventory','https://www.ahrq.gov/sites/default/files/wysiwyg/sops/surveys/hospital/hospitalsurvey2-items.pdf',[
('collaboration','Cooperation, mutual help during demand peaks, and interpersonal respect.',3,2),
('workload','Perceived staffing adequacy, long hours, temporary coverage, and unsafe pace.',4,2),
('improvement','Reviewing processes and evaluating changes to reduce repeated safety problems.',3,2),
('error-response','Learning and supporting staff after mistakes rather than assigning personal blame.',4,2),
('frontline-management','Supervisors listening to concerns and acting without encouraging unsafe shortcuts.',3,3),
('incident-discussion','Sharing error information and changes intended to prevent recurrence.',3,3),
('speaking-up','Raising concerns across authority levels and asking questions without fear.',4,3),
('near-miss-reporting','Reporting corrected errors and incidents that could have caused harm.',2,3),
('executive-priorities','Leadership visibly prioritizing safety and supplying improvement resources.',3,3),
('transfer-information','Preserving essential information across unit transfers and shift changes.',3,4)]),
('w2-behavior-team-observation','AHRQ TeamSTEPPS observation topic inventory','https://www.ahrq.gov/sites/default/files/wysiwyg/teamstepps-program/tools/ts-team-performance-tool.pdf',[
('team-organization','Clarifying roles and accountability while including patients and families.',4,1),
('information-exchange','Timely specific information, confirmation, and structured transitions.',4,1),
('coordination','Setting shared goals, distributing work, delegating, and discussing progress.',6,1),
('shared-awareness','Tracking patient, colleagues, resources, and changing plans.',5,1),
('colleague-assistance','Helping with tasks, giving feedback, and constructively escalating safety concerns.',4,1)])]
def main():
 for sid,title,url,items in SOURCES:
  rs=[]
  for key,description,count,page in items:
   rs.append({'record_id':sid+':'+key,'source_id':sid,'source_record_id':key,'record_type':'BehavioralDimension','data':{'dimension_label':key,'description':description,'source_item_count':count,'locator':f'PDF page {page}; corresponding thematic section','population':'Instrument topic definition; no hospital respondent observations','intended_use':'Candidate scenario and observation-design axis; not an administered or validated derivative instrument'},'provenance':{'source_url':url,'retrieved_at':RETRIEVED,'raw_sha256':None,'acquisition_method':'manual limited factual paraphrase from inspected primary-source PDF; full source not redistributed'},'evidence_kind':'published_reference','review_status':'source_extracted_not_domain_reviewed'})
  path=BASE/'normalized'/(sid+'.jsonl');path.write_text(''.join(json.dumps(r)+'\n' for r in rs))
  m={'dataset_id':sid,'source_id':sid,'title':title,'source_url':url,'record_count':len(rs),'raw_paths':[],'normalized_path':'data/normalized/'+sid+'.jsonl','scope':'Limited original descriptions of published instrument topics; no individual items or hospital survey responses copied','access':'public_document','rights':{'basis':'Original limited factual paraphrases only; source instrument not redistributed','attribution':'Agency for Healthcare Research and Quality (AHRQ); no endorsement implied','terms_url':'https://www.ahrq.gov/faqs/index.html?page=3','limitations':'AHRQ describes geographic/reuse conditions; consult official materials before reproducing instruments, using trademarks or adapting scores.'},'acquisition_status':'acquired_selected_paraphrased_facts','limits':['No local staff or patient response data.','These paraphrases are not an official survey, validated scoring system or clinical behavior probabilities.','Use original source and permissions/guidance for actual survey administration.'],'provenance':{'retrieved_at':RETRIEVED,'method':'Manually verified limited topic paraphrases; rerunning script does not refresh source','raw_artifact_kind':'no_raw_source_available'}}
  (BASE/'catalog'/(sid+'.json')).write_text(json.dumps(m,indent=2)+'\n')
 print('Rebuilt 15 cited topic descriptions across2 sources; no local observations implied')
if __name__=='__main__':main()
