"""Evaluate explicitly filled and copper-capped through vias inside the PHY exposed pad."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess,sys
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'phy-ep-ground.json').read_text());src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
def endpoint(b,r,n):return b.FindFootprintByReference(r).FindPadByNumber(n)
def grounded(b):
 b.BuildConnectivity();return endpoint(b,'C511','2').m_Uuid.AsString() in {k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(endpoint(b,'U5','41'))}
b=p.LoadBoard(str(src));assert not grounded(b);ep=endpoint(b,'U5','41');center=ep.GetPosition()
joint='--power-detour' in sys.argv
folder=root/('runs/phy-thermal-power-joint' if joint else 'runs/phy-thermal-array');folder.mkdir(exist_ok=True);out=folder/src.name
if '--isolate' in sys.argv:
 data=json.loads((folder/'vias.json').read_text());keep=sys.argv[-1];board=p.LoadBoard(str(out))
 discard=[v for v in board.GetTracks() if v.m_Uuid.AsString() in data and v.m_Uuid.AsString()!=keep]
 for v in discard:board.Remove(v)
 assert grounded(board)==(keep!='none');os._exit(0)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
near=lambda o:o.GetBoundingBox().Inflate(3200000).Contains(center)
pads=[q for f in b.GetFootprints() for q in f.Pads() if near(q) and q.m_Uuid.AsString()!=ep.m_Uuid.AsString()]
tracks=[t for t in b.GetTracks() if near(t)]
shapes={l:[k.GetEffectiveShape(l) for k in pads+tracks if k.IsOnLayer(l) and k.GetNetCode()!=ep.GetNetCode()] for l in layers}
def make(site):
 v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetPosition(p.VECTOR2I(*site));v.SetWidth(550000);v.SetDrill(300000);v.SetNetCode(ep.GetNetCode())
 v.SetFillingMode(p.FILLING_MODE_FILLED);v.SetCappingMode(p.CAPPING_MODE_CAPPED);return v
replaced=[];new_parts=[]
if joint:
 blocker=next(t for t in b.GetTracks() if t.m_Uuid.AsString()=='0f7df32b-0214-461f-9fa1-e928cddb7a53')
 assert blocker.GetNetname()=='+1V0_PHY' and blocker.GetWidth()==1550000 and blocker.GetLayer()==p.In3_Cu
 a,z=tuple(blocker.GetStart()),tuple(blocker.GetEnd())
 forbidden=[k.GetEffectiveShape(p.In3_Cu) for k in tracks+pads if k.IsOnLayer(p.In3_Cu) and k.GetNetCode()!=blocker.GetNetCode()]
 best=None
 for dx in range(100000,1250001,50000):
  path=[a,(a[0]+dx,a[1]+dx),(z[0]+dx,z[1]-dx),z];parts=[]
  for u,w in zip(path,path[1:]):
   t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(*u));t.SetEnd(p.VECTOR2I(*w));t.SetLayer(p.In3_Cu);t.SetNetCode(blocker.GetNetCode());t.SetWidth(1550000)
   if any(t.GetEffectiveShape(p.In3_Cu).Collide(s,200000) for s in forbidden):break
   parts.append(t)
  if len(parts)!=3:continue
  # Prefer the shortest displacement that opens two independent barrels.
  clear_sites=[]
  for i in range(6,15):
   for j in range(-10,11):
    site=tuple(center+p.VECTOR2I(i*100000,j*100000));v=make(site)
    if any(q.GetBoundingBox().Inflate(326000).Contains(v.GetPosition()) for q in pads):continue
    if any(isinstance(t,p.PCB_VIA) and math.dist(tuple(t.GetPosition()),site)<850000 for t in tracks):continue
    if any(v.GetEffectiveShape(l).Collide(k.GetEffectiveShape(l),200000) for l in layers for k in pads+tracks+parts if k.m_Uuid.AsString()!=blocker.m_Uuid.AsString() and k.GetNetCode()!=ep.GetNetCode() and k.IsOnLayer(l)):continue
    clear_sites.append(site)
  if not clear_sites:continue
  span=max(math.dist(site,w) for site in clear_sites for w in clear_sites)
  best=(parts,span)
  if span>=1000000:break
 if best:
  new_parts=best[0];replaced=[blocker.m_Uuid.AsString()];b.Remove(blocker)
  for t in new_parts:b.Add(t)
  tracks=[k for k in tracks if k.m_Uuid.AsString() not in replaced]+new_parts
  shapes={l:[k.GetEffectiveShape(l) for k in pads+tracks if k.IsOnLayer(l) and k.GetNetCode()!=ep.GetNetCode()] for l in layers}
sites=[]
for dx in range(-14,15):
 for dy in range(-14,15):
  site=tuple(center+p.VECTOR2I(dx*100000,dy*100000));v=make(site)
  if any(q.GetBoundingBox().Inflate(326000).Contains(v.GetPosition()) for q in pads):continue
  if any(isinstance(t,p.PCB_VIA) and math.dist(tuple(t.GetPosition()),site)<850000 for t in tracks):continue
  if all(not v.GetEffectiveShape(l).Collide(s,200000) for l in layers for s in shapes[l]):sites.append(site)
selected=[];record=None
# Prefer one site per quadrant, then a central via if the inner copper allows it.
for dx,dy in [(-8,-8),(8,8),(-8,8),(8,-8),(0,0)]:
 target=tuple(center+p.VECTOR2I(dx*100000,dy*100000))
 for site in sorted(sites,key=lambda z:math.dist(z,target)):
  if math.dist(site,target)>700000 or any(math.dist(site,z)<900000 for z in selected):continue
  selected.append(site);break
if joint and sites:
 farthest=max(((math.dist(a,z),a,z) for a in sites for z in sites));selected=[farthest[1]]+([farthest[2]] if farthest[0]>=900000 else [])
if selected:
 vias=[make(site) for site in selected]
 for v in vias:b.Add(v)
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
 if not delta:
  saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=replaced);assert grounded(saved) and not screen(saved)
  ids={v.m_Uuid.AsString() for v in vias}
  verified=[v for v in saved.GetTracks() if v.m_Uuid.AsString() in ids];assert len(verified)==len(vias)
  assert all(v.GetFillingMode()==p.FILLING_MODE_FILLED and v.GetCappingMode()==p.CAPPING_MODE_CAPPED for v in verified)
  (folder/'vias.json').write_text(json.dumps(sorted(ids))+'\n')
  for keep in ['none',*sorted(ids)]:subprocess.run([sys.executable,__file__,*(['--power-detour'] if joint else []),'--isolate',keep],capture_output=True,check=True)
  record=dict(detour_mm=sum(t.GetLength()/1e6 for t in new_parts),via_ids=sorted(ids),sites_nm=selected,annulus_outer_mm=.55,drill_mm=.30,each_via_tested_alone=True,all_removed_test=True,preservation=pres)
if not record:out=src
(root/('phy-thermal-power-joint.json' if joint else 'phy-thermal-array.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],clear_sites=len(sites),change=record,process='Epoxy filled and copper capped, planarized; verify fabrication files and stencil before assembly.',source='https://jlcpcb.com/help/article/pcb-via-covering',thermal_qualified=False,assembly_ready=False),indent=2)+'\n')
print(len(sites),selected,bool(record),flush=True);os._exit(0)
