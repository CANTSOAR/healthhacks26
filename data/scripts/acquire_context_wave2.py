#!/usr/bin/env python3
"""Acquire bounded NJ/Middlesex SVI slices; record official ACS access attempts separately."""
import datetime as dt, hashlib, json, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NOW=dt.datetime.now(dt.timezone.utc).isoformat()
BASE='https://onemap.cdc.gov/onemapservices/rest/services/SVI/CDC_ATSDR_Social_Vulnerability_Index_2022_USA/FeatureServer'

def write(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'healthhacks26-public-research/1.0'})
 with urllib.request.urlopen(req,timeout=45) as r: return r.read(8_000_001)
def acquire(layer,level):
 sid=f'w2-context-svi2022-middlesex-{level}'
 url=BASE+f'/{layer}/query?'+urllib.parse.urlencode({'where':"STCNTY='34023'",'outFields':'*','returnGeometry':'false','f':'json'})
 raw=get(url)
 if len(raw)>8_000_000: raise ValueError('response exceeded 8MB cap')
 payload=json.loads(raw); feats=payload.get('features',[])
 assert 0<len(feats)<2000
 attrs=[x['attributes'] for x in feats]
 assert all(a.get('STCNTY')=='34023' and a.get('ST_ABBR')=='NJ' for a in attrs)
 keys=[a.get('FIPS') or a.get('STCNTY') for a in attrs]
 assert len(keys)==len(set(keys)), 'duplicate geographic identifiers'
 if level=='tract': assert len(keys)==192 and all(len(str(k))==11 and str(k).startswith('34023') for k in keys)
 else: assert len(keys)==1 and keys[0]=='34023'
 rawdir=ROOT/'raw'/sid; rawdir.mkdir(parents=True,exist_ok=True)
 (rawdir/'records.json').write_bytes(raw)
 meta_raw=get(BASE+f'/{layer}?f=pjson'); (rawdir/'metadata.json').write_bytes(meta_raw)
 meta=json.loads(meta_raw); sha=hashlib.sha256(raw).hexdigest(); meta_sha=hashlib.sha256(meta_raw).hexdigest()
 receipt={'source_url':url,'metadata_url':BASE+f'/{layer}?f=pjson','retrieved_at':NOW,'sha256':sha,'raw_artifact_kind':'original_downloaded_response_bytes','metadata_sha256':meta_sha,'row_count':len(attrs)}
 write(rawdir/'receipt.json',receipt)
 out=ROOT/'normalized'/f'{sid}.jsonl'; out.parent.mkdir(parents=True,exist_ok=True)
 recs=[]
 for a in attrs:
  key=a.get('FIPS') or a.get('STCNTY')
  recs.append({'record_id':sid+':'+str(key),'source_id':sid,'source_record_id':str(key),'record_type':'AreaVulnerabilityProfile','data':{'geography':{'fips':key,'county_fips':a.get('STCNTY'),'state_fips':a.get('ST'),'level':level,'name':a.get('LOCATION'),'county':a.get('COUNTY'),'state':a.get('STATE')},'period':'2022 SVI release; underlying ACS 2018-2022 estimates','population_estimate_source_value':a.get('E_TOTPOP'),'population_estimate_moe':a.get('M_TOTPOP'),'population_estimate_method':'source-reported E_TOTPOP; not calculated by summing tract rows','comparison_frame':'United States database; rankings compare areas nationally','overall_percentile':a.get('RPL_THEMES'),'theme_percentiles':{k:a.get(k) for k in ('RPL_THEME1','RPL_THEME2','RPL_THEME3','RPL_THEME4')},'source_attributes':a,'allowed_use':['community_context','hypothesis_generation'],'not_validated_for':['hospital_case_mix','individual_patient_sampling','causal_policy_evaluation','local_queue_calibration']},'provenance':{'source_url':url,'retrieved_at':NOW,'raw_sha256':sha,'raw_artifact_kind':'original_downloaded_response_bytes','raw_path':str((rawdir/'records.json').relative_to(ROOT.parent)),'acquisition_method':'CDC/ATSDR ArcGIS FeatureServer bounded query; response saved without geometry'},'evidence_kind':'published_area_vulnerability_index','review_status':'source_extracted_not_domain_reviewed','limits':['Area-level composite percentile is not an individual risk or patient attribute.','SVI uses ACS 2018-2022 estimates; release vintage is 2022.','The US layer compares areas nationally; separate state-specific rankings can differ.','County E_TOTPOP is source-reported and was not calculated from tract rows.','Underlying estimates and composite ranking are not direct measures of hospital utilization or access.']})
 assert len({r['record_id'] for r in recs})==len(recs)
 out.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in recs))
 cat={'dataset_id':sid,'source_id':sid,'title':meta.get('name'),'source_url':url,'landing_url':'https://atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html','acquisition_status':'acquired_bounded_geographic_slice','record_count':len(recs),'raw_paths':[str((rawdir/p).relative_to(ROOT.parent)) for p in ('records.json','metadata.json','receipt.json')],'normalized_path':str(out.relative_to(ROOT.parent)),'scope':{'geography_level':level,'state':'NJ','county_fips':'34023','county':'Middlesex County','period':'2022 SVI; ACS 2018-2022'},'access':'public_unauthenticated','rights_status':'U.S. federal government-produced data; CDC states most agency information is public domain unless otherwise noted. No third-party restriction is identified for this numeric SVI layer; attribution retained.','rights':{'basis':'CDC agency-materials policy states most CDC/ATSDR website information is public domain unless otherwise noted; this layer metadata identifies CDC/ATSDR GRASP and no third-party source.','policy_url':'https://www.cdc.gov/other/agencymaterials.html','attribution':'CDC/ATSDR GRASP','service_copyright_text':meta.get('copyrightText'),'redistribution':'Public domain government data; geometry omitted; retain source attribution'},'limits':['Composite rankings are area-level context and are not patient-level risk.','2022 SVI relies on ACS 2018-2022 estimates and is not a current-year observation.','The US database ranks areas nationally; state database rankings may differ.','No hospital arrivals, insurance eligibility, or service-use outcomes are represented.'],'provenance':receipt}
 write(ROOT/'catalog'/f'{sid}.json',cat);print(sid,len(recs))

for pair in [(1,'county'),(2,'tract')]: acquire(*pair)
sid='w2-context-acs2023-language-insurance-middlesex'; url='https://api.census.gov/data/2023/acs/acs5?get=NAME%2CB16001_001E%2CB16001_002E%2CB27001_001E&for=tract%3A%2A&in=state%3A34%20county%3A023'
try:
 body=get(url)
 if b'Missing Key' in body or b'<html' in body[:500].lower(): raise RuntimeError('Census API returned Missing Key HTML; no ACS observations acquired')
 raise RuntimeError('Unexpected ACS response; follow-up normalization needed')
except Exception as e:
 attempts=ROOT/'research'/'access-attempts'; attempts.mkdir(parents=True,exist_ok=True)
 write(attempts/f'{sid}.json',{'attempt_id':sid,'title':'ACS 2023 5-year language and health insurance characteristics, Middlesex County census tracts','source_url':url,'landing_url':'https://www.census.gov/data/developers/data-sets/acs-5year/2023.html','attempt_status':'blocked_missing_api_key','records_acquired':0,'raw_response_retained':False,'scope':{'geography_level':'tract','state':'NJ','county_fips':'34023','period':'2019-2023 ACS 5-year estimate'},'access':'public API attempt; no API key supplied or registered','reason':str(e),'next_step':'Retry with an authorized Census API key or official key-free bulk slice.','retrieved_at':NOW})
 old=ROOT/'catalog'/f'{sid}.json'
 if old.exists(): old.unlink()
 empty=ROOT/'normalized'/f'{sid}.jsonl'
 if empty.exists(): empty.unlink()
 print(sid,'BLOCKED:',str(e))

# CMS monthly beneficiary enrollment: one county only, kept separate from SVI.
def acquire_cms_enrollment():
 sid='w2-context-cms-medicare-enrollment-middlesex'
 dataset='d7fabe1e-d19b-4333-9eff-e80e0643f2fd'
 base=f'https://data.cms.gov/data-api/v1/dataset/{dataset}/data'
 url=base+'?'+urllib.parse.urlencode({'filter[BENE_FIPS_CD]':'34023','size':5000})
 raw=get(url)
 if len(raw)>8_000_000: raise ValueError('CMS county slice exceeds 8MB cap')
 values=json.loads(raw)
 assert isinstance(values,list) and 0<len(values)<5000
 assert all(r.get('BENE_FIPS_CD','').strip()=='34023' and r.get('BENE_STATE_ABRVTN')=='NJ' and r.get('BENE_GEO_LVL')=='County' for r in values)
 keys=[(r['YEAR'],r['MONTH']) for r in values]; assert len(keys)==len(set(keys))
 meta_url=f'https://data.cms.gov/data-api/v1/dataset/{dataset}/data-viewer?size=1'
 meta_raw=get(meta_url); meta=json.loads(meta_raw)
 rawdir=ROOT/'raw'/sid; rawdir.mkdir(parents=True,exist_ok=True)
 (rawdir/'records.json').write_bytes(raw); (rawdir/'metadata.json').write_bytes(meta_raw)
 sha=hashlib.sha256(raw).hexdigest(); msha=hashlib.sha256(meta_raw).hexdigest()
 receipt={'source_url':url,'metadata_url':meta_url,'retrieved_at':NOW,'sha256':sha,'raw_artifact_kind':'original_downloaded_response_bytes','metadata_sha256':msha,'row_count':len(values)}
 write(rawdir/'receipt.json',receipt)
 out=ROOT/'normalized'/f'{sid}.jsonl'; out.parent.mkdir(parents=True,exist_ok=True); recs=[]
 for r in values:
  rid=f"{r['YEAR']}:{r['MONTH']}:34023"
  recs.append({'record_id':sid+':'+rid,'source_id':sid,'source_record_id':rid,'record_type':'MedicareBeneficiaryEnrollmentAggregate','data':{'geography':{'fips':'34023','state':'NJ','county':'Middlesex County','level':'county'},'period':{'year':int(r['YEAR']),'month_or_annual':'annual' if r['MONTH']=='Year' else r['MONTH']},'beneficiary_counts_source_fields':r,'population_scope':'Medicare beneficiaries in the source-defined county/month; not hospital patients or all county residents','values_are_strings':'CMS supplies count fields as strings; source values preserved without coercion','allowed_use':['dated_payer_context','community_context'],'not_validated_for':['hospital_patient_payer_mix','individual_eligibility','hospital_claim_reimbursement','local_case_mix']},'provenance':{'source_url':url,'retrieved_at':NOW,'raw_sha256':sha,'raw_artifact_kind':'original_downloaded_response_bytes','raw_path':str((rawdir/'records.json').relative_to(ROOT.parent)),'acquisition_method':'CMS Data API exact-match filter on BENE_FIPS_CD, size 5000'},'evidence_kind':'published_administrative_enrollment_aggregate','review_status':'source_extracted_not_domain_reviewed','limits':['Aggregate enrollment does not reveal which beneficiaries use RWJUH or another hospital.','Does not establish a particular person’s eligibility, coverage details, or provider network.','Monthly data available through June 2026 in this retrieval; annual summary rows are also present.','CMS count suppression or definition rules apply; interpret source fields with the data dictionary.']})
 assert len({x['record_id'] for x in recs})==len(recs)
 out.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in recs))
 title='Medicare Monthly Enrollment'
 cat={'dataset_id':sid,'source_id':sid,'title':title,'source_url':url,'landing_url':'https://data.cms.gov/summary-statistics-on-beneficiary-enrollment/medicare-and-medicaid-reports/medicare-monthly-enrollment','acquisition_status':'acquired_bounded_geographic_slice','record_count':len(recs),'raw_paths':[str((rawdir/p).relative_to(ROOT.parent)) for p in ('records.json','metadata.json','receipt.json')],'normalized_path':str(out.relative_to(ROOT.parent)),'scope':{'geography_level':'county','state':'NJ','county_fips':'34023','county':'Middlesex County','periods':sorted({r['YEAR'] for r in values}),'latest_month':max((r for r in values if r['MONTH']!='Year'),key=lambda x:(int(x['YEAR']),['January','February','March','April','May','June','July','August','September','October','November','December'].index(x['MONTH'])))['MONTH']},'access':'public unauthenticated CMS Data API','rights_status':'U.S. federal government dataset. CMS API metadata provides no specific license field; attribution retained and no third-party content identified in the API response.','rights':{'source_copyright':'CMS data API response; no license field in API response','attribution':'Centers for Medicare & Medicaid Services','basis':'Federal agency administrative aggregate dataset; no third-party source identified. Consult CMS terms for uses beyond public research.'},'limits':['Beneficiary enrollment counts are population aggregates, not hospital utilization.','Not individual eligibility, negotiated price, provider participation, or hospital payer mix.','Suppressed/small counts and variable definitions follow CMS documentation.'],'provenance':receipt}
 write(ROOT/'catalog'/f'{sid}.json',cat); print(sid,len(recs),'rows; latest monthly record',cat['scope']['periods'][-1],cat['scope']['latest_month'])
acquire_cms_enrollment()
