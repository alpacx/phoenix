#!/usr/bin/env python3
"""Explicit short eFuse capacitor branches. Current/thermal rating unqualified."""
import pcbnew as p,json,shutil,math,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'migration-rk3562/experiments/stacked-expansion/pcb';b=p.LoadBoard(str(D/'ground-routed.kicad_pcb'));pads={(f.GetReference(),a.GetNumber()):a for f in b.GetFootprints() for a in f.Pads()}
def xy(a):return tuple(p.ToMM(v) for v in [a.GetPosition().x,a.GetPosition().y])
def pt(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
routes=[('3','C8101',[(78.25,6.55),(78.7,6.75),(79.32,7.37)]),('4','C8101',[(78.7,6.75),(79.32,7.37)]),('5','C8102',[(75.7,6.75),(75.7,8),(74.48,8)])];report=[]
for pin,ref,middle in routes:
 a,z=pads['U8101',pin],pads[ref,'1'];assert a.GetNetname()==z.GetNetname();path=[xy(a)]+middle+[xy(z)]
 for x,y in zip(path,path[1:]):
  if math.dist(x,y)<1e-6:continue
  t=p.PCB_TRACK(b);t.SetStart(pt(x));t.SetEnd(pt(y));t.SetWidth(p.FromMM(.3));t.SetLayer(p.B_Cu);t.SetNetCode(a.GetNetCode());b.Add(t)
 report.append({'from':'U8101.'+pin,'to':ref+'.1','net':a.GetNetname(),'length_mm':sum(math.dist(x,y) for x,y in zip(path,path[1:])),'width_mm':.3})
p.ZONE_FILLER(b).Fill(b.Zones());dest=D/'local-power.kicad_pcb';p.SaveBoard(str(dest),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(D/f'candidate.{ext}',dest.with_suffix('.'+ext))
(D/'local-power.json').write_text(json.dumps({'status':'LOCAL_CAPACITOR_BRANCHES_PENDING_DRC','routes':report,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'input_source_connected':False,'J3_power_connected':False,'current_rating_qualified':False,'assembly_ready':False},indent=2)+'\n')
