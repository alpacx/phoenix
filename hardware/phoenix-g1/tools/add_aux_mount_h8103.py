#!/usr/bin/env python3
"""Create auxiliary H8103 M2 NPTH only after both-side reserved-body clearance."""
import pcbnew as p,json,math,shutil,subprocess,hashlib
from pathlib import Path
from drc_regression import introduced
from pcb_preservation import verify_preservation
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/aux-mount-clear/pcb';src=D/'lcd-bypass-placement.kicad_pcb';out=D/'h8103-hole.kicad_pcb';proof=json.loads((D/'lcd-bypass-placement.json').read_text());assert proof['status']=='PLACEMENT_ACCEPTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256'];b=p.LoadBoard(str(src));sites=[('H8103',21,3)];report=[]
def bbox(a):
 q=a.GetBoundingBox();return [p.ToMM(v) for v in (q.GetX(),q.GetY(),q.GetRight(),q.GetBottom())]
for ref,x,y in sites:
 blockers=[]
 for f in b.GetFootprints():
  for item in list(f.Pads())+[g for g in f.GraphicalItems() if g.GetLayer() in (p.F_CrtYd,p.B_CrtYd)]:
   z=bbox(item)
   if math.hypot(max(z[0]-x,0,x-z[2]),max(z[1]-y,0,y-z[3]))<2.7:blockers.append(f.GetReference());break
 assert not blockers,(ref,blockers)
 assert not any(f.GetReference()==ref for f in b.GetFootprints())
 f=p.FootprintLoad('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/MountingHole.pretty','MountingHole_2.2mm_M2');assert f;f.SetReference(ref);f.SetAttributes(f.GetAttributes() | p.FP_BOARD_ONLY | p.FP_EXCLUDE_FROM_BOM | p.FP_EXCLUDE_FROM_POS_FILES);f.Reference().SetLayer(p.F_Fab);f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));b.Add(f)
 pads=list(f.Pads());assert len(pads)==1 and pads[0].GetAttribute()==p.PAD_ATTRIB_NPTH
 report.append({'ref':ref,'center_mm':[x,y],'drill_mm':p.ToMM(pads[0].GetDrillSize().x),'reserved_body_radius_mm':2.7,'component_blockers':[]})
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'h8103-hole-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'lcd-bypass-placement-drc.json').read_text()),json.loads((D/'h8103-hole-drc.json').read_text()));assert not new,new
result={'status':'H8103_NPTH_CANDIDATE_WITH_BODY_CLEARANCE','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'holes':report,'preservation':verify_preservation(p.LoadBoard(str(src)),b),'new_violations':new,'auxiliary_holes_created':['H8103'],'standoff_height_and_screw_length_qualified':False,'daughterboard_mating_and_enclosure_qualified':False,'assembly_ready':False};(D/'h8103-hole.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
