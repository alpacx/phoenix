"""Extend the 1.05 mm PHY trunk to a local bypass using two off-pad power vias."""
from pathlib import Path
import sys
import hashlib,json,math,os,shutil,subprocess
import pcbnew as p
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
front='--enter-pad' in sys.argv
pair_feed='--terminal-pair' in sys.argv
bracket='--bracket' in sys.argv
all_sources='--all-sources' in sys.argv or bracket or pair_feed
fine='--fine-reverse' in sys.argv or all_sources
shift='--shift-ground' in sys.argv or fine
relocated='--after-pin11' in sys.argv or front or pair_feed
cp=json.loads((root/('layout-opposite-bypass.json' if pair_feed else 'phy-bracket-trial.json' if bracket else 'layout-ground-bends.json' if all_sources else 'phy-ground-clearance.json' if shift else 'phy-pin11-bypass.json' if relocated else 'phy-pin40-bypass.json')).read_text());src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();multi='multi' in sys.argv
layer={'multi':p.In2_Cu,'rear':p.B_Cu,'in3':p.In3_Cu,'in2':p.In2_Cu}[sys.argv[1] if len(sys.argv)>1 else 'in2'];width=1050000
def pad(b,ref,num):return b.FindFootprintByReference(ref).FindPadByNumber(num)
q=pad(b,'C516','1');net=q.GetNetCode();pos=q.GetPosition()
def trace(a,z,l):
 t=p.PCB_TRACK(b);t.SetLayer(l);t.SetWidth(width);t.SetNetCode(net);t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));return t
def via(z):
 v=p.PCB_VIA(b);v.SetWidth(600000);v.SetDrill(300000);v.SetPosition(p.VECTOR2I(*z));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(net);return v
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
near=lambda k:k.GetBoundingBox().Inflate(5500000).Contains(pos)
pads=[q for f in b.GetFootprints() for q in f.Pads() if near(q)];tracks=[t for t in b.GetTracks() if near(t)]
shapes={l:[o.GetEffectiveShape(l) for o in pads+tracks if o.GetNetCode()!=net and o.IsOnLayer(l)] for l in layers}
def clear(t,l):return all(not t.GetEffectiveShape(l).Collide(s,200000) for s in shapes[l])
launch_offsets=[(0,0),(0,150000),(0,220000),(-100000,180000),(100000,180000)]
if relocated:launch_offsets=[(x,y) for x in (0,150000,-150000,220000,-220000) for y in (0,150000,-150000,220000,-220000)]
launches={}
all_sites=[]
for dx in range(-36,37):
 for dy in range(-36,37):
  site=tuple(pos+p.VECTOR2I(dx*100000,dy*100000))
  if math.hypot(dx,dy)>36:continue
  v=via(site)
  if pair_feed and any(zone.GetIsRuleArea() and zone.GetDoNotAllowVias() and zone.Outline().Collide(v.GetEffectiveShape(p.F_Cu),0) for zone in b.Zones()):continue
  if any(q.GetBoundingBox().Inflate(351000).Contains(v.GetPosition()) for q in pads):continue
  if any(isinstance(t,p.PCB_VIA) and math.dist(tuple(t.GetPosition()),site)<810000 for t in tracks):continue
  if not all(clear(v,l) for l in layers):continue
  for ox,oy in launch_offsets:
   start=pos+p.VECTOR2I(ox,oy)
   if q.HitTest(start) and clear(trace(tuple(start),site,p.F_Cu),p.F_Cu):
    launches[site]=tuple(start);all_sites.append(site);break
pairs={}
for i,a in enumerate(all_sites):
 for z in all_sites[i+1:]:
  distance=math.dist(a,z)
  if not 800000<=distance<=1100000:continue
  if not all(clear(trace(a,z,l),l) for l in (layer,p.F_Cu)):continue
  for first,second in ((a,z),(z,a)):
   cost=math.dist(tuple(pos),first)+distance
   if first not in pairs or cost<pairs[first][0]:pairs[first]=(cost,second)
ids={t.m_Uuid.AsString() for t in b.GetConnectivity().GetConnectedItems(pad(b,'C515','1'))}
seeds=[]
for t in b.GetTracks():
 if t.m_Uuid.AsString() in ids and t.IsOnLayer(layer) and not isinstance(t,p.PCB_VIA) and t.GetWidth()>=width:
  a,z=tuple(t.GetStart()),tuple(t.GetEnd());count=max(1,math.ceil(t.GetLength()/250000))
  seeds.extend(tuple(round(u+(v-u)*j/count) for u,v in zip(a,z)) for j in range(count+1))
source_pair=[(62015000,24600000),(62575000,24600000)]
if layer!=p.In2_Cu:
 seeds=source_pair if clear(trace(*source_pair,layer),layer) else []
geo=list(geometry(b,layer,net,oval_caps=True));polys=[]
for zone in b.Zones():
 if zone.GetIsRuleArea() and zone.IsOnLayer(layer) and zone.GetDoNotAllowTracks():
  o=zone.Outline().Outline(0);polys.append([tuple(o.CPoint(i)) for i in range(o.PointCount())])
geo.append(polys);folder=root/('runs/phy-c516-wide-'+('terminal-pair' if pair_feed else 'bracket' if bracket else 'all-sources' if all_sources else 'fine-ground-entry' if fine else 'ground-pad-entry' if shift else 'pad-entry' if front else 'relocated' if relocated else 'multi' if multi else b.GetLayerName(layer)));folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
rec=None
if pairs and seeds:
 request=dict(grid_nm=100000,bounds=[500000,500000,89500000,39500000],width_nm=width,layers=[geo],through=[],via_keepouts=[[],[]],start=[seeds],end=[list(pairs)])
 if multi:
  stack=[p.In2_Cu,p.In3_Cu,p.B_Cu,p.F_Cu]
  geometries={l:[*geometry(b,l,net,oval_caps=True),polys] for l in layers}
  # Mechanical mounting reservations on this board prohibit vias throughout the stack.
  boxes=[q.GetBoundingBox() for f in b.GetFootprints() for q in f.Pads()]
  holes=[[tuple(t.GetPosition()),tuple(t.GetPosition()),t.GetDrillValue()+400000] for t in b.GetTracks() if isinstance(t,p.PCB_VIA)]
  ends=[]
  landing={}
  for k,l in enumerate(stack):
   for i,a in enumerate(all_sites):
    for z in all_sites[i+1:]:
     if not 800000<=math.dist(a,z)<=1100000 or not clear(trace(a,z,l),l) or not clear(trace(a,z,p.F_Cu),p.F_Cu):continue
     landing.setdefault((k,a),z);landing.setdefault((k,z),a)
   ends.append([a for idx,a in landing if idx==k])
  if front:
   ends=[[],[],[],[tuple(pos+p.VECTOR2I(dx,dy)) for dx in range(-250000,250001,50000) for dy in range(-250000,250001,50000) if q.HitTest(pos+p.VECTOR2I(dx,dy))]]
  starts=[seeds]+[source_pair if clear(trace(*source_pair,l),l) else [] for l in stack[1:]]
  if all_sources:
   starts=[]
   for l in stack:
    contacts=set()
    for track in b.GetTracks():
     if track.m_Uuid.AsString() not in ids or isinstance(track,p.PCB_VIA) or track.GetLayer()!=l or track.GetWidth()<width:continue
     start,end=tuple(track.GetStart()),tuple(track.GetEnd())
     steps=max(1,math.ceil(track.GetLength()/100000))
     for i in range(steps+1):contacts.add(tuple(round(x+(y-x)*i/steps) for x,y in zip(start,end)))
    starts.append(sorted(contacts))
  request.update(grid_nm=200000,paired_vias=True,via_nm=600000,layers=[geometries[l] for l in stack],through=list(geometries.values()),via_keepouts=[holes,[(v.GetLeft(),v.GetTop(),v.GetRight(),v.GetBottom()) for v in boxes]],start=starts,end=ends)
 if fine:
  assert multi and (front or pair_feed)
  request.update(grid_nm=100000,start=ends,end=starts)
 sol=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('control_board_grid.py'))],input=json.dumps(request),text=True,capture_output=True,check=True).stdout)
 if sol and fine:
  sol["path"].reverse()
  sol["bridges"].reverse()
 if sol:
  path=[tuple(v[1:]) for v in sol['path']];a=path[-1];z=a if front else landing[(sol['path'][-1][0],a)] if multi else pairs[a][1]
  items=[trace(*source_pair,layer)] if layer!=p.In2_Cu else []
  items += [trace(s,e,layer) for s,e in zip(path,path[1:])]+[trace(a,z,layer),trace(launches.get(a,a),a,p.F_Cu),trace(a,z,p.F_Cu),via(a),via(z)]
  if multi:
   entry=stack[sol['path'][0][0]];exit_layer=stack[sol['path'][-1][0]]
   items=[trace(launches.get(a,a),a,p.F_Cu),trace(a,z,p.F_Cu),via(a),via(z)]
   if front:items=[]
   if exit_layer!=p.F_Cu:items.append(trace(a,z,exit_layer))
   if not all_sources and entry not in (p.F_Cu,p.In2_Cu):items.append(trace(*source_pair,entry))
   bridges=iter(sol['bridges'])
   for (l,x,y),(k,u,v) in zip(sol['path'],sol['path'][1:]):
    if k==l:items.append(trace((x,y),(u,v),stack[l]))
    else:
     meet=next(bridges);items.extend([via((x,y)),via(meet),trace((x,y),meet,stack[l]),trace((x,y),meet,stack[k])])
  for t in items:b.Add(t)
  out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
  subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
  delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
  if not delta:
   saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved);assert not screen(saved)
   ids={k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(pad(saved,'C515','1'))}
   assert pad(saved,'U5','11').m_Uuid.AsString() in ids
   rec=dict(via_nm=[tuple(t.GetPosition()) for t in items if isinstance(t,p.PCB_VIA)],layered_path=sol['path'],via_ids=[t.m_Uuid.AsString() for t in items if isinstance(t,p.PCB_VIA)],path_nm=path,preservation=pres)
if not rec:out=src
(root/('phy-c516-wide-'+('terminal-pair' if pair_feed else 'bracket' if bracket else 'all-sources' if all_sources else 'fine-ground-entry' if fine else 'ground-pad-entry' if shift else 'pad-entry' if front else 'relocated' if relocated else 'multi' if multi else b.GetLayerName(layer))+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],source_sites=len(seeds),clear_sites=len(all_sites),paired_destinations=len(pairs),change=rec,assembly_ready=False),indent=2)+'\n')
print(len(all_sites),len(pairs),bool(rec),flush=True);os._exit(0)
