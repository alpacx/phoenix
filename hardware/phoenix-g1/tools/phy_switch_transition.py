"""Minimize the exposed switch-pin neck by moving only the head of the full-width trunk."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'phy-pin11-bypass.json').read_text());src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
base=p.LoadBoard(str(src));b=p.LoadBoard(str(src));code=b.GetNetcodeFromNetname('PHY_SW')
copper=[t for t in b.GetTracks() if t.GetNetCode()==code];assert len(copper)==3
neck=next(t for t in copper if t.GetWidth()==200000)
head=next(t for t in copper if tuple(t.GetStart())==(60100000,27700000))
start=tuple(neck.GetStart());tip=tuple(neck.GetEnd());fixed=tuple(head.GetEnd());old=tuple(head.GetStart())
length=math.dist(start,tip);unit=[(z-a)/length for a,z in zip(start,tip)]
def point(d):return tuple(round(a+d*u) for a,u in zip(start,unit))
def distance(q,a,z):
 dx,dy=z[0]-a[0],z[1]-a[1];t=max(0,min(1,((q[0]-a[0])*dx+(q[1]-a[1])*dy)/(dx*dx+dy*dy)))
 return math.hypot(q[0]-a[0]-t*dx,q[1]-a[1]-t*dy)
def entry(a):
 lo,hi=0,length
 if distance(tip,a,fixed)>775000:return None
 for _ in range(23):
  mid=(lo+hi)/2
  if distance(point(mid),a,fixed)>775000:lo=mid
  else:hi=mid
 return hi
original=entry(old);assert original is not None
shapes=[k.GetEffectiveShape(p.F_Cu) for k in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if k.GetNetCode()!=code and k.IsOnLayer(p.F_Cu) and k.GetBoundingBox().Inflate(4000000).Contains(neck.GetStart())]
opts=[]
for dx in range(-20,41):
 for dy in range(-20,41):
  site=(old[0]+dx*25000,old[1]+dy*25000);e=entry(site)
  if e is None or e>original-30000 or e+120000>length:continue
  head.SetStart(p.VECTOR2I(*site))
  if any(head.GetEffectiveShape(p.F_Cu).Collide(s,200000) for s in shapes):continue
  # Keep the wide copper local to the component and avoid extending the original SW trunk.
  if head.GetLength()>math.dist(old,fixed)+250000:continue
  opts.append((e,head.GetLength(),site))
folder=root/'runs/phy-switch-entry';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
rec=None
for e,_,site in sorted(opts)[:8]:
 head.SetStart(p.VECTOR2I(*site));neck.SetEnd(p.VECTOR2I(*point(e+120000)))
 out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
 if delta:continue
 saved=p.LoadBoard(str(out));pres=verify_preservation(base,saved,replaced_copper=[head.m_Uuid.AsString(),neck.m_Uuid.AsString()]);assert not screen(saved)
 def linked(board):
  board.BuildConnectivity();q=board.FindFootprintByReference('U5').FindPadByNumber('30');z=board.FindFootprintByReference('L501').FindPadByNumber('1')
  return z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in board.GetConnectivity().GetConnectedItems(q)}
 assert linked(saved)
 victim=next(t for t in saved.GetTracks() if t.m_Uuid.AsString()==neck.m_Uuid.AsString());saved.Remove(victim);assert not linked(saved)
 rec=dict(wide_head_nm=site,narrow_centerline_mm=neck.GetLength()/1e6,uncovered_centerline_before_mm=original/1e6,uncovered_centerline_after_mm=e/1e6,wide_width_mm=1.55,narrow_width_mm=.20,cut_detected=True,preservation=pres);break
if not rec:out=src
(root/'phy-switch-entry.json').write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],drc_candidates=len(opts),change=rec,assembly_ready=False),indent=2)+'\n')
print(len(opts),rec and (rec['uncovered_centerline_before_mm'],rec['uncovered_centerline_after_mm']),flush=True);os._exit(0)
