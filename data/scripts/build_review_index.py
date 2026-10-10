#!/usr/bin/env python3
"""Build an offline, searchable human audit view; never changes evidence/review status."""
import hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parents[1]
def resolve(s):return D.parent/s if s.startswith('data/') else D/s
rows=[]
for cp in sorted((D/'catalog').glob('*.json')):
 c=json.loads(cp.read_text());p=resolve(c['normalized_path'])
 for line,s in enumerate(p.read_text().splitlines(),1):
  if not s.strip():continue
  r=json.loads(s);r['_review']={'source_title':c['title'],'catalog_path':'../catalog/'+cp.name,'normalized_path':'../normalized/'+p.name,'normalized_line':line,'record_sha256':hashlib.sha256(s.encode()).hexdigest(),'raw_paths':['../'+str(resolve(x).relative_to(D)) for x in c['raw_paths']],'rights':c['rights'],'source_limits':c['limits']};rows.append(r)
payload=json.dumps(rows,ensure_ascii=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
template=(D/'review/template.html').read_text();out=template.replace('__EVIDENCE_JSON__',payload)
(D/'review/index.html').write_text(out)
print(f'Built human review index: {len(rows)} records; {len(out):,} characters')
