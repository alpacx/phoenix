#!/usr/bin/env python3
"""Isolated PHY/WiFi-return co-design. No weakened routing constraints."""
import pcbnew as p,json,hashlib,shutil,sys,os
from pathlib import Path
H=Path(__file__).resolve().parents[1];D=H/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((D/'load-c513-16v-checkpoint.json').read_text());src=D/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src))
vec=lambda xy:p.VECTOR2I(*(p.FromMM(x) for x in xy));removed=[];held=[]
# Replace only the C2007 ground detour to Y2001; preserve Y2001's own direct via.
for t in list(b.GetTracks()):
 if isinstance(t,p.PCB_VIA) or t.GetLayer()!=p.F_Cu or t.GetNetname()!='GND':continue
 a=[p.ToMM(v) for v in t.GetStart()];z=[p.ToMM(v) for v in t.GetEnd()]
 if all(52.4<=x<=54.52 for x in (a[0],z[0])) and all(25.35<=y<=28 for y in (a[1],z[1])):
  if sorted([a,z]) in [sorted([[54.5,25.35],[54.52,25.35]]),sorted([[54.5,25.35],[54.5,26.45]])]:continue
  assert t.GetWidth()==p.FromMM(.2);removed.append(t.m_Uuid.AsString());b.Remove(t);held.append(t)
assert len(removed)>10
start=(52.48,28)
if os.environ.get('PHOENIX_ROTATE_C2007')=='1':
 cap=next(f for f in b.GetFootprints() if f.GetReference()=='C2007');angle=int(os.environ.get('PHOENIX_CAP_ANGLE','180'));cap.SetOrientationDegrees(angle);cap.SetPosition(vec((51.04,28) if angle==180 else (51.52,27.52) if angle==90 else (51.52,28.48)));start=(50.56,28) if angle==180 else (51.52,27.04) if angle==90 else (51.52,28.96)
 assert next(q for q in cap.Pads() if q.GetNumber()=='1').GetPosition()==vec((51.52,28))
xy=tuple(map(float,os.environ.get('PHOENIX_GROUND_XY','55,28').split(',')))
v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(v)
t=p.PCB_TRACK(b);t.SetStart(vec(start));t.SetEnd(vec(xy));t.SetWidth(p.FromMM(.2));t.SetLayer(p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(t)
case=os.environ.get('PHOENIX_GROUND_CASE','input-ground-local-002');assert '/' not in case
r=D/'runs'/case;r.mkdir(exist_ok=True);out=r/'phy-joint.kicad_pcb'
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',r/'fp-lib-table');p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
m={'source':str(src),'source_sha256':cp['sha256'],'candidate':str(out),'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'removed':removed,'required_pairs':[[['C2007','2'],['Y2001','2']]],'new_ground_via_uuid':v.m_Uuid.AsString(),'new_ground_track_uuid':t.m_Uuid.AsString(),'power_layout_accepted':False,'assembly_ready':False,'limitations':['Local ground return change only; RF/clock impedance and via manufacturing still unqualified.','Power corridor remains incomplete.']}
mp=r/'input.json';mp.write_text(json.dumps(m,indent=2)+'\n');os.execv(sys.executable,[sys.executable,str(H/'tools/parallel_phy_sw_joint.py'),'--audit',str(mp)])
