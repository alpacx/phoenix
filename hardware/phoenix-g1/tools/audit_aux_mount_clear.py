#!/usr/bin/env python3
"""Promote only after original connections, placement scope and DRC are checked."""
import pcbnew as p,json,hashlib,math
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';S=E/'pmic-inputs';D=E/'aux-mount-clear'
cp=json.loads((S/'working-candidate.json').read_text());src=S/cp['board'];out=D/'pcb/lcd-bypass.kicad_pcb'
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
r=json.loads((D/'pcb/lcd-bypass.json').read_text());assert r['status']=='LCD_LOCAL_BYPASS_CONNECTED'
assert hashlib.sha256(out.read_bytes()).hexdigest()==r['sha256']
a,b=p.LoadBoard(str(src)),p.LoadBoard(str(out))
old={f.GetReference():f for f in a.GetFootprints()};new={f.GetReference():f for f in b.GetFootprints()}
assert set(new)-set(old)=={'H8103'}
for ref,f in old.items():
 g=new[ref];assert f.GetValue()==g.GetValue()
 if ref not in ['C1801','C1802','R1815']:
  assert f.GetPosition()==g.GetPosition() and f.GetOrientationDegrees()==g.GetOrientationDegrees() and f.GetLayer()==g.GetLayer(),ref
for ext in ['.kicad_pro','.kicad_dru']:assert src.with_suffix(ext).read_bytes()==out.with_suffix(ext).read_bytes()
for f in b.GetFootprints():
 if f.GetReference()=='H8103':continue
 for q in list(f.Pads())+[g for g in f.GraphicalItems() if g.GetLayer() in [p.F_CrtYd,p.B_CrtYd]]:
  bb=q.GetBoundingBox();x0,y0,x1,y1=[p.ToMM(v) for v in [bb.GetX(),bb.GetY(),bb.GetRight(),bb.GetBottom()]]
  assert math.hypot(max(x0-21,0,21-x1),max(y0-3,0,3-y1))>=2.7,f.GetReference()
preserved=verify_preservation(a,b)
violations=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'pcb/lcd-bypass-drc.json').read_text()));assert not violations
sha=hashlib.sha256(out.read_bytes()).hexdigest()
report={'status':'LOCAL_LCD_BYPASS_AND_AUX_MOUNT_NOT_QUALIFIED','sha256':sha,'source_sha256':cp['sha256'],'preservation':preserved,'new_violations':violations,'existing_rules_unchanged':True,'moved_refs':['C1801','C1802','R1815'],'new_hole':'H8103','body_radius_mm':2.7,'lcd_checks':r['checks'],'assembly_ready':False}
(D/'pcb/final-audit.json').write_text(json.dumps(report,indent=2)+'\n')
(D/'working-candidate.json').write_text(json.dumps({'status':report['status'],'board':'pcb/lcd-bypass.kicad_pcb','sha256':sha,'verification':'pcb/final-audit.json','schematic':cp['schematic'],'assembly_ready':False},indent=2)+'\n')
print(json.dumps(report,indent=2))
