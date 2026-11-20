"""Evaluate the rear bypass and inner output trunk together for a second PHY ground barrel."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from phy_corridor_path import geometry
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'phy-thermal-power-joint.json').read_text());src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();ep=b.FindFootprintByReference('U5').FindPadByNumber('41');anchor=b.FindFootprintByReference('C511').FindPadByNumber('2');center=ep.GetPosition();folder=root/'runs/phy-second-ground-barrel';folder.mkdir(exist_ok=True);out=folder/src.name
if '--isolate' in sys.argv:
 b=p.LoadBoard(str(out));uids=json.loads((folder/'vias.json').read_text());keep=sys.argv[-1]
 removed=[t for t in b.GetTracks() if t.m_Uuid.AsString() in uids and t.m_Uuid.AsString()!=keep]
 for t in removed:b.Remove(t)
 b.BuildConnectivity();actual=anchor.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('U5').FindPadByNumber('41'))}
 assert actual==(keep!='none');os._exit(0)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
tracks=[t for t in b.GetTracks() if t.GetBoundingBox().Inflate(7000000).Contains(center)]
pads=[q for f in b.GetFootprints() for q in f.Pads() if q.GetBoundingBox().Inflate(7000000).Contains(center) and q.m_Uuid.AsString()!=ep.m_Uuid.AsString()]
sources=['97d91e4a-c0a1-4463-a3dc-97a93da9606a','ff10aae3-e4e5-4337-a636-8f91c1fd64ad'];remaining=[k for k in tracks+pads if k.m_Uuid.AsString() not in sources]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
shapes={l:[k.GetEffectiveShape(l) for k in remaining if k.IsOnLayer(l) and k.GetNetCode()!=ep.GetNetCode()] for l in layers}
def via(site):
 v=p.PCB_VIA(b);v.SetWidth(550000);v.SetDrill(300000);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetViaType(p.VIATYPE_THROUGH);v.SetNetCode(ep.GetNetCode());v.SetFillingMode(p.FILLING_MODE_FILLED);v.SetCappingMode(p.CAPPING_MODE_CAPPED);v.SetPosition(p.VECTOR2I(*site));return v
options=[]
for uid in sources:
 orig=next(t for t in tracks if t.m_Uuid.AsString()==uid);l=orig.GetLayer();a,z=tuple(orig.GetStart()),tuple(orig.GetEnd());length=math.dist(a,z);u=((z[0]-a[0])/length,(z[1]-a[1])/length);normal=(-u[1],u[0])
 assert orig.GetNetname()=='+1V0_PHY' and orig.GetWidth()==1550000
 obs=[k.GetEffectiveShape(l) for k in remaining if k.IsOnLayer(l) and k.GetNetCode()!=orig.GetNetCode()]
 variants=[(0,[(a,z)],[orig.GetEffectiveShape(l)])]
 for step in range(1,26):
  d=step*50000
  for sign in (-1,1):
   for front,rear in ((0,0),(400000,0),(0,400000),(500000,500000),(800000,400000),(400000,800000),(800000,800000),(1200000,300000),(300000,1200000)):
    if front+rear+2*d>=length:continue
    first=tuple(round(a[i]+front*u[i]) for i in range(2));last=tuple(round(z[i]-rear*u[i]) for i in range(2))
    path=[a,first,tuple(round(first[i]+d*(u[i]+sign*normal[i])) for i in range(2)),tuple(round(last[i]+d*(-u[i]+sign*normal[i])) for i in range(2)),last,z]
    path=[v for j,v in enumerate(path) if j==0 or v!=path[j-1]]
    segs=list(zip(path,path[1:]));ss=[]
    for start,end in segs:
     t=p.PCB_TRACK(b);t.SetLayer(l);t.SetStart(p.VECTOR2I(*start));t.SetEnd(p.VECTOR2I(*end));t.SetWidth(1550000);s=t.GetEffectiveShape(l)
     if any(s.Collide(k,200000) for k in obs):break
     ss.append(s)
    if len(ss)==len(segs):variants.append((sum(math.dist(*seg) for seg in segs)-length,segs,ss))
 options.append((orig,sorted(variants,key=lambda row:row[0])))
feasible=[]
for dx in range(-14,15):
 for dy in range(-14,15):
  site=tuple(center+p.VECTOR2I(dx*100000,dy*100000));v=via(site)
  if any(q.GetBoundingBox().Inflate(326000).Contains(v.GetPosition()) for q in pads):continue
  if any(isinstance(t,p.PCB_VIA) and math.dist(tuple(t.GetPosition()),site)<950000 for t in tracks):continue
  if any(v.GetEffectiveShape(l).Collide(s,200000) for l in layers for s in shapes[l]):continue
  choices=[]
  for orig,variants in options:
   for delta,segs,ss in variants:
    if all(not v.GetEffectiveShape(orig.GetLayer()).Collide(s,200000) for s in ss):
     choices.append((delta,segs));break
  if len(choices)==2:feasible.append((sum(c[0] for c in choices),site,choices))
if '--maze' in sys.argv and not feasible:
 candidates=[]
 for dx in range(-14,15,2):
  for dy in range(-14,15,2):
   site=tuple(center+p.VECTOR2I(dx*100000,dy*100000));v=via(site)
   if any(q.GetBoundingBox().Inflate(326000).Contains(v.GetPosition()) for q in pads) or any(isinstance(t,p.PCB_VIA) and math.dist(tuple(t.GetPosition()),site)<950000 for t in tracks):continue
   if any(v.GetEffectiveShape(l).Collide(s,200000) for l in layers for s in shapes[l]):continue
   # Maximize separation from the existing EP ground connection.
   candidates.append((math.dist(site,tuple(cp['change']['sites_nm'][0])),site))
 attempts=[]
 for _,site in sorted(candidates,reverse=True):
  if any(math.dist(site,prior)<400000 for prior in attempts):continue
  attempts.append(site);v=via(site);choices=[]
  for orig,variants in options:
   l=orig.GetLayer();old_shape=orig.GetEffectiveShape(l);old_length=orig.GetLength()
   if not v.GetEffectiveShape(l).Collide(old_shape,200000):
    choices.append((0,[(tuple(orig.GetStart()),tuple(orig.GetEnd()))]));continue
   geo=list(geometry(b,l,orig.GetNetCode(),oval_caps=True));geo[0].append([site,site,550000])
   polygons=[]
   for zone in b.Zones():
    if zone.GetIsRuleArea() and zone.IsOnLayer(l) and zone.GetDoNotAllowTracks():
     contour=zone.Outline().Outline(0);polygons.append([tuple(contour.CPoint(i)) for i in range(contour.PointCount())])
   geo.append(polygons)
   request=dict(geometry=geo,width=1550000,ends=[tuple(orig.GetStart()),tuple(orig.GetEnd())])
   path=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('reset_link_grid.py'))],input=json.dumps(request),capture_output=True,check=True,text=True).stdout)
   if not path:break
   segs=list(zip(path,path[1:]));extra=sum(math.dist(a,z) for a,z in segs)-old_length
   if extra>1200000:break
   choices.append((extra,segs))
  if len(choices)==2:feasible.append((sum(x[0] for x in choices),site,choices))
record=None
for _,site,choices in sorted(feasible)[:12]:
 candidate=p.LoadBoard(str(src));byid={t.m_Uuid.AsString():t for t in candidate.GetTracks()};changed=[]
 for uid,(delta,segs) in zip(sources,choices):
  if delta<=0:continue
  orig=byid[uid];layer=orig.GetLayer();net=orig.GetNetCode();candidate.Remove(orig);changed.append(uid)
  for a,z in segs:
   t=p.PCB_TRACK(candidate);t.SetLayer(layer);t.SetNetCode(net);t.SetWidth(1550000);t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));candidate.Add(t)
 v=via(site);candidate.Add(v);p.ZONE_FILLER(candidate).Fill(candidate.Zones());p.SaveBoard(str(out),candidate)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
 if delta:continue
 saved=p.LoadBoard(str(out));pres=verify_preservation(b,saved,replaced_copper=changed);assert not screen(saved)
 uids=cp['change']['via_ids']+[v.m_Uuid.AsString()];(folder/'vias.json').write_text(json.dumps(uids)+'\n')
 for keep in ['none',*uids]:subprocess.run([sys.executable,__file__,'--isolate',keep],check=True,capture_output=True)
 record=dict(via_ids=uids,site_nm=site,extra_length_mm=[d/1e6 for d,_ in choices],preservation=pres);break
if not record:out=src
(root/'phy-second-ground.json').write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],clear_sites=len(feasible),change=record,thermal_qualified=False,assembly_ready=False),indent=2)+'\n');print(len(feasible),bool(record),flush=True);os._exit(0)
