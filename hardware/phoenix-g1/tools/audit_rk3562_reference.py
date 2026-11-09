#!/usr/bin/env python3
"""Independent designer-reference crosscheck; not electrical qualification."""
import csv, json, re, hashlib
from pathlib import Path
import fitz
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'migration-rk3562/review'
source=ROOT/'reference/rk3562-oomwoo-reference.pdf'
doc=fitz.open(source)
known={r['ball']:r for r in csv.DictReader((OUT/'manufacturer-pins.csv').open())}
reference={}
for page_index in range(4,12):
 lines=[s.strip() for s in doc[page_index].get_text().splitlines()]
 domain=None
 for i,line in enumerate(lines[:-1]):
  m=re.fullmatch(r'RK3562_[A-Z]+\((.*)\)',line)
  if m: domain=m[1]
  ball=lines[i+1]
  if ball not in known or not re.search(r'[A-Z]',line) or line.startswith(('PI','CO','PO')): continue
  if not ('|' in line or line.startswith(('DDR','USB','MULTI','SARADC','PMUIO','VCCIO','XIN','XOUT','nPOR','SYSPLL','PMUPLL','PMU_'))): continue
  reference[ball]={'functions':re.split(r'\s*\|\s*',line),'domain':domain,'pdf_page':page_index+1}
allocation=json.loads((OUT/'initial-function-allocation.json').read_text())['signals']
checks=[]
for a in allocation:
 r=reference.get(a['soc_ball']); function=a['function']
 checks.append({'net':a['net'],'ball':a['soc_ball'],'function':function,'reference':r,'result':'NOT_EXTRACTED' if r is None else ('MATCH' if function in r['functions'] else 'REVIEW')})
report={'status':'DOCUMENT CROSSCHECK ONLY','source_url':'https://github.com/makerspet/oomwoo-pcb/blob/346d30e84f622e32db1f6d4276131fb18d2b9770/etc/Altium/OutputFiles/PDF/Controller-RK3562.PDF','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_limit':'Third-party designer schematic; not proof of working hardware or manufacturer approval. Text extraction needs visual follow-up for ambiguous rows.','counts':{k:sum(c['result']==k for c in checks) for k in ['MATCH','REVIEW','NOT_EXTRACTED']},'checks':checks,'production_ready':False}
(OUT/'independent-reference-check.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['counts'])
for c in checks:
 if c['result']=='REVIEW': print(c)
