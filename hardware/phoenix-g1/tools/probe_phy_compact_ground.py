#!/usr/bin/env python3
"""Restore grounds after compact-inductor placement, preserving branch/via sizes."""
import argparse,hashlib,json,shutil,subprocess,tempfile,math
from pathlib import Path
import pcbnew as p
from local_pcb_router import LocalRouter
from pcb_preservation import verify_preservation
from pcb_route_guards import require_constant_width_branch
from drc_regression import introduced
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
from phy_study_source import load_source
cp,root=load_source(D)
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bulk-0603',action='store_true');parser.add_argument('--reserve-output',action='store_true');args=parser.parse_args()
placement_name='phy-compact-0603-placement-probe.json' if args.bulk_0603 else 'phy-compact-power-placement-probe.json'
proof=json.loads((D/'pcb'/placement_name).read_text());src=Path(proof['temporary_candidate'])
assert proof['source_sha256']==cp['sha256']==hashlib.sha256(root.read_bytes()).hexdigest()
assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['candidate_sha256']
b=p.LoadBoard(str(src));old=p.LoadBoard(str(root));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
ids=['353c793c-2fde-4e45-a944-7f6b0ff7d320','4bb1168a-d647-4743-9dd8-60be61a4eee6','6a398cd1-9612-444e-b43d-0f00b6829a79','6e11dda3-002c-49b6-9abe-eb30ca22e7e2','8653b1df-8759-4800-8bf8-337ab3e20f29','8da758e9-215b-4c35-91d3-82bc52782f01','c7be60d9-fe0d-4326-acbc-8373b5099c66','9a777003-3bdd-4be2-916f-935d2f0a5f08','410979f8-580d-4434-9883-ad3cf785333c','d60df459-ad1a-4299-b3bd-5b7da6f5f7ec']
if args.bulk_0603:ids+=['1ce012e4-f7db-493a-a4c4-30dec5ed03f7','9bafe2c0-f71e-4e19-9aca-a33c516b7728']
held=[]
for t in list(b.GetTracks()):
 if t.m_Uuid.AsString() not in ids:continue
 assert t.GetNetname()=='GND'
 if isinstance(t,p.PCB_VIA):assert t.GetWidth(p.F_Cu)==p.FromMM(.6) and t.GetDrillValue()==p.FromMM(.3)
 elif t.m_Uuid.AsString() in ids[8:]:assert t.GetWidth()==p.FromMM(.2) and t.GetLayer()==p.F_Cu
 else:assert t.GetWidth()==p.FromMM(.5) and t.GetLayer()==p.B_Cu
 b.Remove(t);held.append(t)
assert len(held)==len(ids)
reset_detour=None
if args.bulk_0603:
 uid='91783e84-7aa8-47f6-b77c-57ca34d2b8fb'
 t=next(t for t in b.GetTracks() if t.m_Uuid.AsString()==uid)
 assert t.GetNetname()=='PHY_RESET_N' and t.GetLayer()==p.F_Cu and t.GetWidth()==p.FromMM(.2)
 reset_detour=tuple(tuple(p.ToMM(v) for v in point) for point in [(t.GetStart().x,t.GetStart().y),(t.GetEnd().x,t.GetEnd().y)])
 b.Remove(t);held.append(t);ids.append(uid)
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
def tracks(path,width,layer):
 result=[]
 for a,z in zip(path,path[1:]):
  if vec(a)==vec(z):continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(t);result.append(t)
 return result
def escape(start,layer,width,diameter,drill,limit):
 r=LocalRouter(b,(54,22,66,35),width=width,grid=.05);tree=r.paths_from(r.blocked(layer,'GND'),r.cell(start),limit)
 forbidden=set()
 for lay in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= r.blocked(lay,'GND',diameter,True)
 def reserved(q):
  if not args.reserve_output or width!=.5:return False
  point=r.world(q);a=pads['L501','2'];z=pads['C511','1']
  start=(p.ToMM(a.GetPosition().x),p.ToMM(a.GetPosition().y));end=(p.ToMM(z.GetPosition().x),p.ToMM(z.GetPosition().y))
  path=[start,(end[0],start[1]+abs(end[0]-start[0])),end]
  for a,z in zip(path,path[1:]):
   dx,dy=z[0]-a[0],z[1]-a[1];den=dx*dx+dy*dy
   u=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/den)) if den else 0
   if math.dist(point,(a[0]+u*dx,a[1]+u*dy)) < .775+diameter/2+.2:return True
  return False
 choices=sorted((q for q in tree['distances'] if q not in forbidden and not reserved(q)),key=lambda q:(tree['distances'][q],q))
 if not choices:return None
 q=choices[0];path=[start]+r.path_from_tree(tree,q);segments=tracks(path,width,layer)
 guard=require_constant_width_branch(segments,net='GND',layer=layer,width_mm=width,start_mm=start,end_mm=r.world(q))
 v=p.PCB_VIA(b);v.SetPosition(vec(r.world(q)));v.SetWidth(p.FromMM(diameter));v.SetDrill(p.FromMM(drill));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(v)
 return {'path_mm':path,'via_mm':r.world(q),'via_diameter_mm':diameter,'via_drill_mm':drill,'guard':guard}
branch=escape((57.3,29.6),p.B_Cu,.5,.6,.3,4)
assert branch,'No full-width ground relocation'
caps={}
for ref in (['C511','C515'] if args.bulk_0603 else ['C511']):
 q=pads[ref,'2'];cap=escape((p.ToMM(q.GetPosition().x),p.ToMM(q.GetPosition().y)),p.F_Cu,.2,.45,.2,4 if args.bulk_0603 else 2)
 assert cap,'No capacitor ground escape: '+ref
 caps[ref]=cap
if args.bulk_0603:
 oldpads={(f.GetReference(),q.GetNumber()):q for f in old.GetFootprints() for q in f.Pads()}
 for num in ['1','2']:
  q=pads['R516',num];orig=oldpads['R516',num];r=LocalRouter(b,(63,23,68,27),width=.2,grid=.01)
  path=r.solve(r.blocked(p.F_Cu,q.GetNetname()),r.cell(r.xy(orig)),r.cell(r.xy(q)))
  assert path,'No R516 stub restoration'
  for a,z in zip(path,path[1:]):
   if vec(a)==vec(z):continue
   t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(.2));t.SetLayer(p.F_Cu);t.SetNetCode(q.GetNetCode());b.Add(t)
if reset_detour:
 r=LocalRouter(b,(63,23,69,28),width=.2,grid=.025)
 path=r.solve(r.blocked(p.F_Cu,'PHY_RESET_N'),r.cell(reset_detour[0]),r.cell(reset_detour[1]))
 assert path,'No reset detour'
 path=[reset_detour[0]]+path+[reset_detour[1]]
 reset_tracks=[]
 for a,z in zip(path,path[1:]):
  if vec(a)==vec(z):continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(.2));t.SetLayer(p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname('PHY_RESET_N'));b.Add(t);reset_tracks.append(t)
 require_constant_width_branch(reset_tracks,net='PHY_RESET_N',layer=p.F_Cu,width_mm=.2,start_mm=reset_detour[0],end_mm=reset_detour[1])
f=next(f for f in b.GetFootprints() if f.GetReference()=='L501');f.Reference().SetVisible(False)
outdir=Path(tempfile.mkdtemp(prefix='phoenix-compact-ground-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',outdir/'fp-lib-table')
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);b.BuildConnectivity()
drc=outdir/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
new=introduced(json.loads(root.with_name(root.stem+'-drc.json').read_text()),json.loads(drc.read_text()))
preservation=verify_preservation(old,b,replaced_copper=ids)
key=lambda r:(r['reservation'],r['ref']);mechanical=sorted({key(r) for r in screen(b)}-{key(r) for r in screen(old)})
result={'status':'COMPACT_GROUNDS_GEOMETRY_PASSED' if not new and not mechanical else 'COMPACT_GROUNDS_REJECTED','source_sha256':cp['sha256'],'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'temporary_candidate':str(out),'branch':branch,'capacitors':caps,'bulk_0603':args.bulk_0603,'reserved_output_corridor':args.reserve_output,'new_violations':new,'mechanical_conflicts':mechanical,'preservation':preservation,'checkpoint_modified':False,'assembly_ready':False,'limitations':['Alternative inductor requires electrical approval against current PHY layout guide; not selected BOM.','No main power or switching routing; DRC and continuity are not PI or current qualification.']}
assert hashlib.sha256(root.read_bytes()).hexdigest()==cp['sha256']
(D/'pcb'/('phy-compact-0603-ground-probe.json' if args.bulk_0603 else 'phy-compact-ground-probe.json')).write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
