#!/usr/bin/env python3
"""Explicit single-layer full-width feed probes; rejected routes are evidence only."""
import json,os,sys,hashlib,shutil
from pathlib import Path
import pcbnew as p
from pcb_route_guards import require_constant_width_branch
H=Path(__file__).resolve().parents[1];D=H/'migration-rk3562/experiments/phy-power-parallel';case=sys.argv[1];cp=json.loads((D/('load-c514-checkpoint.json' if case.startswith('load-in3-c513') else 'load-checkpoint.json' if case.startswith('load-in3-c514') else 'checkpoint.json')).read_text());src=D/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));case=sys.argv[1]
if case.startswith('load-in3-c513'):
 cap=next(f for f in b.GetFootprints() if f.GetReference()=='C513');cap.SetPosition(p.VECTOR2I(p.FromMM(64.9),p.FromMM(35.05)));cap.SetOrientationDegrees(270)
 if case in ['load-in3-c513b','load-in3-c513c','load-in3-c513d']:cap.SetPosition(p.VECTOR2I(p.FromMM(65.4),p.FromMM(34.4)));cap.SetOrientationDegrees(0)
 if case in ['load-in3-c513c','load-in3-c513d']:cap.SetPosition(p.VECTOR2I(p.FromMM(65.4),p.FromMM(34.5)))
if case=='feed-front':net='+3V3_PHY';width=1.05;points=[(53.56,27),(54.8,27),(56.6,25.2),(61.975,25.2),(61.975,24.2)]
elif case.startswith('load-in3-c513'):net='+1V0_PHY';width=1.55;points=[(64.8,28.9),(64.8,32.8),(65.2,33.2),(65.2,34.65)]
elif case=='load-front':net='+1V0_PHY';width=1.55;points=[(56.425,32.2),(55,32.2),(55,36.5),(62.27,36.5),(62.27,34.75)]
elif case=='load-in3-c514c':net='+1V0_PHY';width=1.55;points=[(62.425,30.375),(63.9,28.9),(66.75,28.9)]
elif case=='load-in3-c514b':net='+1V0_PHY';width=1.55;points=[(62.425,30.375),(63.8,29),(66.75,29)]
elif case.startswith('load-in3-c514'):net='+1V0_PHY';width=1.55;points=[(62.425,30.375),(63.8,29),(66.75,29),(66.75,29.1)]
elif case=='load-in3-north2':net='+1V0_PHY';width=1.55;points=[(56.2,31.1),(56.6,30.7),(56.6,29.75),(61.8,29.75),(62.425,30.375),(62.425,34.5)]
elif case=='load-in3-north':net='+1V0_PHY';width=1.55;points=[(56.2,31.1),(56.6,30.7),(56.6,29.5),(61.8,29.5),(62.425,30.125),(62.425,34.5)]
elif case.startswith('load-in3'):net='+1V0_PHY';width=1.55;points=[(56.3,31.5),(56.3,36.7),(61.95,36.7),(61.95,35.1)]
else:raise ValueError(case)
tracks=[];vias=[];removed=[];held=[]
if case in ['load-in3-c513b','load-in3-c513c','load-in3-c513d']:
 for t in list(b.GetTracks()):
  if not isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and t.GetLayer()==p.F_Cu and t.GetStart() in [p.VECTOR2I(p.FromMM(76.98),p.FromMM(37.5)),p.VECTOR2I(p.FromMM(77),p.FromMM(37.5))]:
   assert p.ToMM(t.GetLength())<.71;removed.append(t.m_Uuid.AsString());b.Remove(t);held.append(t)
for a,z in zip(points,points[1:]):
 t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(*(p.FromMM(v) for v in a)));t.SetEnd(p.VECTOR2I(*(p.FromMM(v) for v in z)));t.SetWidth(p.FromMM(width));t.SetLayer(p.In3_Cu if case.startswith('load-in3') else p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t);tracks.append(t)
guard=require_constant_width_branch(tracks,net=net,layer=p.In3_Cu if case.startswith('load-in3') else p.F_Cu,width_mm=width,start_mm=points[0],end_mm=points[-1])
if case.startswith('load-in3'):
 for xy in ([(64.55,34.25),(65.1,34.25)] if case in ['load-in3-c513c','load-in3-c513d'] else [(64.6,34.4),(65.2,34.4)] if case in ['load-in3-c513b','load-in3-c513c','load-in3-c513d'] else [(64.75,34.65),(65.35,34.65)] if case.startswith('load-in3-c513') else [(66.45,29.1),(67.05,29.1)] if case.startswith('load-in3-c514') else [(56.2,31.5),(56.2,30.7),(61.9,34.5),(62.45,34.5)] if case.startswith('load-in3-north') else [(55.9,31.5),(56.7,31.5),(61.55,35.1),(62.35,35.1)]):
  v=p.PCB_VIA(b);v.SetPosition(p.VECTOR2I(*(p.FromMM(x) for x in xy)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v);vias.append({'uuid':v.m_Uuid.AsString(),'xy_mm':xy,'diameter_mm':.6,'drill_mm':.3})
 for a,z in ([] if case.startswith('load-in3-north') or case.startswith('load-in3-c514') or case.startswith('load-in3-c513') else [((56.425,32.2),(56.3,31.5)),((61.95,35.1),(61.95,34.75))]):
  t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(*(p.FromMM(v) for v in a)));t.SetEnd(p.VECTOR2I(*(p.FromMM(v) for v in z)));t.SetWidth(p.FromMM(width));t.SetLayer(p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
if case.startswith('load-in3-c513'):
 v=p.PCB_VIA(b);v.SetPosition(p.VECTOR2I(p.FromMM(66.5 if case in ['load-in3-c513b','load-in3-c513c','load-in3-c513d'] else 64.9),p.FromMM(34.3 if case in ['load-in3-c513b','load-in3-c513c','load-in3-c513d'] else 36.05)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(v)
 t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(p.FromMM(65.88 if case in ['load-in3-c513b','load-in3-c513c','load-in3-c513d'] else 64.9),p.FromMM(34.5 if case in ['load-in3-c513c','load-in3-c513d'] else 34.4 if case in ['load-in3-c513b','load-in3-c513c','load-in3-c513d'] else 35.53)));t.SetEnd(v.GetPosition());t.SetWidth(p.FromMM(.2));t.SetLayer(p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(t)
pin_branch=[]
if case=='load-in3-c513d':
 pinpoints=[(64,33.4),(64,33.9),(64.6,34.5),(64.92,34.5)]
 for a,z in zip(pinpoints,pinpoints[1:]):
  t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(*(p.FromMM(x) for x in a)));t.SetEnd(p.VECTOR2I(*(p.FromMM(x) for x in z)));t.SetWidth(p.FromMM(.2));t.SetLayer(p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t);pin_branch.append(t)
 require_constant_width_branch(pin_branch,net=net,layer=p.F_Cu,width_mm=.2,start_mm=pinpoints[0],end_mm=pinpoints[-1])
output_case=os.environ.get('PHOENIX_PHY_OUTPUT_CASE',case);assert '/' not in output_case;run=D/'runs'/output_case;run.mkdir(exist_ok=True);out=run/'phy-joint.kicad_pcb'
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',run/'fp-lib-table');p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
m={'source':str(src),'source_sha256':cp['sha256'],'candidate':str(out),'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'removed':removed,'additional_pin_fanout_qualified':False,'additional_pin_fanout_uuids':[t.m_Uuid.AsString() for t in pin_branch],'via_array':vias,'current_via_PI_qualified':False,'via_pad_overlap_manufacturing_qualified':False,'required_pairs':[[['R530','2'],['C515','1']]] if case=='feed-front' else [[['C511','1'],['C513' if case.startswith('load-in3-c513') else 'C514' if case.startswith('load-in3-c514') else 'C512','1']]],'additional_required_pair':[['U5','8'],['C513','1']] if case=='load-in3-c513d' else None,'routes':[{'label':case,'path_mm':points,'width_mm':width,'net':net,'layer':'In3.Cu' if case.startswith('load-in3') else 'F.Cu','guard':guard,'uuids':[t.m_Uuid.AsString() for t in tracks]}],'historical_60mil_width_met_on_entire_path':False,'main_checkpoint_modified':False,'power_layout_accepted':False,'assembly_ready':False,'limitations':['Manual full-width geometry only; no current/via/PI qualification. In3 studies are post-inductor distribution, not a waiver for local REG_OUT/DVDD33. Ground planes retain their role. Via-to-pad overlap requires fabrication/process review. Rejected geometry must not be adopted.']}
if case.startswith('load-in3-c513'):m['required_pairs'].append([['C513','2'],['C515','2']])
mp=run/'input.json';mp.write_text(json.dumps(m,indent=2)+'\n');os.execv(sys.executable,[sys.executable,str(H/'tools/parallel_phy_sw_joint.py'),'--audit',str(mp)])
