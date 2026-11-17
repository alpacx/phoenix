#!/usr/bin/env python3
"""Try a closer C515 and restore its ground on a temporary PCB; never promote."""
import argparse,hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
import pcbnew as p
from local_pcb_router import LocalRouter
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text());src=D/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
original_src=src
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--compact-parent',action='store_true');args=parser.parse_args()
parent_hash=cp['sha256']
if args.compact_parent:
 parent=json.loads((D/'pcb/phy-compact-ground-probe.json').read_text())
 assert parent['status']=='COMPACT_GROUNDS_GEOMETRY_PASSED' and parent['source_sha256']==cp['sha256']
 src=Path(parent['temporary_candidate']);parent_hash=parent['candidate_sha256']
 assert hashlib.sha256(src.read_bytes()).hexdigest()==parent_hash
b=p.LoadBoard(str(src));old=p.LoadBoard(str(src));fs={f.GetReference():f for f in b.GetFootprints()}
old_necks={'1ce012e4-f7db-493a-a4c4-30dec5ed03f7':(80.48,33,80.5,33),'9bafe2c0-f71e-4e19-9aca-a33c516b7728':(80.5,33,81.2,33)}
replaced=list(old_necks);held=[]
for t in list(b.GetTracks()):
 if t.m_Uuid.AsString() in replaced:
  assert t.GetNetname()=='GND' and t.GetLayer()==p.F_Cu
  assert (t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y)==tuple(p.FromMM(v) for v in old_necks[t.m_Uuid.AsString()])
  b.Remove(t);held.append(t)
assert len(held)==2
f=fs['C515'];f.SetPosition(p.VECTOR2I(p.FromMM(61.7),p.FromMM(24)));f.SetOrientationDegrees(90)
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
r=LocalRouter(b,(58,21,66,28),width=.2,grid=.05)
tree=r.paths_from(r.blocked(p.F_Cu,'GND'),r.cell(r.xy(pads['C515','2'])),2)
blocked=set()
for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:blocked |= r.blocked(layer,'GND',.45,True)
choices=sorted((q for q in tree['distances'] if q not in blocked),key=tree['distances'].get)
result={'source_sha256':cp['sha256'],'parent_sha256':parent_hash,'includes_compact_inductor':args.compact_parent,'checkpoint_modified':False,'assembly_ready':False,'position_mm':[61.7,24],'angle_deg':90,
 'limitations':['Only input bulk placement and ground trial; main power path, return impedance and regulator stability unqualified.',
 'The old 0.72 mm ground pad branch is explicitly replaced; all other copper is retained. Temporary candidate is not authoritative.']}
if not choices:result['status']='NO_GROUND_ESCAPE'
else:
 q=choices[0];path=[r.xy(pads['C515','2'])]+r.path_from_tree(tree,q)
 def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
 for a,z in zip(path,path[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(.2));t.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(t)
 v=p.PCB_VIA(b);v.SetPosition(vec(r.world(q)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(v)
 outdir=Path(tempfile.mkdtemp(prefix='phoenix-input-bulk-'));out=outdir/src.name
 for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
 table=(src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent))
 (outdir/'fp-lib-table').write_text(table)
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);b.BuildConnectivity()
 drc=outdir/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 base=src.parent/'drc.json' if args.compact_parent else src.with_name(src.stem+'-drc.json')
 new=introduced(json.loads(base.read_text()),json.loads(drc.read_text()))
 reached={i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(pads['C515','2'])}
 connected=pads['U20','2'].m_Uuid.AsString() in reached
 result['preservation']=verify_preservation(old,b,replaced_copper=replaced)
 if args.compact_parent:result['root_preservation']=verify_preservation(p.LoadBoard(str(original_src)),b,replaced_copper=replaced+list(parent['preservation']['explicitly_replaced_copper']))
 key=lambda row:(row['reservation'],row['ref'])
 conflicts=sorted({key(row) for row in screen(b)}-{key(row) for row in screen(old)})
 result.update(status='LOCAL_GROUND_TRIAL_PASSED' if not new and connected and not conflicts else 'LOCAL_GROUND_TRIAL_REJECTED',
  temporary_candidate=str(out),candidate_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),ground_connected=connected,new_drc_violations=new,new_mechanical_conflicts=conflicts,ground_via_mm=r.world(q))
assert hashlib.sha256(original_src.read_bytes()).hexdigest()==cp['sha256']
report_name='phy-compact-combined-ground-probe.json' if args.compact_parent else 'phy-input-bulk-ground-probe.json'
(D/'pcb'/report_name).write_text(json.dumps(result,indent=2)+'\n')
print(result['status'])
