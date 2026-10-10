#!/usr/bin/env python3
"""Build a proposed encounter coverage map; citations are evidence candidates, not local protocols."""
import json
from pathlib import Path
D=Path(__file__).resolve().parents[1]
records={}
for p in (D/'normalized').glob('*.jsonl'):
 if p.stat().st_size>5_000_000:continue
 for line in p.read_text().splitlines():
  r=json.loads(line);records[r['record_id']]=r
# A domain index is a discovery aid; every source still requires claim-level review.
domains={domain:[r['id'] for r in json.loads((D/'research'/f'encounter-{domain}.json').read_text()) if r.get('source_access')!='search_index_only_pending_primary_inspection'] for domain in ['arrival','treatment','communication']}
stages=[
 ('arrival_identity','Arrival, identity and handoff',['registration','EMS crew','triage nurse'],['arrival mode','patient identifier or temporary identity','handoff owner','arrival timestamp'],[],['arrival'],'Local identity-match/duplicate-record/unknown-patient policy; EMS handoff timestamps'),
 ('urgency_waiting','Urgency assessment and waiting reassessment',['triage nurse','emergency clinician'],['presenting concern','acuity decision','observations','next reassessment owner','waiting location'],['admin-emtala-screening'],['arrival'],'Reviewed local acuity logic, reassessment/escalation policy and staffed coverage'),
 ('history_assessment','History, examination and communication needs',['patient','clinician','nurse','interpreter'],['authored findings','allergies and medicines','communication needs','decision capacity','assessment completeness'],[],['treatment','communication'],'Clinician-authored findings and differential/decision rules; interpreter availability'),
 ('orders_execution','Order entry, acceptance and performance',['clinician','nurse','pharmacist','diagnostic staff'],['order status','accepting actor','dependencies','resource reservation','performance time'],['gap-medication-cpoe-verification-time','gap-diagnostics-lab-error-rejection-criteria'],[],'Local order routing, queue priorities, equipment/staff compatibility and service distributions'),
 ('results_review','Result availability and clinical review',['diagnostic staff','ordering clinician'],['result status','result reviewer','acknowledgment','change to assessment'],['acr-acute-wrist-trauma-imaging-pathway'],['treatment','communication'],'Separate ordered/performed/preliminary/final/acknowledged states; authored clinical interpretation'),
 ('treatment_reassessment','Treatment choice, execution and reassessment',['patient','clinician','nurse','consultant'],['reviewed treatment choice','consent','intervention event','reassessment findings','complication/escalation branch'],[],['treatment','communication'],'Reviewed injury-specific protocol, prerequisites, actor permissions and response logic'),
 ('disposition_handoff','Disposition and receiving-team acceptance',['ED clinician','consultant','bed manager','receiving nurse'],['disposition decision','accepting service','bed readiness','handoff acceptance','transport'],['gap-flow-room-turnover-isolation'],['treatment'],'Local discharge/admission/transfer criteria and receiving-service acceptance policy'),
 ('discharge_communication','Discharge plan and patient understanding',['patient','caregiver','nurse','clinician','interpreter'],['instructions','understanding check','return precautions','appointment or referral','practical barriers'],[],['communication','treatment'],'Accessible authored instructions, escalation wording, appointment access and patient goals'),
 ('pending_results_followup','Pending results, callbacks and follow-up',['responsible clinician','follow-up team','patient'],['pending result owner','due event','contact attempt','acknowledgment','closed-loop resolution'],[],['communication'],'Local results-routing and escalation policy; failed contact/uncompleted referral branches'),
 ('administration_parallel','Parallel benefit and payment workflow',['registration','financial counselor','payer reviewer'],['plan/product snapshot','eligibility','notification','authorization status','claim/payment status'],['specialty-ins-notification-vs-review','specialty-ins-emergency-screening'],[],'Actual plan/service/network/benefit evidence; avoid administrative gates on emergency care')
]
out=[]
for sid,title,roles,fields,ids,ds,gap in stages:
 assert all(r in records for r in ids),(sid,ids)
 candidate=list(dict.fromkeys(ids+sum((domains[d] for d in ds),[])))
 out.append({'stage_id':sid,'title':title,'proposed_roles':roles,'proposed_state_fields':fields,'existing_source_record_ids':ids,'new_source_candidate_ids':list(dict.fromkeys(sum((domains[d] for d in ds),[]))),'evidence_mapping_scope':'Stage-level discovery only; not every cited source supports every proposed role or field. Review each source claim before adoption.','source_record_ids':candidate,'design_status':'authored_proposal_not_executable_protocol','local_validation':'not_established','duration_distribution':None,'remaining_requirement':gap})
result={'version':1,'status':'proposed_encounter_coverage_not_runnable_or_clinically_approved','scope':'General hospital encounter research scaffold, with adult distal-radius/wrist example; not all diagnoses or age groups.','stages':out,'invariants':['Patient condition is separate from documented chart state.','An order does not imply performance, a result does not imply review, and a referral does not imply attendance.','Clinical and administrative tasks may run concurrently; emergency care must not wait for invented payer approval.','Responsibility for pending results survives encounter discharge until explicitly reassigned and accepted.','External outcomes never supply a local probability or patient response without reviewed adoption.'],'completion_gates':['Clinician-reviewed case truth and treatment/disposition branches','Local role permissions and task/state semantics','Explicitly calibrated or declared synthetic timing/resource model','Reviewed communication, consent and escalation content','End-to-end scenario verification including exceptions and follow-up']}
(D/'knowledge/full-encounter-readiness.json').write_text(json.dumps(result,indent=2)+'\n')
print(len(out),'proposed stages; all source IDs resolve; no local timing distributions assigned')
