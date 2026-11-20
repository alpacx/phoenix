"""Move the neighbouring ground return away from the C516 full-width feed."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'phy-second-ground.json').read_text());src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));base=p.LoadBoard(str(src));byid={t.m_Uuid.AsString():t for t in b.GetTracks()}
t=byid['1e522730-8934-4866-bd3a-1cebe35cef28'];v=byid['af45c499-2547-44ca-b089-a3bca2209eae']
assert v.GetPosition()==t.GetEnd() and t.GetNetname()==v.GetNetname()=='GND'
length=t.GetLength();start=t.GetStart();old=tuple(v.GetPosition());keep=[t.m_Uuid.AsString(),v.m_Uuid.AsString()]
near=lambda o:o.GetBoundingBox().Inflate(3500000).Contains(start)
pads=[q for f in b.GetFootprints() for q in f.Pads() if near(q)]
tracks=[k for k in b.GetTracks() if near(k) and k.m_Uuid.AsString() not in keep]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
obs={l:[k.GetEffectiveShape(l) for k in pads+tracks if k.IsOnLayer(l) and k.GetNetCode()!=v.GetNetCode()] for l in layers}
opts=[]
for dx in range(-15,16):
 for dy in range(0,16):
  site=start+p.VECTOR2I(dx*50000,dy*50000);t.SetEnd(site);v.SetPosition(site)
  if t.GetLength()>length or any(q.GetBoundingBox().Inflate(v.GetWidth(p.F_Cu)//2+51000).Contains(site) for q in pads):continue
  if any(isinstance(k,p.PCB_VIA) and math.dist(tuple(site),tuple(k.GetPosition()))<750000 for k in tracks):continue
  if any(t.GetEffectiveShape(p.F_Cu).Collide(s,200000) for s in obs[p.F_Cu]):continue
  if any(v.GetEffectiveShape(l).Collide(s,200000) for l in layers for s in obs[l]):continue
  opts.append((-math.dist(tuple(site),(66400000,33600000)),t.GetLength(),tuple(site)))
folder=root/'runs/phy-ground-clearance';folder.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
record=None
for _,_,site in sorted(opts)[:12]:
 v.SetPosition(p.VECTOR2I(*site));t.SetEnd(v.GetPosition());out=folder/src.name
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
 if delta:continue
 saved=p.LoadBoard(str(out));pres=verify_preservation(base,saved,replaced_copper=keep);assert not screen(saved)
 record=dict(old_nm=old,site_nm=site,length_before_mm=length/1e6,length_after_mm=t.GetLength()/1e6,preservation=pres);break
if not record:out=src
(root/'phy-ground-clearance.json').write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],candidates=len(opts),change=record,assembly_ready=False),indent=2)+'\n');print(len(opts),record and record['site_nm'],flush=True);os._exit(0)
