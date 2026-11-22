#!/usr/bin/env python3
"""Isolated joint output/SW/ground-corridor experiment; never qualifies pin fanout."""
import argparse,hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from pcb_route_guards import require_constant_width_branch
from audit_mount_component_reservations import screen
H=Path(__file__).resolve().parents[1]
S=H/'migration-rk3562/experiments/phy-compact-inductor/corridor'
D=H/'migration-rk3562/experiments/phy-power-parallel'
D.mkdir(parents=True,exist_ok=True)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
if '--audit' in sys.argv:
 m=json.loads(Path(sys.argv[-1]).read_text());src=Path(m['source']);out=Path(m['candidate']);drc=out.parent/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 raw=json.loads(drc.read_text());new=introduced(json.loads((src.parent/'drc.json').read_text()),raw);ids={i for r in new for i in r['items']}
 m.update(new_violations=new,details=[r for r in raw['violations'] if any(i['uuid'] in ids for i in r['items'])],status='JOINT_SW_GEOMETRY_REJECTED',power_layout_accepted=False,assembly_ready=False)
 if not new:
  old=p.LoadBoard(str(src));b=p.LoadBoard(str(out));m['preservation']=verify_preservation(old,b,replaced_copper=m['removed']);key=lambda r:(r['reservation'],r['ref']);m['new_mechanical_conflicts']=sorted({key(r) for r in screen(b)}-{key(r) for r in screen(old)});b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};m['checks']=[]
  for a,z in [(('U5','30'),('L501','1')),(('L501','2'),('C511','1')),(('R522','2'),('C515','2')),(('C515','1'),('C517','1'))]+[(tuple(a),tuple(z)) for a,z in m.get('required_pairs',[])+([m['additional_required_pair']] if m.get('additional_required_pair') else [])]:
   connected=pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])};m['checks'].append({'from':'.'.join(a),'to':'.'.join(z),'connected':connected})
  if all(r['connected'] for r in m['checks']) and not m['new_mechanical_conflicts']:m['status']='JOINT_SW_GEOMETRY_PASSED_PIN_FANOUT_HOLD'
 (out.parent/'report.json').write_text(json.dumps(m,indent=2)+'\n');print(m['status'],flush=True);os._exit(0)
ap=argparse.ArgumentParser();ap.add_argument('--case',default='joint-001');ap.add_argument('--output-x',type=float,default=57.025);ap.add_argument('--bulk-0805',action='store_true');ap.add_argument('--bulk-16v',action='store_true');args=ap.parse_args();assert '/' not in args.case
base=D/'baseline';base.mkdir(exist_ok=True)
if not (base/'checkpoint.json').exists():
 cp=json.loads((S/'checkpoint.json').read_text());source=S/cp['board'];assert sha(source)==cp['sha256']
 for ext in ['.kicad_pcb','.kicad_pro','.kicad_dru']:shutil.copy2(source.with_suffix(ext),base/('source'+ext))
 (base/'fp-lib-table').write_text((source.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(source.parent)))
 shutil.copy2(source.parent/'drc.json',base/'drc.json')
 main=json.loads((H/'migration-rk3562/experiments/pmic-ldo-inputs/pcb/ethernet-dvdd33-bypass.json').read_text())['rxclk_route']
 output=json.loads((S.parent/'study-checkpoint.json').read_text())['path_mm']
 inputs={'source_checkpoint':str(S/'checkpoint.json'),'source_sha256':cp['sha256'],'old_ground':cp['source_reports']['rxclk-strap'],'new_ground':main,'old_output':output}
 (base/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');(base/'checkpoint.json').write_text(json.dumps({'board':'source.kicad_pcb','sha256':cp['sha256'],'status':'FROZEN_EXPERIMENT_BASELINE'},indent=2)+'\n')
cp=json.loads((base/'checkpoint.json').read_text());src=base/cp['board'];assert sha(src)==cp['sha256'];inputs=json.loads((base/'inputs.json').read_text());b=p.LoadBoard(str(src));vec=lambda q:p.VECTOR2I(*(p.FromMM(v) for v in q));removed=[];held=[]
assert not (args.bulk_0805 and args.bulk_16v)
if args.bulk_16v:
 cap=next(f for f in b.GetFootprints() if f.GetReference()=='C515');cap.SetValue('4.7uF CL10A475KO8NNNC CANDIDATE 16V')
if args.bulk_0805:
 oldcap=next(f for f in b.GetFootprints() if f.GetReference()=='C515');oldpads={q.GetNumber():q for q in oldcap.Pads()}
 cap=p.PCB_IO_KICAD_SEXPR().FootprintLoad('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Capacitor_SMD.pretty','C_0805_2012Metric',False)
 cap.SetReference('C515');cap.SetValue('4.7uF CL21A475KAQNNNE CANDIDATE');cap.SetFPID(p.LIB_ID('Capacitor_SMD','C_0805_2012Metric'));cap.SetUuid(oldcap.m_Uuid)
 for q in cap.Pads():q.SetUuid(oldpads[q.GetNumber()].m_Uuid);q.SetNet(oldpads[q.GetNumber()].GetNet())
 cap.SetPosition(oldcap.GetPosition());cap.SetOrientationDegrees(oldcap.GetOrientationDegrees());cap.Reference().SetVisible(False);b.Remove(oldcap);held.append(oldcap);b.Add(cap)
def remove_branch(points,net,layer,width):
 edges={(tuple(vec(a)),tuple(vec(z))) for a,z in zip(points,points[1:]) if vec(a)!=vec(z)};seen=set()
 for t in list(b.GetTracks()):
  if isinstance(t,p.PCB_VIA) or t.GetNetname()!=net or t.GetLayer()!=layer:continue
  edge=tuple(t.GetStart()),tuple(t.GetEnd())
  if edge in edges:
   assert t.GetWidth()==p.FromMM(width);removed.append(t.m_Uuid.AsString());seen.add(edge);b.Remove(t);held.append(t)
 assert seen==edges,(net,len(seen),len(edges))
remove_branch(inputs['old_ground']['ground_path_mm'],'GND',p.B_Cu,.2)
remove_branch(inputs['old_output'],'+1V0_PHY',p.F_Cu,1.55)
oldvia=vec(inputs['old_ground']['ground_via_mm'])
for t in list(b.GetTracks()):
 if isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and t.GetPosition()==oldvia:
  assert t.GetWidth(p.F_Cu)==p.FromMM(.45) and t.GetDrillValue()==p.FromMM(.2);removed.append(t.m_Uuid.AsString());b.Remove(t);held.append(t)
assert len(removed)>3
records=[]
def route(points,net,layer,width,label):
 tracks=[]
 for a,z in zip(points,points[1:]):
  if vec(a)==vec(z):continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t);tracks.append(t)
 guard=require_constant_width_branch(tracks,net=net,layer=layer,width_mm=width,start_mm=points[0],end_mm=points[-1]);records.append({'label':label,'path_mm':points,'width_mm':width,'net':net,'layer':b.GetLayerName(layer),'guard':guard,'length_mm':sum(math.dist(a,z) for a,z in zip(points,points[1:])),'uuids':[t.m_Uuid.AsString() for t in tracks]})
route(inputs['new_ground']['ground_path_mm'],'GND',p.B_Cu,.2,'rxclk_ground')
viaxy=inputs['new_ground']['ground_via_mm'];v=p.PCB_VIA(b);v.SetPosition(vec(viaxy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(v)
output=[(args.output_x,30),(56.425,30+args.output_x-56.425),(56.425,32.2)];route(output,'+1V0_PHY',p.F_Cu,1.55,'output')
route([(60.1,27.7),(58.825,28.975),(58.825,30)],'PHY_SW',p.F_Cu,1.55,'switch_trunk')
route([(61.2,28.6),(60.7,28.1)],'PHY_SW',p.F_Cu,.2,'pin_fanout')
outdir=D/'runs'/args.case;outdir.mkdir(parents=True,exist_ok=True);out=outdir/'phy-joint.kicad_pcb'
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(base/'fp-lib-table',outdir/'fp-lib-table');filler=p.ZONE_FILLER(b);filler.Fill(b.Zones());p.SaveBoard(str(out),b)
m={'source':str(src),'source_sha256':cp['sha256'],'candidate':str(out),'candidate_sha256':sha(out),'removed':removed,'routes':records,'new_ground_via_mm':viaxy,'new_ground_via_diameter_mm':.45,'new_ground_via_drill_mm':.2,'new_ground_via_uuid':v.m_Uuid.AsString(),'historical_60mil_width_met_on_entire_path':False,'main_checkpoint_modified':False,'bulk_0805_candidate':args.bulk_0805,'bulk_16v_candidate':args.bulk_16v,'limitations':['QFN pin fanout remains 0.20 mm, 0.707 mm long; historical width requirement is not waived. No power-layout adoption or qualification.','Output/inductor termination is offset 0.15 mm within its existing pad; both broad branches remain 1.55 mm.','Need applicable manufacturer fanout guidance and electrical/thermal/ripple qualification.']}
mp=outdir/'input.json';mp.write_text(json.dumps(m,indent=2)+'\n');os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),'--audit',str(mp)])
