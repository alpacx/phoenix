"""Try C518 between the PHY, crystal, C512 and relocated C520 using courtyard edge coordinates."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
rset='--rset' in sys.argv
pmic=next((arg for arg in sys.argv if arg in ('C413','C414','C415')),None)
ref=pmic or ('R513' if rset else 'C518')
stage='pmic-local-'+pmic if pmic else 'phy-rset-front-pocket' if rset else 'phy-c518-pocket'
cp=json.loads((root/({'C413':'layout-usb-shell.json','C414':'pmic-local-C413.json','C415':'pmic-local-C414.json'}[pmic] if pmic else 'layout-peripheral-supply-balls.json' if rset else 'phy-clock-load-window.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));base=p.LoadBoard(str(src));base.BuildConnectivity()
cap=b.FindFootprintByReference(ref);chip=b.FindFootprintByReference('U4' if pmic else 'U5');pin=chip.FindPadByNumber({'C413':'46','C414':'44','C415':'48'}[pmic] if pmic else '39' if rset else '40')
one,two=[cap.FindPadByNumber(n) for n in ('1','2')]
old={'91d7da59-2c3c-4c50-8933-76c2d14a9050','ac0929a2-3fca-4d5e-ba2d-c38b18d6595e','68d03e85-125d-4d76-a9dd-d8720122c640'}
if rset:old={'21186a84-1592-43f9-81bb-cf066de74848','56108bb3-0641-4179-9660-3d8afa3bd9f4','a9f4d91c-4225-488d-906c-7f5fc84fd508','e515bb5e-8aa0-4488-80cd-370176cc54b3','6a389b43-8a71-4916-9661-eb35bf5e425b'}
if pmic:
     branch=[t for t in b.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and t.IsOnLayer(p.F_Cu) and (two.HitTest(t.GetStart()) or two.HitTest(t.GetEnd()))]
     assert len(branch)==1
     far=branch[0].GetEnd() if two.HitTest(branch[0].GetStart()) else branch[0].GetStart()
     connected=[t for t in b.GetTracks() if t.GetStart()==far or t.GetEnd()==far]
     old={t.m_Uuid.AsString() for t in branch}
     if len(connected)==2:old.update(t.m_Uuid.AsString() for t in connected if isinstance(t,p.PCB_VIA))
cut=[t for t in b.GetTracks() if t.m_Uuid.AsString() in old];assert len(cut)==len(old) and all(t.GetNetname()=='GND' for t in cut)
for t in cut:b.Remove(t)
others=[f for f in b.GetFootprints() if f.GetReference()!=ref]
near=lambda k:k.GetBoundingBox().Inflate(6000000).Contains(pin.GetPosition())
pads=[q for f in others for q in f.Pads() if near(q)];traces=[k for k in b.GetTracks() if near(k)]
courts=[f.GetCourtyard(p.F_Cu).BBox() for f in others if f.GetLayer()==p.F_Cu and near(f)]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
obs={l:[(k.GetNetCode(),k.GetEffectiveShape(l)) for k in pads+traces if k.IsOnLayer(l)] for l in layers}
def free(t,l):
 shape=t.GetEffectiveShape(l)
 return all(k==t.GetNetCode() or not shape.Collide(o,200000) for k,o in obs[l])
def line(a,z,n):
 t=p.PCB_TRACK(b);t.SetWidth(200000 if rset and n==pin.GetNetCode() else 300000);t.SetLayer(p.F_Cu);t.SetNetCode(n);t.SetStart(a);t.SetEnd(z);return t
def via(z):
 v=p.PCB_VIA(b);v.SetWidth(600000);v.SetDrill(300000);v.SetNetCode(two.GetNetCode());v.SetPosition(z);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);return v
def paths(start,end):
 x,y=end-start;d=min(abs(x),abs(y));diag=p.VECTOR2I(int(math.copysign(d,x)),int(math.copysign(d,y)))
 for corner in (start,start+diag,end-diag):
    yield [(a,z) for a,z in ((start,corner),(corner,end)) if a!=z]
vec=p.VECTOR2I
def positions(lo,hi,edges):
 values=set(range(lo,hi+1,100000))
 for val in edges:
    for offset in (10000,30000,50000):
        for x in (val-offset,val+offset):
            if lo<=x<=hi:values.add(x)
 return sorted(values)
starts=[pin.GetPosition()+vec(x,y) for x in (-285000,-220000,-100000,0,180000,280000) for y in (75000,40000,0)]
starts=[a for a in starts if pin.HitTest(a)]
if pmic:
     edge=pin.GetBoundingBox().GetRight()
     starts=[vec(edge+i,pin.GetPosition().y) for i in (-100000,-50000,0,50000)]
known={k.m_Uuid.AsString() for k in base.GetConnectivity().GetConnectedItems(base.FindFootprintByReference('C511').FindPadByNumber('2'))}
grounds=[k for k in pads+traces if k.IsOnLayer(p.F_Cu) and k.m_Uuid.AsString() in known]
opts=[];fitting=0;signal_ok=0;courtfit=0;blockers={}
for angle in (0,90,180,270):
 cap.SetOrientationDegrees(angle);bb=cap.GetCourtyard(p.F_Cu).BBox();hw=bb.GetWidth()//2;hh=bb.GetHeight()//2
 xs=positions(pin.GetPosition().x-500000 if pmic else 58100000,pin.GetPosition().x+2700000 if pmic else 62200000,[v for c in courts for v in (c.GetLeft()-hw,c.GetRight()+hw)])
 ys=positions(pin.GetPosition().y-2500000 if pmic else 29400000 if rset else 32100000,pin.GetPosition().y+2500000 if pmic else 35500000,[v for c in courts for v in (c.GetTop()-hh,c.GetBottom()+hh)])
 for x in xs:
  for y in ys:
    cap.SetPosition(vec(x,y));bb=cap.GetCourtyard(p.F_Cu).BBox()
    if any(bb.Intersects(c) for c in courts):continue
    courtfit+=1
    if not all(free(q,p.F_Cu) for q in cap.Pads()):
        names={k.GetParentFootprint().GetReference()+'.'+k.GetNumber() if isinstance(k,p.PAD) else k.GetNetname() for q in cap.Pads() for k in pads+traces if k.IsOnLayer(p.F_Cu) and k.GetNetCode()!=q.GetNetCode() and k.GetEffectiveShape(p.F_Cu).Collide(q.GetEffectiveShape(p.F_Cu),200000)}
        key=tuple(sorted(names));blockers.setdefault(key,[angle,x,y]);continue
    fitting+=1;signals=[]
    for start in starts:
        for dx,dy in ((0,0),(-150000,0),(150000,0),(0,-150000),(0,150000)):
            end=one.GetPosition()+vec(dx,dy)
            if not one.HitTest(end):continue
            for coords in paths(start,end):
                ts=[line(a,z,one.GetNetCode()) for a,z in coords]
                length=sum(t.GetLength() for t in ts)
                if length<=2400000 and all(free(t,p.F_Cu) and not t.GetEffectiveShape(p.F_Cu).Collide(two.GetEffectiveShape(p.F_Cu),200000) for t in ts):
                    signals.append((length,ts))
    if not signals:continue
    signal_ok+=1;length,signal=min(signals,key=lambda o:o[0]);ground=two.GetPosition()
    existing=[]
    for k in grounds:
        pos=k.GetPosition()
        if isinstance(k,p.PCB_TRACK) and not isinstance(k,p.PCB_VIA):
            a,z=k.GetStart(),k.GetEnd();dx,dy=z-a;u=max(0,min(1,((ground.x-a.x)*dx+(ground.y-a.y)*dy)/max(1,dx*dx+dy*dy)));pos=a+vec(round(dx*u),round(dy*u))
        if math.dist(tuple(pos),tuple(ground))<=1200000:existing.append((tuple(pos),False))
    sites=existing+[(tuple(ground+vec(dx*100000,dy*100000)),True) for dx in range(-10,11) for dy in range(-10,11) if dx*dx+dy*dy<=110]
    for site,new in sites:
        gz=vec(*site);v=via(gz)
        if new and (any(q.GetBoundingBox().Inflate(351000).Contains(gz) for q in pads+[one,two]) or not all(free(v,l) for l in layers)):continue
        for coords in paths(ground,gz):
            ret=[line(a,z,two.GetNetCode()) for a,z in coords]
            gl=sum(t.GetLength() for t in ret)
            if gl>1200000 or not all(free(t,p.F_Cu) for t in ret):continue
            if any(t.GetEffectiveShape(p.F_Cu).Collide(s.GetEffectiveShape(p.F_Cu),200000) for t in ret+([v] if new else []) for s in signal+[one]):continue
            opts.append((length+gl,new,angle,(x,y),signal,ret,site))
            break
folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
for n in ('fp-lib-table','phy-joint.kicad_dru','phy-joint.kicad_pro'):shutil.copy2(src.parent/n,folder/n)
rec=None;attempts=0
for _,new,angle,pos,sig,ret,site in sorted(opts,key=lambda v:v[:4]):
 cap.SetOrientationDegrees(angle);cap.SetPosition(vec(*pos))
 if screen(b):continue
 items=sig+ret+([via(vec(*site))] if new else [])
 for t in items:b.Add(t)
 out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));attempts+=1
 if not delta:
    saved=p.LoadBoard(str(out));pres=verify_preservation(base,saved,replaced_copper=old);assert not screen(saved)
    a=saved.FindFootprintByReference(ref).FindPadByNumber('1')
    assert pin.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(a)}
    rec=dict(position_nm=pos,angle=angle,signal_length_mm=sum(t.GetLength() for t in sig)/1e6,ground_length_mm=sum(t.GetLength() for t in ret)/1e6,preservation=pres);break
 for t in items:b.Remove(t)
 if attempts>=12:break
if not rec:out=src
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],courtyard_fits=courtfit,blocking_sets=[dict(objects=key,example=value) for key,value in sorted(blockers.items(),key=lambda e:len(e[0]))[:16]],fits=fitting,short_bypass_poses=signal_ok,options=len(opts),attempts=attempts,change=rec,assembly_ready=False),indent=2)+'\n')
print(fitting,signal_ok,len(opts),attempts,bool(rec),flush=True);os._exit(0)
