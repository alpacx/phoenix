"""Place C518 at the remaining PHY 3V3 corner pin, keeping its ground return intact."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess,sys
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
clock='--clock-together' in sys.argv
move516='--pin11' in sys.argv
ref='C516' if move516 else 'C518'
pin_number='11' if move516 else '40'
cp=json.loads((root/('layout-opposite-bypass.json' if clock else 'layout-storage-io.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));base=p.LoadBoard(str(src));b.BuildConnectivity()
f=b.FindFootprintByReference(ref);pin=b.FindFootprintByReference('U5').FindPadByNumber(pin_number)
vcc=f.FindPadByNumber('1');gnd=f.FindPadByNumber('2')
assert vcc.GetNetCode()==pin.GetNetCode()
source_group={k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(vcc)}
assert (pin.m_Uuid.AsString() in source_group)==move516
old_ids={'91d7da59-2c3c-4c50-8933-76c2d14a9050','ac0929a2-3fca-4d5e-ba2d-c38b18d6595e','68d03e85-125d-4d76-a9dd-d8720122c640'}
if move516:
 old_ids={'28aeade0-65bc-40cb-b160-24169a4993a8','ba2dbe3a-556d-4e25-b0fc-d4e2839eac19','a91e9065-d525-48b7-be2b-2fc66ba91c01'}
 old_ids.update(t.m_Uuid.AsString() for t in b.GetTracks() if t.m_Uuid.AsString() in source_group)
clockref=b.FindFootprintByReference('C520')
clockref_pos=clockref.GetPosition()
if clock:
 old_ids.update({'e959cb29-180c-425e-b3b3-e3c6263bbe8d','f8c8dc40-2f58-4aed-b76f-0c719ae26ea0','b031e3f6-1250-473e-99ab-1038c94e01d3'})
 clockref.SetPosition(p.VECTOR2I(-20000000,-20000000))
old=[t for t in b.GetTracks() if t.m_Uuid.AsString() in old_ids]
assert len(old)==len(old_ids) and all(t.GetNetname() in ('GND','+3V3_PHY') for t in old)
for t in old:b.Remove(t)
others=[fp for fp in b.GetFootprints() if fp.GetReference()!=ref]
pads=[q for fp in others for q in fp.Pads() if q.GetBoundingBox().Inflate(6000000).Contains(pin.GetPosition())]
tracks=[t for t in b.GetTracks() if t.GetBoundingBox().Inflate(6000000).Contains(pin.GetPosition())]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
shapes={l:[(q.GetNetCode(),q.GetEffectiveShape(l)) for q in pads+tracks if q.IsOnLayer(l)] for l in layers}
courts=[fp.GetCourtyard(p.F_Cu).BBox() for fp in others if fp.GetLayer()==p.F_Cu and fp.GetCourtyard(p.F_Cu).BBox().Inflate(6000000).Contains(pin.GetPosition())]
def clear(t,l):return all(n==t.GetNetCode() or not t.GetEffectiveShape(l).Collide(s,200000) for n,s in shapes[l])
def trace(a,z,net):
    t=p.PCB_TRACK(b);t.SetStart(a);t.SetEnd(z);t.SetLayer(p.F_Cu);t.SetWidth(200000 if move516 and net==vcc.GetNetCode() else 300000);t.SetNetCode(net);return t
def makevia(pos):
    v=p.PCB_VIA(b);v.SetWidth(600000);v.SetDrill(300000);v.SetPosition(pos);v.SetNetCode(gnd.GetNetCode());v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetViaType(p.VIATYPE_THROUGH);return v
box=pin.GetBoundingBox()
starts=[p.VECTOR2I(x,y) for x in range(box.GetLeft()+10000,box.GetRight(),50000) for y in range(box.GetTop()+10000,box.GetBottom(),30000) if pin.HitTest(p.VECTOR2I(x,y))]
opts=[]
for dx in (range(-16,28) if move516 else range(-29,13)):
 for dy in (range(-20,28) if move516 else range(-3,28)):
  for angle in (0,90,180,270):
   f.SetOrientationDegrees(angle);f.SetPosition(pin.GetPosition()+p.VECTOR2I(dx*100000,dy*100000))
   if any(f.GetCourtyard(p.F_Cu).BBox().Intersects(c) for c in courts) or not all(clear(q,p.F_Cu) for q in (vcc,gnd)):continue
   for s in sorted(starts,key=lambda s:math.dist(tuple(s),tuple(vcc.GetPosition()))):
    t=trace(s,vcc.GetPosition(),vcc.GetNetCode())
    if t.GetLength()>(1450000 if move516 else 2400000) or not clear(t,p.F_Cu) or t.GetEffectiveShape(p.F_Cu).Collide(gnd.GetEffectiveShape(p.F_Cu),200000):continue
    opts.append((t.GetLength(),tuple(f.GetPosition()),angle,tuple(s)));break
folder=root/('runs/phy-front-clock-joint' if clock else 'runs/phy-pin11-bypass' if move516 else 'runs/phy-pin40-bypass');folder.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
known={o.m_Uuid.AsString() for o in base.GetConnectivity().GetConnectedItems(base.FindFootprintByReference('C511').FindPadByNumber('2'))}
existing=[tuple(v.GetPosition()) for v in tracks if isinstance(v,p.PCB_VIA) and v.m_Uuid.AsString() in known]
rec=None;trials=0
for length,pos,angle,start in sorted(opts):
 f.SetOrientationDegrees(angle);f.SetPosition(p.VECTOR2I(*pos));s=p.VECTOR2I(*start)
 if not clock and screen(b):continue
 sig=trace(s,vcc.GetPosition(),vcc.GetNetCode())
 sites=set(existing)|{tuple(gnd.GetPosition()+p.VECTOR2I(x*100000,y*100000)) for x in range(-10,11) for y in range(-10,11)}
 for site in sorted(sites,key=lambda k:math.dist(k,tuple(gnd.GetPosition()))):
  distance=math.dist(site,tuple(gnd.GetPosition()))
  if distance>1100000:break
  g=p.VECTOR2I(*site);ret=trace(gnd.GetPosition(),g,gnd.GetNetCode());v=makevia(g)
  if any(q.GetBoundingBox().Inflate(351000).Contains(g) for q in [vcc,gnd]):continue
  if not clear(ret,p.F_Cu) or any(ret.GetEffectiveShape(p.F_Cu).Collide(k.GetEffectiveShape(p.F_Cu),200000) for k in (sig,vcc)):continue
  if site not in existing and (any(q.GetBoundingBox().Inflate(351000).Contains(g) for q in pads) or not all(clear(v,l) for l in layers)):continue
  items=[sig,ret]+([] if site in existing else [v])
  if clock:
   load=b.FindFootprintByReference('C520')
   fixed=base.FindFootprintByReference('C520').FindPadByNumber('1').GetPosition()
   signal_pad=load.FindPadByNumber('1');ground_pad=load.FindPadByNumber('2')
   clkopts=[]
   for a in (90,180,270,0):
    load.SetOrientationDegrees(a)
    for dx in range(-4,5):
     for dy in range(-4,5):
      x=fixed+p.VECTOR2I(dx*100000,dy*100000)
      if math.dist(tuple(x),tuple(fixed))>400000:continue
      load.Move(x-signal_pad.GetPosition())
      box=load.GetCourtyard(p.F_Cu).BBox()
      if box.Intersects(f.GetCourtyard(p.F_Cu).BBox()) or any(box.Intersects(c) for c in courts):continue
      if not all(clear(q,p.F_Cu) for q in (signal_pad,ground_pad)):continue
      ct=trace(fixed,x,signal_pad.GetNetCode());ct.SetWidth(200000)
      if not clear(ct,p.F_Cu):continue
      for ox,oy in ((0,7),(7,0),(-7,0),(0,-7),(5,5),(-5,5),(5,-5),(-5,-5),(0,9),(9,0),(-9,0),(0,-9)):
       new=ground_pad.GetPosition()+p.VECTOR2I(ox*100000,oy*100000)
       gv=makevia(new);gt=trace(ground_pad.GetPosition(),new,ground_pad.GetNetCode())
       if any(q.GetBoundingBox().Inflate(351000).Contains(new) for q in pads+[signal_pad,ground_pad,vcc,gnd]):continue
       if not clear(gt,p.F_Cu) or not all(clear(gv,l) for l in layers):continue
       if any(o.GetNetCode()!=q.GetNetCode() and o.GetEffectiveShape(p.F_Cu).Collide(q.GetEffectiveShape(p.F_Cu),200000) for o in [gv,gt,ct,signal_pad,ground_pad] for q in items+[vcc,gnd]):continue
       clkopts.append((ct.GetLength()+gt.GetLength(),a,tuple(load.GetPosition()),[gt,gv]+([ct] if x!=fixed else [])))
   if not clkopts:continue
   _,a,position,loads=min(clkopts,key=lambda entry:entry[0]);load.SetOrientationDegrees(a);load.SetPosition(p.VECTOR2I(*position))
   items+=loads
   if screen(b):continue
  for item in items:b.Add(item)
  out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
  subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
  delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));trials+=1
  if not delta:
   saved=p.LoadBoard(str(out));pres=verify_preservation(base,saved,replaced_copper=old_ids);assert not screen(saved)
   q=saved.FindFootprintByReference(ref).FindPadByNumber('1')
   assert pin.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(q)}
   rec=dict(position_nm=pos,signal_mm=length/1e6,return_mm=distance/1e6,existing_ground=site in existing,preservation=pres);break
  for item in items:b.Remove(item)
  if trials>=12:break
 if rec or trials>=12:break
if not rec:out=src
(root/('phy-front-clock-joint.json' if clock else 'phy-pin11-bypass.json' if move516 else 'phy-pin40-bypass.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],placement_options=len(opts),drc_trials=trials,change=rec,assembly_ready=False),indent=2)+'\n')
print(len(opts),trials,rec and rec['position_nm'],flush=True);os._exit(0)
