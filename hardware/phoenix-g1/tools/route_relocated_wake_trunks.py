"""Restore the wake-clock supply and buffered output to their original physical pad groups."""
import hashlib,json,math,os,shutil,subprocess,sys
model_long='--model-long-clock' in sys.argv
reclaimed='--reclaimed-termination' in sys.argv
extended='--clock-boardwide' in sys.argv or reclaimed or model_long
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
from drc_regression import introduced
from pcb_power_leg import make,barrel
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text())
cp=read('wake-repurposed-termination' if reclaimed else 'wake-clock-trunk-recovery' if extended else 'wake-clock-local-recovery');src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];prior=src
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu];stack=[p.F_Cu,p.In2_Cu,p.In3_Cu,p.B_Cu];uid=lambda o:o.m_Uuid.AsString()
def get(b,r):
 ref,n=r.split('.');return b.FindFootprintByReference(ref).FindPadByNumber(n)
def points(objects,l):
 pts=set()
 for o in objects:
  if not o.IsOnLayer(l):continue
  if isinstance(o,p.PAD):
   center=o.GetPosition();pts.add(tuple(center));bb=o.GetBoundingBox()
   for ix in (.15,.35,.65,.85):
    for iy in (.15,.35,.65,.85):
     pos=p.VECTOR2I(round(bb.GetLeft()+ix*bb.GetWidth()),round(bb.GetTop()+iy*bb.GetHeight()))
     if o.HitTest(pos):pts.add(tuple(pos))
  else:
   a,z=tuple(o.GetStart()),tuple(o.GetEnd());n=max(1,math.ceil(math.dist(a,z)/400000))
   pts.update(tuple(round(x+(y-x)*i/n) for x,y in zip(a,z)) for i in range(n+1))
 return sorted(pts)
records=[]
for a,z,w,limit in [('R2003.2','U25.24',200000,36000000),('C2007.1','C470.1',300000,27000000)]:
 if extended and not a.startswith('R'):continue
 b=p.LoadBoard(str(prior));b.BuildConnectivity()
 qa=get(b,a);net=qa.GetNetname();qz=next(q for q in b.FindFootprintByReference('U25').Pads() if q.GetNetname()==net) if a.startswith('R') else get(b,z);z=qz.GetParentFootprint().GetReference()+'.'+qz.GetNumber();code=qa.GetNetCode();assert qz.GetNetCode()==code
 ids={uid(o) for o in b.GetConnectivity().GetConnectedItems(qz)}
 candidates=[o for o in b.GetTracks() if uid(o) in ids and (a.startswith('R') or not isinstance(o,p.PCB_VIA) and o.GetWidth()>=500000)]
 candidates.append(qz);geos={}
 for l in layers:
  tracks,boxes=geometry(b,l,code,oval_caps=True);zones=[]
  for zone in b.Zones():
   if zone.GetIsRuleArea() and zone.IsOnLayer(l) and (zone.GetDoNotAllowTracks() or zone.GetDoNotAllowVias()):
    for i in range(zone.Outline().OutlineCount()):
     poly=zone.Outline().Outline(i);zones.append([tuple(poly.CPoint(j)) for j in range(poly.PointCount())])
  geos[l]=[tracks,boxes,zones]
 holes=[[tuple(t.GetPosition()),tuple(t.GetPosition()),t.GetDrillValue()+400000] for t in b.GetTracks() if isinstance(t,p.PCB_VIA)]
 boxes=[q.GetBoundingBox() for f in b.GetFootprints() for q in f.Pads()]
 req=dict(layers=[geos[l] for l in stack],through=list(geos.values()),via_keepouts=[holes,[(v.GetLeft(),v.GetTop(),v.GetRight(),v.GetBottom()) for v in boxes]],bounds=[34000000,500000,70000000,28500000],grid_nm=100000,width_nm=w,via_nm=450000,start=[points([qa],l) for l in stack],end=[points(candidates,l) for l in stack],explain=True)
 if extended:
  req['bounds']=[500000,500000,89500000,39500000];req['start'],req['end']=req['end'],req['start'];req['export_frontier']=True
 solver=subprocess.run(['python3',str(Path(__file__).with_name('control_board_grid.py'))],input=json.dumps(req),capture_output=True,text=True,check=True);result=json.loads(solver.stdout)
 if not result.get('path'):
  if extended and 'frontier_nm' in result:(root/'runs/wake-lpo-target-frontier.json').write_text(json.dumps(result.pop('frontier_nm'))+'\n')
  records.append(dict(a=a,z=z,screen=result));continue
 path=result['path'];length=sum(math.dist(s[1:],t[1:]) for s,t in zip(path,path[1:]))
 if length>limit and not model_long:records.append(dict(a=a,z=z,length_mm=length/1e6,reason='excess route length'));continue
 for (l,x,y),(k,u,v) in zip(path,path[1:]):
  if l==k:b.Add(make(b,(x,y),(u,v),w,code,stack[l]))
  else:b.Add(barrel(b,(x,y),code))
 folder=root/'runs'/(('model-long-wake-trunk-' if model_long else 'reclaimed-wake-trunk-' if reclaimed else 'relocated-wake-trunk-')+a);folder.mkdir(exist_ok=True);out=folder/src.name
 for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);dr=folder/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],capture_output=True,check=True)
 delta=introduced(json.loads((prior.parent/'drc.json').read_text()),json.loads(dr.read_text()));saved=p.LoadBoard(str(out));saved.BuildConnectivity();joined=uid(get(saved,z)) in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(get(saved,a))}
 records.append(dict(a=a,z=z,length_mm=length/1e6,new_drc=delta,joined_on_disk=joined))
 if not delta and joined and not screen(saved):prior=out
(root/('wake-clock-long-cad-model.json' if model_long else 'wake-clock-lpo-reclaimed.json' if reclaimed else 'wake-clock-lpo-boardwide.json' if extended else 'wake-clock-trunk-recovery.json')).write_text(json.dumps(dict(parent_sha256=cp['sha256'],board=str(prior.relative_to(root)),sha256=hashlib.sha256(prior.read_bytes()).hexdigest(),records=records,assembly_ready=False),indent=2)+'\n');print(records,flush=True);os._exit(0)
