"""Find an off-pad thermal/ground escape for PHY EP41 through a package corner."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'phy-switch-entry.json').read_text());src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();ep=b.FindFootprintByReference('U5').FindPadByNumber('41');ground=b.FindFootprintByReference('C511').FindPadByNumber('2')
ids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(ground)};assert ep.m_Uuid.AsString() not in ids
net=ep.GetNetCode();box=ep.GetBoundingBox()
pads=[q for f in b.GetFootprints() for q in f.Pads() if q.GetBoundingBox().Inflate(6000000).Contains(ep.GetPosition())]
tracks=[t for t in b.GetTracks() if t.GetBoundingBox().Inflate(6000000).Contains(ep.GetPosition())]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
shapes={l:[k.GetEffectiveShape(l) for k in pads+tracks if k.IsOnLayer(l) and k.GetNetCode()!=net] for l in layers}
def clear(t,l):return all(not t.GetEffectiveShape(l).Collide(s,200000) for s in shapes[l])
def via(z):
 v=p.PCB_VIA(b);v.SetPosition(z);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetViaType(p.VIATYPE_THROUGH);v.SetWidth(600000);v.SetDrill(300000);v.SetNetCode(net);return v
def track(a,z):
 t=p.PCB_TRACK(b);t.SetStart(a);t.SetEnd(z);t.SetNetCode(net);t.SetWidth(500000);t.SetLayer(p.F_Cu);return t
options=[];tested=0
known=[tuple(t.GetPosition()) for t in tracks if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in ids]
for sx in (-1,1):
 for sy in (-1,1):
  corner=p.VECTOR2I(box.GetLeft() if sx<0 else box.GetRight(),box.GetTop() if sy<0 else box.GetBottom())
  starts=[corner+p.VECTOR2I(-sx*x,-sy*y) for x in range(10000,410000,50000) for y in range(10000,410000,50000)]
  sites=set(known)|{tuple(corner+p.VECTOR2I(sx*x*100000,sy*y*100000)) for x in range(-3,19) for y in range(-3,19)}
  for site in sites:
   z=p.VECTOR2I(*site);v=via(z)
   if math.dist(site,tuple(corner))>2200000:continue
   if site not in known:
    if any(q.GetBoundingBox().Inflate(351000).Contains(z) for q in pads):continue
    if any(isinstance(k,p.PCB_VIA) and math.dist(tuple(k.GetPosition()),site)<810000 for k in tracks):continue
    if not all(clear(v,l) for l in layers):continue
   tested+=1
   for a in sorted(starts,key=lambda v:math.dist(tuple(v),site)):
    if not ep.HitTest(a):continue
    t=track(a,z)
    if clear(t,p.F_Cu):
     options.append((t.GetLength(),site not in known,tuple(a),site));break
folder=root/'runs/phy-ep-ground';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
record=None
for length,new,a,z in sorted(options)[:10]:
 items=[track(p.VECTOR2I(*a),p.VECTOR2I(*z))]+([via(p.VECTOR2I(*z))] if new else [])
 for t in items:b.Add(t)
 out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
 if not delta:
  saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved);assert not screen(saved)
  q=saved.FindFootprintByReference('U5').FindPadByNumber('41');assert ground.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(q)}
  record=dict(site_nm=z,run_mm=length/1e6,preservation=pres);break
 for t in items:b.Remove(t)
if not record:out=src
(root/'phy-ep-ground.json').write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],candidate_sites=tested,clear_routes=len(options),change=record,thermal_qualified=False),indent=2)+'\n')
print(tested,len(options),bool(record),flush=True);os._exit(0)
