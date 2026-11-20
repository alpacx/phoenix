#!/usr/bin/env python3
"""Isolated C522 relocation with explicit XOUT replacement; all power/clock qualification held."""
import json,os,sys,hashlib,shutil
from pathlib import Path
import pcbnew as p
from pcb_route_guards import require_constant_width_branch
H=Path(__file__).resolve().parents[1];D=H/'migration-rk3562/experiments/phy-power-parallel';cp=json.loads((D/'load-c513-checkpoint.json').read_text());src=D/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));vec=lambda xy:p.VECTOR2I(*(p.FromMM(v) for v in xy));removed=[];held=[];records=[]
for t in list(b.GetTracks()):
 if isinstance(t,p.PCB_VIA):continue
 a,z=tuple(p.ToMM(v) for v in t.GetStart()),tuple(p.ToMM(v) for v in t.GetEnd())
 clock=t.GetNetname()=='PHY_XOUT' and t.GetLayer()==p.F_Cu and min(a[1],z[1])>=31.6 and max(a[1],z[1])<=33.025
 stub=t.GetNetname()=='GND' and t.GetLayer()==p.F_Cu and a[1]==34.5 and 82.98<=a[0]<=83
 xin=t.GetNetname()=='PHY_XIN' and t.GetLayer()==p.B_Cu and min(a[1],z[1])>=31 and max(a[1],z[1])<=34.825
 if clock or stub or xin:removed.append(t.m_Uuid.AsString());b.Remove(t);held.append(t)
assert len(removed)>=8
cap=next(f for f in b.GetFootprints() if f.GetReference()=='C522');cap.Flip(cap.GetPosition(),False);cap.SetPosition(vec((61.5,31.8)));cap.SetOrientationDegrees(0)
def route(points,net,layer,width,label):
 ts=[]
 for a,z in zip(points,points[1:]):
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetLayer(layer);t.SetWidth(p.FromMM(width));t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t);ts.append(t)
 guard=require_constant_width_branch(ts,net=net,layer=layer,width_mm=width,start_mm=points[0],end_mm=points[-1]);records.append({'label':label,'path_mm':points,'net':net,'layer':b.GetLayerName(layer),'width_mm':width,'guard':guard,'uuids':[t.m_Uuid.AsString() for t in ts]})
route([(60.6,31.6),(59.375,31.6)],'PHY_XOUT',p.F_Cu,.15,'clock_pin')
route([(59.375,31.6),(59.375,32.6),(58.95,33.025),(57.825,33.025)],'PHY_XOUT',p.F_Cu,.2,'clock_body')
route([(59.875,31),(59.35,31.525),(59.35,32.6),(59.95,33.2),(61.25,33.2),(61.25,34.825)],'PHY_XIN',p.B_Cu,.2,'clock_input_back')
route([(60.6,32),(59.9,32)],'+1V0_PHY',p.F_Cu,.2,'pin38_fanout')
route([(62.425,32.1),(60.55,32.1)],'+1V0_PHY',p.In3_Cu,1.55,'post_inductor')
route([(60.55,32.1),(60.7,31.9)],'+1V0_PHY',p.B_Cu,1.55,'back_load')
vias=[]
for xy,net in [((59.9,32),'+1V0_PHY'),((61.98,31.8),'GND')]:
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v);vias.append({'uuid':v.m_Uuid.AsString(),'xy_mm':xy,'net':net,'diameter_mm':.45,'drill_mm':.2})
run=D/'runs/c522-clock2';run.mkdir(exist_ok=True);out=run/'phy-joint.kicad_pcb'
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',run/'fp-lib-table');p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
m={'source':str(src),'source_sha256':cp['sha256'],'candidate':str(out),'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'removed':removed,'routes':records,'via_array':vias,'required_pairs':[[['C511','1'],['C522','1']],[['U5','38'],['C522','1']],[['C522','2'],['C515','2']]],'current_via_PI_qualified':False,'clock_loop_qualified':False,'via_pad_overlap_manufacturing_qualified':False,'historical_60mil_width_met_on_entire_path':False,'main_checkpoint_modified':False,'limitations':['Backside decoupler and clock reroute are experimental; loop/clock loading/EMI unqualified.','Single local power fanout via 0.45/0.20 mm due QFN/oscillator escape constraints; not equivalent to two 0.60/0.30 distribution vias. Current/PI qualification mandatory; power layout not accepted.','1.55 mm trunks preserved; 0.20 mm pin38 fanout remains unqualified.']};mp=run/'input.json';mp.write_text(json.dumps(m,indent=2)+'\n');os.execv(sys.executable,[sys.executable,str(H/'tools/parallel_phy_sw_joint.py'),'--audit',str(mp)])
