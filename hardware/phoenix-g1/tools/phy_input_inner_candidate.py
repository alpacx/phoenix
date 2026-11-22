#!/usr/bin/env python3
"""Full-width PHY input candidate on an inner signal layer. Isolated, not adopted."""
import pcbnew as p,json,hashlib,shutil,sys,os
from pathlib import Path
from pcb_route_guards import require_constant_width_branch
H=Path(__file__).resolve().parents[1];D=H/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((D/'load-c513-checkpoint.json').read_text());src=D/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));vec=lambda xy:p.VECTOR2I(*(p.FromMM(v) for v in xy));tracks=[];vias=[]
case=sys.argv[1] if len(sys.argv)>1 else 'input-in2-001'
assert case in ('input-in2-001','input-in2-002')
points=[(54,26.4),(54,25.5),(55.5,24),(60.9,24),(60.9,24.2)]
if case=='input-in2-002':points=[(54,26.4),(54,25.5),(55.5,24),(59.9,24),(60.9,25),(60.9,24.2)]
net='+3V3_PHY';width=1.05
for a,z in zip(points,points[1:]):
 t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(p.In2_Cu);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t);tracks.append(t)
guard=require_constant_width_branch(tracks,net=net,layer=p.In2_Cu,width_mm=width,start_mm=points[0],end_mm=points[-1])
for xy in [(53.7,26.4),(54.3,26.4),(60.9,23.9),(60.9,24.5)]:
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v);vias.append(v)
for a,z in [((53.51,27),(54,26.4)),((60.9,24.2),(61.975,24.2))]:
 t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
r=D/'runs'/case;r.mkdir(exist_ok=True);out=r/'phy-joint.kicad_pcb'
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',r/'fp-lib-table');p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
m={'source':str(src),'source_sha256':cp['sha256'],'candidate':str(out),'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'removed':[],'required_pairs':[[['R530','2'],['C515','1']]],'routes':[{'label':case,'path_mm':points,'width_mm':width,'net':net,'layer':'In2.Cu','guard':guard,'uuids':[t.m_Uuid.AsString() for t in tracks]}],'power_layout_accepted':False,'assembly_ready':False,'limitations':['Via current, manufacturing clearance, input loop and PI not qualified.','Inherited SW QFN neck hold remains.']}
mp=r/'input.json';mp.write_text(json.dumps(m,indent=2)+'\n');os.execv(sys.executable,[sys.executable,str(H/'tools/parallel_phy_sw_joint.py'),'--audit',str(mp)])
