#!/usr/bin/env python3
"""Integrated eMMC schematic candidate. Leaves source and routed PCB untouched.
New 1.8V/3.3V supply nets remain explicitly unqualified/unconnected to sources.
"""
import json,shutil,uuid,math
from pathlib import Path
import sexpdata as sx
from audit_rk3568 import fields,walk
import integrate_schematic as integration
R=Path(__file__).resolve().parents[1];E=R/'migration-rk3562/experiments';BASE=E/'stacked-expansion/system';MEM=E/'emmc-8gb';OUT=E/'emmc-system';SYS=OUT/'system'
for folder in ['kicad','sourcing']:shutil.copytree(BASE/folder,SYS/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('integrated','pcb','*.lck','*.kicad_prl'))
(SYS/'review').mkdir(parents=True,exist_ok=True)
for source in (BASE/'review').iterdir():
 if source.name.endswith('-expected.json') or source.name=='footprint-overrides.json':shutil.copy2(source,SYS/'review'/source.name)
old=json.loads((SYS/'review/boot-flash-expected.json').read_text());removed=sorted({r['ref'] for r in old});(SYS/'kicad/boot-flash.kicad_sch').unlink();(SYS/'review/boot-flash-expected.json').unlink()
for name in ['emmc-storage-candidate.kicad_sch','Phoenix_eMMC_Draft.kicad_sym']:shutil.copy2(MEM/'kicad'/name,SYS/'kicad'/name)
shutil.copytree(MEM/'kicad/Phoenix_eMMC_Draft.pretty',SYS/'kicad/Phoenix_eMMC_Draft.pretty',dirs_exist_ok=True)
shutil.copy2(MEM/'review/emmc-storage-candidate-expected.json',SYS/'review/emmc-storage-candidate-expected.json')
changed=[]
def replace(ball,oldnet,newnet,pintype):
 contract_file=next(f for f in (SYS/'review').glob('*expected.json') if any(r['ref']=='U1' and r['pin']==ball for r in json.loads(f.read_text())))
 rows=json.loads(contract_file.read_text());row=next(r for r in rows if r['ref']=='U1' and r['pin']==ball);assert row['net']==oldnet,(ball,row);sch=SYS/'kicad'/contract_file.name.replace('-expected.json','.kicad_sch');tree=sx.loads(sch.read_text());found=None
 for inst in fields(tree,'symbol'):
  if not any(p[1]=='Reference' and p[2]=='U1' for p in fields(inst,'property')):continue
  unit=fields(inst,'unit')[0][1];lib=next(s for group in fields(tree,'lib_symbols') for s in fields(group,'symbol') if s[1]==fields(inst,'lib_id')[0][1])
  for sub in fields(lib,'symbol'):
   if not str(sub[1]).endswith(f'_{unit}_1'):continue
   for pin in walk(sub,'pin'):
    if str(fields(pin,'number')[0][1])==ball:found=inst,pin
 assert found,ball
 inst,pin=found;ix,iy=fields(inst,'at')[0][1:3];px,py,angle=fields(pin,'at')[0][1:];x,y=round(ix+px,4),round(iy-py,4);pin[1]=sx.Symbol(pintype)
 if oldnet is None:
  nc=next(n for n in fields(tree,'no_connect') if fields(n,'at')[0][1:3]==[x,y]);tree.remove(nc);ex=round(x-5.08*math.cos(math.radians(angle)),4)
  tree.append(sx.loads(f'(wire (pts (xy {x} {y}) (xy {ex} {y})) (stroke (width 0) (type default)) (uuid "{uuid.uuid5(uuid.NAMESPACE_URL,"emmc-wire-"+ball)}"))'))
  tree.append(sx.loads(f'(label "{newnet}" (at {ex} {y} 0) (effects (font (size 1 1)) (justify {"right" if angle==0 else "left"} bottom)) (uuid "{uuid.uuid5(uuid.NAMESPACE_URL,"emmc-label-"+ball)}"))'))
 else:
  ends=[]
  for w in fields(tree,'wire'):
   pts=[q[1:3] for pts in fields(w,'pts') for q in fields(pts,'xy')]
   if [x,y] in pts:ends.extend(q for q in pts if q!=[x,y])
  labels=[n for n in fields(tree,'label') if n[1]==oldnet and fields(n,'at')[0][1:3] in ends];assert len(labels)==1,(ball,ends,len(labels));labels[0][1]=newnet
 sch.write_text(sx.dumps(tree)+'\n');row['net']=newnet;contract_file.write_text(json.dumps(rows,indent=2)+'\n');changed.append({'ball':ball,'from':oldnet,'to':newnet})
for m in json.loads((MEM/'signal-map.json').read_text()):
 net='SOC_EMMC_CLK' if m['signal']=='EMMC_CLK' else m['signal'];typ='output' if m['signal']=='EMMC_CLK' else 'input' if m['signal']=='EMMC_STRB' else 'bidirectional';replace(m['soc_ball'],m['previous_net'],net,typ)
replace('1F14','+3V3_IO','EMMC_IO_1V8','power_in')
p=SYS/'sourcing/selected-references.json';selected=json.loads(p.read_text());removed_codes=[]
for code in list(selected):
 selected[code]=' '.join(r for r in selected[code].split() if r not in removed)
 if not selected[code]:removed_codes.append(code);del selected[code]
selected['C25792']=(selected.get('C25792','')+' R8005').strip();selected['C1525']=(selected.get('C1525','')+' C8010').strip();selected['C499918']='U8001';p.write_text(json.dumps(selected,indent=2)+'\n')
p=SYS/'sourcing/selected-main-parts.json';data=json.loads(p.read_text());data['parts']=[r for r in data['parts'] if r.get('jlc') not in removed_codes];data['parts'].append({'jlc':'C499918','mpn':'KLM8G1GETF-B041'});p.write_text(json.dumps(data,indent=2)+'\n')
p=SYS/'kicad/fp-lib-table';tree=sx.loads(p.read_text());tree.append(sx.loads('(lib (name "Phoenix_eMMC_Draft") (type "KiCad") (uri "${KIPRJMOD}/Phoenix_eMMC_Draft.pretty") (options "") (descr "Unqualified eMMC candidate"))'));p.write_text(sx.dumps(tree)+'\n')
p=SYS/'kicad/sym-lib-table';tree=sx.loads(p.read_text());tree.append(sx.loads('(lib (name "Phoenix_eMMC_Draft") (type "KiCad") (uri "${KIPRJMOD}/Phoenix_eMMC_Draft.kicad_sym") (options "") (descr "Unqualified eMMC candidate"))'));p.write_text(sx.dumps(tree)+'\n')
sch=SYS/'kicad/emmc-storage-candidate.kicad_sch';tree=sx.loads(sch.read_text())
for inst in fields(tree,'symbol'):
 ref=next(v[2] for v in fields(inst,'property') if v[1]=='Reference')
 if ref in ['R8005','C8010']:
  target='Phoenix_Passives:R_0402_1005Metric' if ref=='R8005' else 'Phoenix_Passives:C_0402_1005Metric'
  prop=next(v for v in fields(inst,'property') if v[1]=='Footprint');prop[2]=target
sch.write_text(sx.dumps(tree)+'\n')
integration.ROOT=SYS;integration.main()
report={'status':'INTEGRATED_SCHEMATIC_CANDIDATE_POWER_SOURCES_OPEN','removed_boot_flash_references':removed,'soc_pin_changes':changed,'VCCIO3_unchanged':True,'EMMC_3V3_source_connected':False,'EMMC_IO_1V8_source_connected':False,'PCB_updated':False,'assembly_ready':False};(OUT/'integration.json').write_text(json.dumps(report,indent=2)+'\n');(SYS/'review/candidate-checkpoint.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
