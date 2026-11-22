"""Leave room for a pin-40 power barrel while retaining C520 close to the oscillator."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'layout-phy-full-feed.json').read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
base=p.LoadBoard(str(src));base.BuildConnectivity();b=p.LoadBoard(str(src))
old={'e959cb29-180c-425e-b3b3-e3c6263bbe8d','f8c8dc40-2f58-4aed-b76f-0c719ae26ea0','b031e3f6-1250-473e-99ab-1038c94e01d3'}
cut=[t for t in b.GetTracks() if t.m_Uuid.AsString() in old]
assert len(cut)==3 and all(t.GetNetname()=='GND' for t in cut)
for t in cut:b.Remove(t)
load=b.FindFootprintByReference('C520');one,two=[load.FindPadByNumber(n) for n in ('1','2')]
fixed=one.GetPosition();vectors=p.VECTOR2I;center=vectors(60600000,33900000)
chip=b.FindFootprintByReference('U5');power=chip.FindPadByNumber('40').GetNetCode()
others=[f for f in b.GetFootprints() if f.GetReference()!='C520']
near=lambda t:t.GetBoundingBox().Inflate(6000000).Contains(fixed)
courts=[f.GetCourtyard(p.F_Cu).BBox() for f in others if f.GetLayer()==p.F_Cu and near(f)]
pads=[q for f in others for q in f.Pads() if near(q)];traces=[t for t in b.GetTracks() if near(t)]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
shapes={l:[(k.GetNetCode(),k.GetEffectiveShape(l)) for k in pads+traces if k.IsOnLayer(l)] for l in layers}
def free(t,l):
 shape=t.GetEffectiveShape(l)
 return all(n==t.GetNetCode() or not shape.Collide(s,200000) for n,s in shapes[l])
def trace(a,z,n,w):
 t=p.PCB_TRACK(b);t.SetWidth(w);t.SetLayer(p.F_Cu);t.SetNetCode(n);t.SetStart(a);t.SetEnd(z);return t
def barrel(pos,net):
 v=p.PCB_VIA(b);v.SetWidth(600000);v.SetDrill(300000);v.SetNetCode(net);v.SetPosition(pos);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);return v
reserved=barrel(center,power)
assert all(free(reserved,l) for l in layers)
known={k.m_Uuid.AsString() for k in base.GetConnectivity().GetConnectedItems(base.FindFootprintByReference('C511').FindPadByNumber('2'))}
existing=[k for k in pads+traces if k.IsOnLayer(p.F_Cu) and k.m_Uuid.AsString() in known and (isinstance(k,p.PCB_VIA) or isinstance(k,p.PAD))]
options=[];fitting=0
def clear_reserved(k):return not k.GetEffectiveShape(p.F_Cu).Collide(reserved.GetEffectiveShape(p.F_Cu),200000)
for angle in (0,90,180,270):
 load.SetOrientationDegrees(angle)
 for dx in range(-4,5):
  for dy in range(-4,5):
   end=fixed+vectors(dx*50000,dy*50000);load.Move(end-one.GetPosition())
   if not one.HitTest(fixed) or not all(clear_reserved(q) and free(q,p.F_Cu) for q in (one,two)):continue
   if any(load.GetCourtyard(p.F_Cu).BBox().Intersects(c) for c in courts):continue
   fitting+=1;ground=two.GetPosition()
   sites=[(k.GetPosition(),False) for k in existing if math.dist(tuple(k.GetPosition()),tuple(ground))<=1450000]
   sites.extend((ground+vectors(x*100000,y*100000),True) for x in range(-11,12) for y in range(-11,12) if x*x+y*y<=121)
   for gs,new in sites:
    if new:
     if any(q.GetBoundingBox().Inflate(351000).Contains(gs) for q in pads+[one,two]):continue
     if any(isinstance(k,p.PCB_VIA) and math.dist(tuple(k.GetPosition()),tuple(gs))<800000 for k in traces):continue
     v=barrel(gs,two.GetNetCode())
     if not all(free(v,l) for l in layers) or math.dist(tuple(center),tuple(gs))<800000:continue
    delta=gs-ground;d=min(abs(delta.x),abs(delta.y));step=vectors(int(math.copysign(d,delta.x)),int(math.copysign(d,delta.y)))
    for corner in (ground+step,gs-step):
     ts=[trace(a,z,two.GetNetCode(),300000) for a,z in ((ground,corner),(corner,gs)) if a!=z]
     if not ts or not all(free(t,p.F_Cu) and clear_reserved(t) and not t.GetEffectiveShape(p.F_Cu).Collide(one.GetEffectiveShape(p.F_Cu),200000) for t in ts):continue
     length=sum(t.GetLength() for t in ts)
     if length<=1500000:
      options.append((length,math.dist(tuple(end),tuple(fixed)),angle,tuple(load.GetPosition()),tuple(gs),new,ts))
     break
folder=root/'runs/phy-clock-load-window';folder.mkdir(exist_ok=True)
for n in ('fp-lib-table','phy-joint.kicad_dru','phy-joint.kicad_pro'):shutil.copy2(src.parent/n,folder/n)
rec=None;attempts=0
for length,shift,angle,pos,gs,new,ts in sorted(options,key=lambda e:e[:2]):
 load.SetOrientationDegrees(angle);load.SetPosition(vectors(*pos))
 if screen(b):continue
 items=ts+([barrel(vectors(*gs),two.GetNetCode())] if new else [])
 for t in items:b.Add(t)
 out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));attempts+=1
 if not delta:
    saved=p.LoadBoard(str(out));pres=verify_preservation(base,saved,replaced_copper=old);assert not screen(saved)
    rec=dict(position_nm=pos,angle=angle,clock_pad_displacement_mm=shift/1e6,ground_mm=length/1e6,ground_new_via=new,ground_site_nm=gs,preservation=pres);break
 for t in items:b.Remove(t)
 if attempts>=12:break
if not rec:out=src
(root/'phy-clock-load-window.json').write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],fitting_poses=fitting,return_options=len(options),attempts=attempts,change=rec,assembly_ready=False),indent=2)+'\n')
print(fitting,len(options),attempts,bool(rec),flush=True);os._exit(0)
