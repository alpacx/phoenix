#!/usr/bin/env python3
"""Enlarge active RK3562 library courtyards that fail basic pad containment.
Preserves copper, holes, masks and existing body envelope. Not full package signoff.
Use KiCad Python; --apply writes active copied libraries only, never baseline.
"""
from pathlib import Path
import pcbnew as p,json,math,re,hashlib,sys,uuid
R=Path(__file__).resolve().parents[1]/'migration-rk3562';K=R/'kicad'
board=p.LoadBoard(str(K/'pcb/phoenix-g1.kicad_pcb'))
issues=json.loads((R/'review/courtyard-envelope-audit.json').read_text());refs={a['ref'] for a in issues['findings']};jobs={}
for f in board.GetFootprints():
 if f.GetReference() not in refs:continue
 fid=f.GetFPID();lib=str(fid.GetLibNickname());name=str(fid.GetLibItemName());key=(lib,name)
 jobs.setdefault(key,[]).append(f.GetReference())
def box(a):
 q=a.GetBoundingBox();return [p.ToMM(v) for v in [q.GetX(),q.GetY(),q.GetRight(),q.GetBottom()]]
def end(text,start):
 depth=0;quoted=False;escape=False
 for i in range(start,len(text)):
  c=text[i]
  if quoted:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c=='"':quoted=False
  elif c=='"':quoted=True
  elif c=='(':depth+=1
  elif c==')':
   depth-=1
   if depth==0:return i+1
 raise ValueError('Unclosed expression')
def pad_signature(f):
 return sorted((a.GetNumber(),a.GetPosition().x,a.GetPosition().y,a.GetSize().x,a.GetSize().y,a.GetDrillSize().x,a.GetDrillSize().y,str(a.GetLayerSet().FmtHex())) for a in f.Pads())
rows=[]
for (lib,name),references in sorted(jobs.items()):
 directory=K/(lib+'.pretty');path=directory/(name+'.kicad_mod');assert path.resolve().is_relative_to(K.resolve()),'Library outside active variant'
 fp=p.FootprintLoad(str(directory),name);assert fp is not None
 before_pads=pad_signature(fp);shapes=[box(a) for a in fp.GraphicalItems() if a.GetLayer()==p.F_CrtYd];margin=.5 if any(ref.startswith(('J','Y')) for ref in references) else .25
 for pad in fp.Pads():
  q=box(pad);shapes.append([q[0]-margin,q[1]-margin,q[2]+margin,q[3]+margin])
 q=[math.floor(min(a[0] for a in shapes)*100)/100,math.floor(min(a[1] for a in shapes)*100)/100,math.ceil(max(a[2] for a in shapes)*100)/100,math.ceil(max(a[3] for a in shapes)*100)/100]
 old=path.read_text();text=old;cuts=[]
 for match in re.finditer(r'\(fp_(?:line|rect|poly|arc|circle)\s',text):
  stop=end(text,match.start());part=text[match.start():stop]
  if re.search(r'\(layer\s+"?F\.CrtYd"?\)',part):cuts.append((match.start(),stop))
 for start,stop in reversed(cuts):text=text[:start]+text[stop:]
 uid=uuid.uuid5(uuid.NAMESPACE_URL,lib+':'+name+':'+str(q));drawing=f'\n (fp_rect (start {q[0]} {q[1]}) (end {q[2]} {q[3]}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd") (uuid "{uid}"))\n'
 last=text.rfind(')');text=text[:last]+drawing+text[last:]
 row={'library_id':lib+':'+name,'references':references,'minimum_pad_margin_mm':margin,'courtyard_centerline_bounds_mm':q,'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(text.encode()).hexdigest()}
 if '--apply' in sys.argv:
  backup=Path('/tmp/phoenix-pre-courtyard-libraries')/(lib+'.pretty')/path.name;backup.parent.mkdir(parents=True,exist_ok=True)
  if not backup.exists():backup.write_text(old)
  path.write_text(text);after=p.FootprintLoad(str(directory),name);assert after is not None and pad_signature(after)==before_pads,'Pad geometry changed'
  overlay=R/'overrides/footprints'/(lib+'.pretty')/path.name;overlay.parent.mkdir(parents=True,exist_ok=True);overlay.write_text(text)
  row['pad_geometry_preserved_by_load_compare']=True
  row['original_before_any_repair_sha256']=hashlib.sha256(backup.read_bytes()).hexdigest()
 rows.append(row)
report={'status':'APPLIED; REGENERATE PCB AND RUN DRC' if '--apply' in sys.argv else 'PROPOSED ONLY','source':'https://klc.kicad.org/footprint/f5/f5.3/','libraries':rows,'limitations':['Repairs basic pad enclosure in active copied libraries only.','Preserves existing body envelope but does not independently establish package maximum dimensions, assembly process, connector mating space or full KLC conformance.','Placement and routing must be regenerated and all mechanical/electrical regressions resolved.'],'production_ready':False}
(R/'review/courtyard-library-repair.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'libraries':len(rows)},indent=2))
