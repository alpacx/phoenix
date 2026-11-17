#!/usr/bin/env python3
"""Try a closer C511 and restore its ground on a temporary PCB; never promote."""
import argparse,hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
import pcbnew as p
from local_pcb_router import LocalRouter
from drc_regression import introduced
from pcb_preservation import verify_preservation
from pcb_route_guards import require_constant_width_branch
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text());src=D/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
original_src=src
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--with-input-bulk',action='store_true');parser.add_argument('--detour-extent',nargs=4,type=float,default=[44,24,58,38]);parser.add_argument('--capacitor-position',nargs=2,type=float,default=[52,30.25]);parser.add_argument('--capacitor-angle',type=int,choices=[0,90,180,270],default=180);args=parser.parse_args()
parent_hash=cp['sha256']
if args.with_input_bulk:
 proof=json.loads((D/'pcb/phy-input-bulk-ground-probe.json').read_text())
 assert proof['status']=='LOCAL_GROUND_TRIAL_PASSED' and proof['source_sha256']==cp['sha256']
 src=Path(proof['temporary_candidate']);parent_hash=proof['candidate_sha256']
 assert hashlib.sha256(src.read_bytes()).hexdigest()==parent_hash
b=p.LoadBoard(str(src));old=p.LoadBoard(str(src));fs={f.GetReference():f for f in b.GetFootprints()}
old_necks={'410979f8-580d-4434-9883-ad3cf785333c':(76.98,36,77,36),'d60df459-ad1a-4299-b3bd-5b7da6f5f7ec':(77,36,77.7,36),'545b053b-db69-41f9-bd1f-f3135bcf88b9':(53.5,29.8,49.75,29.8)}
replaced=list(old_necks);held=[]
for t in list(b.GetTracks()):
 if t.m_Uuid.AsString() in replaced:
  assert t.GetNetname()=='GND' and t.GetLayer()==p.F_Cu
  assert t.GetWidth()==p.FromMM(.8 if t.m_Uuid.AsString()=='545b053b-db69-41f9-bd1f-f3135bcf88b9' else .2),'Unexpected original branch width'
  assert (t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y)==tuple(p.FromMM(v) for v in old_necks[t.m_Uuid.AsString()])
  b.Remove(t);held.append(t)
assert len(held)==3
f=fs['C511'];f.SetPosition(p.VECTOR2I(*(p.FromMM(v) for v in args.capacitor_position)));f.SetOrientationDegrees(args.capacitor_angle)
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
r=LocalRouter(b,tuple(args.detour_extent),width=.8,grid=.05)
wide_blocked=r.blocked(p.F_Cu,'GND')
start=r.cell((53.5,29.8));goal=r.cell(r.xy(pads['C2204','2']))
reroute=r.solve(wide_blocked,start,goal)
if not reroute:
 report={'status':'REJECTED_NO_GROUND_DETOUR_AT_ORIGINAL_WIDTH','source_sha256':cp['sha256'],'parent_sha256':parent_hash,'includes_input_bulk':args.with_input_bulk,'position_mm':args.capacitor_position,'angle_deg':args.capacitor_angle,'original_ground_width_mm':.8,'screen_bounds_mm':args.detour_extent,'start_blocked':start in wide_blocked,'goal_blocked':goal in wide_blocked,'checkpoint_modified':False,'assembly_ready':False,'limitations':['Earlier 0.20 mm ground detour is rejected: original segment is 0.80 mm wide.','No 0.80 mm path found in bounded screen; not proof of global impossibility.']}
 name='phy-combined-bulk-ground-probe.json' if args.with_input_bulk else 'phy-output-bulk-ground-probe.json'
 (D/'pcb'/name).write_text(json.dumps(report,indent=2)+'\n')
 assert hashlib.sha256(original_src.read_bytes()).hexdigest()==cp['sha256']
 print(report['status']);raise SystemExit(0)
detour_tracks=[]
for a,z in zip(reroute,reroute[1:]):
 t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(*(p.FromMM(v) for v in a)));t.SetEnd(p.VECTOR2I(*(p.FromMM(v) for v in z)));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(.8));t.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(t);detour_tracks.append(t)
width_guard=require_constant_width_branch(detour_tracks,net='GND',layer=p.F_Cu,width_mm=.8,start_mm=(53.5,29.8),end_mm=r.xy(pads['C2204','2']))
r=LocalRouter(b,(48,27,55,33),width=.2,grid=.05)
tree=r.paths_from(r.blocked(p.F_Cu,'GND'),r.cell(r.xy(pads['C511','2'])),2)
blocked=set()
for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:blocked |= r.blocked(layer,'GND',.45,True)
choices=sorted((q for q in tree['distances'] if q not in blocked),key=tree['distances'].get)
result={'source_sha256':cp['sha256'],'parent_sha256':parent_hash,'includes_input_bulk':args.with_input_bulk,'checkpoint_modified':False,'assembly_ready':False,'width_guard':width_guard,'position_mm':args.capacitor_position,'angle_deg':args.capacitor_angle,
 'limitations':['Only output bulk placement and ground trial; switching and main power path, return impedance and regulator stability unqualified.',
 'The old 0.72 mm capacitor ground branch and one 3.75 mm ground segment are explicitly replaced; all other copper is retained. Temporary candidate is not authoritative.']}
if not choices:result['status']='NO_GROUND_ESCAPE'
else:
 q=choices[0];path=[r.xy(pads['C511','2'])]+r.path_from_tree(tree,q)
 def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
 for a,z in zip(path,path[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(.2));t.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(t)
 v=p.PCB_VIA(b);v.SetPosition(vec(r.world(q)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(v)
 outdir=Path(tempfile.mkdtemp(prefix='phoenix-output-bulk-'));out=outdir/src.name
 for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
 table=(src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent))
 (outdir/'fp-lib-table').write_text(table)
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);b.BuildConnectivity()
 drc=outdir/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 base=src.parent/'drc.json' if args.with_input_bulk else src.with_name(src.stem+'-drc.json')
 new=introduced(json.loads(base.read_text()),json.loads(drc.read_text()))
 reached={i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(pads['C511','2'])}
 connected=pads['U20','2'].m_Uuid.AsString() in reached
 result['preservation']=verify_preservation(old,b,replaced_copper=replaced)
 if args.with_input_bulk:
  root_replaced=replaced+list(proof['preservation']['explicitly_replaced_copper'])
  result['root_preservation']=verify_preservation(p.LoadBoard(str(original_src)),b,replaced_copper=root_replaced)
 key=lambda row:(row['reservation'],row['ref'])
 conflicts=sorted({key(row) for row in screen(b)}-{key(row) for row in screen(old)})
 result.update(status='LOCAL_GROUND_TRIAL_PASSED' if not new and connected and not conflicts else 'LOCAL_GROUND_TRIAL_REJECTED',
  temporary_candidate=str(out),candidate_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),ground_connected=connected,new_drc_violations=new,new_mechanical_conflicts=conflicts,ground_via_mm=r.world(q),ground_detour_mm=reroute)
assert hashlib.sha256(original_src.read_bytes()).hexdigest()==cp['sha256']
report_name='phy-combined-bulk-ground-probe.json' if args.with_input_bulk else 'phy-output-bulk-ground-probe.json'
(D/'pcb'/report_name).write_text(json.dumps(result,indent=2)+'\n')
print(result['status'])
