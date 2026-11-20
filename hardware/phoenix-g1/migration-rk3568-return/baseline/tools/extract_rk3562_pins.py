#!/usr/bin/env python3
"""Extract manufacturer's two-column pin table; no electrical types inferred."""
import csv,json,re,hashlib
from pathlib import Path
import fitz
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'reference/rk3562-cost-study.pdf';doc=fitz.open(source);rows=[]
for page_no in range(17,22):
 words=doc[page_no].get_text('words')
 for nx0,nx1,px0,px1 in [(55,259,260,295),(299,509,510,545)]:
  pins=[w for w in words if px0<=w[0]<px1 and re.fullmatch(r'1?[A-Z]{1,2}\d{1,2}',w[4]) and 60<w[1]<800]
  chunks={p[4]:[] for p in pins}
  for w in words:
   if not(nx0<=w[0]<nx1 and 60<w[1]<800) or not pins:continue
   y=(w[1]+w[3])/2
   p=min(pins,key=lambda p:abs((p[1]+p[3])/2-y))
   if abs((p[1]+p[3])/2-y)<9:chunks[p[4]].append(w)
  for p in pins:
   name=''.join(w[4] for w in sorted(chunks[p[4]],key=lambda w:(round(w[1],1),w[0])))
   assert name and 'PinName' not in name,(page_no,p,name)
   rows.append({'ball':p[4],'name':name,'pdf_page':page_no+1,'type':'UNREVIEWED','power_domain':'UNREVIEWED'})
assert len(rows)==478,len(rows)
assert len({r['ball'] for r in rows})==478
out=ROOT/'migration-rk3562/review'
with (out/'manufacturer-pins.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(out/'pin-extraction.json').write_text(json.dumps({'status':'478 UNIQUE PIN LABELS EXTRACTED; NOT INDEPENDENTLY AUDITED','source':str(source.relative_to(ROOT)),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'pages':[18,19,20,21,22],'electrical_types':'Unreviewed; do not copy RK3568 pin numbers/types/unused-pin rules','count':len(rows)},indent=2)+'\n')
print(len(rows),'unique pins extracted')
