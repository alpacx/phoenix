#!/usr/bin/env python3
"""Create H8105 only after clearance screening; enclosure still unqualified."""
import pcbnew as p,json,math,shutil,subprocess,hashlib,os,sys
from pathlib import Path
from drc_regression import introduced
from pcb_preservation import verify_preservation
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/mechanical-clearance-parallel';src=D/'mount-clearance.kicad_pcb';out=D/'h8105-hole.kicad_pcb'
if '--verify' in sys.argv:
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'hole-drc.json'),str(out)],check=True,capture_output=True)
 a=p.LoadBoard(str(src));b=p.LoadBoard(str(out));new=introduced(json.loads((D/'drc.json').read_text()),json.loads((D/'hole-drc.json').read_text()))
 result={'status':'H8105_GEOMETRY_ACCEPTED' if not new else 'REJECTED','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'preservation':verify_preservation(a,b),'hole':{'reference':'H8105','center_mm':[70,34],'drill_mm':2.2,'body_reservation_radius_mm':2.7},'assembly_ready':False,'standoff_screw_length_enclosure_and_thermal_qualified':False}
 (D/'hole-checkpoint.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);os._exit(0)
proof=json.loads((D/'checkpoint.json').read_text());assert proof['status']=='PLACEMENT_ACCEPTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256'];b=p.LoadBoard(str(src));blockers=[]
for f in b.GetFootprints():
 for item in list(f.Pads())+[g for g in f.GraphicalItems() if g.GetLayer() in (p.F_CrtYd,p.B_CrtYd)]:
  q=item.GetBoundingBox();z=[p.ToMM(v) for v in (q.GetX(),q.GetY(),q.GetRight(),q.GetBottom())]
  if math.hypot(max(z[0]-70,0,70-z[2]),max(z[1]-34,0,34-z[3]))<2.7:blockers.append(f.GetReference());break
assert not blockers,blockers
assert not any(f.GetReference()=='H8105' for f in b.GetFootprints())
f=p.FootprintLoad('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/MountingHole.pretty','MountingHole_2.2mm_M2');assert f
f.SetReference('H8105');f.SetAttributes(f.GetAttributes()|p.FP_BOARD_ONLY|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES);f.Reference().SetLayer(p.F_Fab);f.SetPosition(p.VECTOR2I(p.FromMM(70),p.FromMM(34)));b.Add(f)
assert list(f.Pads())[0].GetAttribute()==p.PAD_ATTRIB_NPTH
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);os.execv(sys.executable,[sys.executable,__file__,'--verify'])
