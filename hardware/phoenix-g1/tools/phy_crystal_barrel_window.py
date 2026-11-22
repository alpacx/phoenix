"""Shift Y501 and reconnect its lands while reserving both C518 rear capped-via locations."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'phy-clock-load-window.json').read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));base=p.LoadBoard(str(src));crystal=b.FindFootprintByReference('Y501')
center=crystal.GetPosition();oldpads={q.GetNumber():q.GetPosition() for q in crystal.Pads()}
old={'2a176e64-c95e-43e0-89f9-f2b5f584ce09','d3b1e057-da6c-4b9c-9a7e-292026d311af'}
remove=[t for t in b.GetTracks() if t.m_Uuid.AsString() in old];assert len(remove)==2 and all(t.GetNetname()=='PHY_XIN' for t in remove)
for t in remove:b.Remove(t)
vec=p.VECTOR2I
refs=[f for f in b.GetFootprints() if f.GetReference()!='Y501']
near=lambda t:t.GetBoundingBox().Inflate(6000000).Contains(center)
pads=[q for f in refs for q in f.Pads() if near(q)]
tracks=[t for t in b.GetTracks() if near(t)]
courts=[f.GetCourtyard(p.F_Cu).BBox() for f in refs if f.GetLayer()==p.F_Cu and near(f)]
net=b.GetNetcodeFromNetname
def barrel(pos,n):
 v=p.PCB_VIA(b);v.SetWidth(550000);v.SetDrill(300000);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetViaType(p.VIATYPE_THROUGH);v.SetPosition(vec(*pos));v.SetNetCode(n);return v
angled='--angled-capped' in sys.argv
sites=[(60100000,33900000),(59140000,33900000)]
stage='phy-crystal-barrel-window'
if angled:
 result=json.loads((root/'rear-c518-angled-capped.json').read_text())
 assert result['parent_sha256']==cp['sha256']
 sites=next(row['sites'] for row in result['return_conflicts'] if row['objects']==['Y501.1'])
 stage='phy-crystal-angled-window'
reserved=[barrel(site,net(name)) for site,name in zip(sites,('+3V3_PHY','GND'))]
shapes=[(k.GetNetCode(),k.GetEffectiveShape(p.F_Cu)) for k in pads+tracks+reserved if k.IsOnLayer(p.F_Cu)]
def free(t):
 shape=t.GetEffectiveShape(p.F_Cu)
 return all(n==t.GetNetCode() or not shape.Collide(o,200000) for n,o in shapes)
def track(a,z,n):
 t=p.PCB_TRACK(b);t.SetWidth(300000 if n==net('GND') else 200000);t.SetNetCode(n);t.SetLayer(p.F_Cu);t.SetStart(a);t.SetEnd(z);return t
def paths(a,z):
 x,y=z-a;d=min(abs(x),abs(y));step=vec(int(math.copysign(d,x)),int(math.copysign(d,y)))
 for c in (a,a+step,z-step,vec(a.x,z.y),vec(z.x,a.y)):
    yield [(u,v) for u,v in ((a,c),(c,z)) if u!=v]
anchor=vec(59475000,34400000)
opts=[];clear_poses=0;reasons={}
for dx in range(-30,16 if angled else 1):
 for dy in range(-11,12):
    delta=vec(dx*50000,dy*50000);crystal.SetPosition(center+delta)
    cbox=crystal.GetCourtyard(p.F_Cu).BBox()
    if any(cbox.Intersects(c) for c in courts) or not all(free(q) for q in crystal.Pads()):
        objects={f.GetReference() for f in refs if f.GetLayer()==p.F_Cu and near(f) and cbox.Intersects(f.GetCourtyard(p.F_Cu).BBox())}
        for q in crystal.Pads():
            for k in pads+tracks+reserved:
                if k.IsOnLayer(p.F_Cu) and k.GetNetCode()!=q.GetNetCode() and q.GetEffectiveShape(p.F_Cu).Collide(k.GetEffectiveShape(p.F_Cu),200000):
                    objects.add(k.GetParentFootprint().GetReference() if isinstance(k,p.PAD) else ('C518-reserved' if k in reserved else k.GetNetname()))
        key=tuple(sorted(objects));reasons.setdefault(key,tuple(delta));continue
    clear_poses+=1;added=[]
    for q in sorted(crystal.Pads(),key=lambda pad:pad.GetNumber()):
        n=q.GetNetCode();num=q.GetNumber();a=anchor if num=='1' else oldpads[num]
        if q.HitTest(a):continue
        local=[]
        for x in (-450000,-250000,0,250000,450000):
         for y in (-350000,0,350000):
            end=q.GetPosition()+vec(x,y)
            if not q.HitTest(end):continue
            for points in paths(a,end):
                ts=[track(u,v,n) for u,v in points];length=sum(t.GetLength() for t in ts)
                if length>2200000:continue
                if not all(free(t) and all(k.GetNetCode()==n or not t.GetEffectiveShape(p.F_Cu).Collide(k.GetEffectiveShape(p.F_Cu),200000) for k in list(crystal.Pads())+added) for t in ts):continue
                local.append((length,ts))
        if not local:break
        added+=min(local,key=lambda r:r[0])[1]
    else:opts.append((sum(t.GetLength() for t in added),tuple(crystal.GetPosition()),added))
folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
for n in ('fp-lib-table','phy-joint.kicad_dru','phy-joint.kicad_pro'):shutil.copy2(src.parent/n,folder/n)
rec=None;attempts=0
for length,position,items in sorted(opts,key=lambda r:r[0]):
 crystal.SetPosition(vec(*position))
 if screen(b):continue
 for t in items:b.Add(t)
 out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));attempts+=1
 if not delta:
    saved=p.LoadBoard(str(out))
    try:pres=verify_preservation(base,saved,replaced_copper=old)
    except AssertionError:pres=None
    if pres and not screen(saved):
        rec=dict(position_nm=position,total_added_trace_mm=length/1e6,preservation=pres);break
 for t in items:b.Remove(t)
 if attempts>=15:break
if not rec:out=src
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],poses=clear_poses,obstacles=[dict(objects=k,example_delta_nm=v) for k,v in sorted(reasons.items(),key=lambda e:len(e[0]))[:12]],options=len(opts),drc_attempts=attempts,change=rec,oscillator_qualified=False,assembly_ready=False),indent=2)+'\n')
print(clear_poses,len(opts),attempts,bool(rec),flush=True);os._exit(0)
