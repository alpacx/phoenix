"""Fit C518 behind pin 40 with one off-pad via per terminal and short local traces."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
detour='--pmic-detour' in sys.argv
pmic=next((arg for arg in sys.argv if arg in ('C413','C414','C415')),None)
bank_rset='--bank-rset' in sys.argv
fresh='--fresh-placement' in sys.argv or bank_rset or bool(pmic)
bent_return='--bent-return' in sys.argv
angled_return='--angled-return' in sys.argv or bent_return
angled='--angled-capped' in sys.argv or angled_return
rset='--rset' in sys.argv or bank_rset
radial='--radial' in sys.argv
window='--clock-window' in sys.argv or radial
reuse='--reuse-rear-ground' in sys.argv
both='--both-capped' in sys.argv
centered='--centered-barrel' in sys.argv or both
passive=pmic or ('R513' if rset else 'C518')
cp=json.loads((root/('pmic-3v3-via-clearance.json' if detour else {'C413':'layout-usb-shell.json','C414':'pmic-rear-C413.json','C415':'pmic-rear-C414.json'}[pmic] if pmic else 'layout-cap-bank.json' if bank_rset else 'phy-clock-load-window.json' if window else 'layout-opposite-bypass.json' if rset else 'layout-package-local.json')).read_text())
src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src))
base=p.LoadBoard(str(src))
old={'91d7da59-2c3c-4c50-8933-76c2d14a9050','ac0929a2-3fca-4d5e-ba2d-c38b18d6595e','68d03e85-125d-4d76-a9dd-d8720122c640'}
rotate='--rotate-load' in sys.argv
stage=('rear-phy-c518-clock-'+sys.argv[sys.argv.index('--rotate-load')+1]) if rotate else 'rear-phy-c518'
if window:stage='rear-c518-window-reuse' if reuse else 'rear-c518-window-double' if both else 'rear-c518-window-capped' if centered else 'rear-c518-window'
if radial:stage='rear-c518-window-radial-capped' if centered else 'rear-c518-window-radial'
if angled:
    assert centered and window and not radial
    if angled_return:
        assert not both
        stage='rear-c518-angled-existing-return' if reuse else 'rear-c518-angled-offpad-return'
    else:
        assert both and not reuse
        stage='rear-c518-angled-capped'
if bent_return:
    assert reuse
    stage='rear-c518-bent-existing-return-fresh' if fresh else 'rear-c518-bent-existing-return'
if rset:
    assert not rotate
    stage='rear-rset-cap-bank' if bank_rset else 'rear-phy-rset'
    old={'21186a84-1592-43f9-81bb-cf066de74848','56108bb3-0641-4179-9660-3d8afa3bd9f4','a9f4d91c-4225-488d-906c-7f5fc84fd508','e515bb5e-8aa0-4488-80cd-370176cc54b3','6a389b43-8a71-4916-9661-eb35bf5e425b'}
if rotate:
    old.update({'e959cb29-180c-425e-b3b3-e3c6263bbe8d','f8c8dc40-2f58-4aed-b76f-0c719ae26ea0','b031e3f6-1250-473e-99ab-1038c94e01d3'})
if pmic:
    stage='pmic-rear-'+pmic+('-detour' if detour else '')
    pad=b.FindFootprintByReference(pmic).FindPadByNumber('2')
    branch=[t for t in b.GetTracks() if not isinstance(t,p.PCB_VIA) and t.IsOnLayer(p.F_Cu) and t.GetNetname()=='GND' and (pad.HitTest(t.GetStart()) or pad.HitTest(t.GetEnd()))]
    assert len(branch)==1
    far=branch[0].GetEnd() if pad.HitTest(branch[0].GetStart()) else branch[0].GetStart()
    attached=[t for t in b.GetTracks() if t.GetStart()==far or t.GetEnd()==far]
    old={t.m_Uuid.AsString() for t in branch}
    if len(attached)==2:old.update(t.m_Uuid.AsString() for t in attached if isinstance(t,p.PCB_VIA))
remove=[t for t in b.GetTracks() if t.m_Uuid.AsString() in old]
assert len(remove)==len(old) and all(t.GetNetname()=='GND' for t in remove)
for t in remove:b.Remove(t)
chip=b.FindFootprintByReference('U4' if pmic else 'U5')
pin=chip.FindPadByNumber({'C413':'46','C414':'44','C415':'48'}[pmic] if pmic else '39' if rset else '40')
cap=b.FindFootprintByReference(passive)
cap.Flip(cap.GetPosition(),False)
rail,gnd=[cap.FindPadByNumber(n) for n in ('1','2')]
assert rail.GetNetCode()==pin.GetNetCode()
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
if rotate:
    load=b.FindFootprintByReference('C520')
    fixed=load.FindPadByNumber('1').GetPosition()
    load.SetOrientationDegrees(load.GetOrientationDegrees()+float(sys.argv[sys.argv.index('--rotate-load')+1]))
    load.Move(fixed-load.FindPadByNumber('1').GetPosition())
    assert fixed==load.FindPadByNumber('1').GetPosition()
pads=[q for f in b.GetFootprints() if f.GetReference()!=passive for q in f.Pads() if q.GetBoundingBox().Inflate(6000000).Contains(pin.GetPosition())]
tracks=[t for t in b.GetTracks() if t.GetBoundingBox().Inflate(6000000).Contains(pin.GetPosition())]
shapes={l:[(k.GetNetCode(),k.GetEffectiveShape(l)) for k in pads+tracks if k.IsOnLayer(l)] for l in layers}
courts=[f.GetCourtyard(p.B_Cu).BBox() for f in b.GetFootprints() if f.GetLayer()==p.B_Cu and f.GetReference()!=passive and f.GetBoundingBox(False,False).Inflate(6000000).Contains(pin.GetPosition())]
if angled or bank_rset or detour:
    facing=[f.GetCourtyard(p.B_Cu) for f in b.GetFootprints() if f.GetLayer()==p.B_Cu and f.GetReference()!=passive and f.GetBoundingBox(False,False).Inflate(6000000).Contains(pin.GetPosition())]
def courtyard_conflict():
    outline=cap.GetCourtyard(p.B_Cu)
    if angled or bank_rset or detour:
        return any(outline.Collide(other,0) for other in facing)
    return any(outline.BBox().Intersects(c) for c in courts)
def clear(k,l):
    return all(n==k.GetNetCode() or not k.GetEffectiveShape(l).Collide(s,200000) for n,s in shapes[l])
def via(site,net):
    v=p.PCB_VIA(b);v.SetWidth(450000 if rset and net==rail.GetNetCode() else 550000 if centered and (net==rail.GetNetCode() or both) else 600000);v.SetDrill(200000 if rset and net==rail.GetNetCode() else 300000);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetPosition(site);v.SetNetCode(net)
    if centered and (net==rail.GetNetCode() or both):v.SetCappingMode(p.CAPPING_MODE_CAPPED);v.SetFillingMode(p.FILLING_MODE_FILLED)
    return v
def tr(a,z,l,n):
    t=p.PCB_TRACK(b);t.SetLayer(l);t.SetStart(a);t.SetEnd(z);t.SetWidth(200000 if rset and n==rail.GetNetCode() else 300000);t.SetNetCode(n);return t
def available(v):
    z=v.GetPosition()
    return not any(q.GetBoundingBox().Inflate(v.GetWidth(p.F_Cu)//2+51000).Contains(z) for q in pads) and not any(isinstance(t,p.PCB_VIA) and math.dist(tuple(t.GetPosition()),tuple(z))<800000 for t in tracks) and all(clear(v,l) for l in layers)
vec=p.VECTOR2I
starts=[pin.GetPosition()+vec(x,y) for x in range(-400000,1,50000) for y in (-60000,0,60000)]
starts=[s for s in starts if pin.HitTest(s)]
if pmic:starts=[vec(pin.GetBoundingBox().GetRight()+i,pin.GetPosition().y) for i in (-100000,-50000,0,50000)]
clock_return=None
load_conflicts=[]
if rotate:
    earth=load.FindPadByNumber('2')
    near=earth.GetPosition()
    for other in b.GetFootprints():
        if other.GetReference() in ('C518','C520') or other.GetLayer()!=p.F_Cu:continue
        if load.GetCourtyard(p.F_Cu).BBox().Intersects(other.GetCourtyard(p.F_Cu).BBox()):
            load_conflicts.append(other.GetReference())
    for distance in (700000,800000,900000,1000000):
        for dx,dy in ((1,0),(0,1),(-1,0),(0,-1),(.707,.707),(-.707,.707),(.707,-.707),(-.707,-.707)):
            pos=near+vec(round(dx*distance),round(dy*distance))
            v=via(pos,earth.GetNetCode());t=tr(near,pos,p.F_Cu,earth.GetNetCode())
            if available(v) and clear(t,p.F_Cu):
                clock_return=[v,t];break
        if clock_return:break
    if not clock_return and not load_conflicts:
        anchor=base.FindFootprintByReference('C511').FindPadByNumber('2')
        base.BuildConnectivity()
        grounded={k.m_Uuid.AsString() for k in base.GetConnectivity().GetConnectedItems(anchor)}
        for k in sorted(tracks,key=lambda item:math.dist(tuple(near),tuple(item.GetStart()))):
            if not isinstance(k,p.PCB_VIA) or k.m_Uuid.AsString() not in grounded:continue
            pos=k.GetPosition()
            if math.dist(tuple(pos),tuple(near))>1300000:continue
            t=tr(near,pos,p.F_Cu,earth.GetNetCode())
            if clear(t,p.F_Cu):
                clock_return=[t];break
    if clock_return:
        for part in clock_return:
            b.Add(part);tracks.append(part)
            for l in layers:
                if part.IsOnLayer(l):shapes[l].append((part.GetNetCode(),part.GetEffectiveShape(l)))
landings=[]
blockers={}
free_sites=0
bore_conflicts={}
for x in (range(0,22) if pmic else range(-24,8)):
 for y in range(-16,18):
    z=pin.GetPosition()+vec(100000*x,100000*y)
    v=via(z,rail.GetNetCode())
    if not available(v):
        obstacles=set()
        for k in pads+tracks:
            if isinstance(k,p.PAD):
                label=k.GetParentFootprint().GetReference()+'.'+k.GetNumber()
                if k.GetBoundingBox().Inflate(351000).Contains(z):obstacles.add(label)
            else:
                label=k.GetNetname()+' '+b.GetLayerName(k.GetLayer())
                if isinstance(k,p.PCB_VIA) and math.dist(tuple(k.GetPosition()),tuple(z))<800000:obstacles.add(label)
            if k.GetNetCode()!=rail.GetNetCode() and any(k.IsOnLayer(l) and k.GetEffectiveShape(l).Collide(v.GetEffectiveShape(l),200000) for l in layers):
                obstacles.add(label)
        key=tuple(sorted(obstacles))
        distance=math.dist(tuple(pin.GetPosition()),tuple(z))
        if distance<=1800000 and (key not in bore_conflicts or distance<bore_conflicts[key][0]):bore_conflicts[key]=(distance,tuple(z))
        continue
    free_sites+=1
    for s in sorted(starts,key=lambda s:math.dist(tuple(s),tuple(z))):
        t=tr(s,z,p.F_Cu,rail.GetNetCode())
        if t.GetLength()<=1800000 and clear(t,p.F_Cu):
            landings.append((t.GetLength(),tuple(s),tuple(z)));break
        if t.GetLength()<=1800000:
            blocked=[k for k in pads+tracks if k.IsOnLayer(p.F_Cu) and k.GetNetCode()!=pin.GetNetCode() and t.GetEffectiveShape(p.F_Cu).Collide(k.GetEffectiveShape(p.F_Cu),200000)]
            key=tuple(sorted({k.GetParentFootprint().GetReference()+'.'+k.GetNumber() if isinstance(k,p.PAD) else k.GetNetname() for k in blocked}))
            if key and (key not in blockers or t.GetLength()<blockers[key][0]):blockers[key]=(t.GetLength(),tuple(s),tuple(z))
opts=[]
return_conflicts={}
funnel=dict(courtyard=0,pads=0,signal=0,cap_land=0,ground_bore=0)
directions=[vec(x,y) for x,y in ((0,800000),(800000,0),(0,-800000),(-800000,0),(600000,600000),(-600000,600000),(600000,-600000),(-600000,-600000))]
base.BuildConnectivity()
anchor=base.FindFootprintByReference('C511').FindPadByNumber('2')
grounded={k.m_Uuid.AsString() for k in base.GetConnectivity().GetConnectedItems(anchor)}
existing=[k for k in pads+tracks if k.IsOnLayer(p.B_Cu) and k.m_Uuid.AsString() in grounded]
if radial or angled_return:
    directions=[vec(x*100000,y*100000) for x in range(-11,12) for y in range(-11,12) if x*x+y*y<=121]
    ground_sites=set()
    for ix in range(575,635):
      for iy in range(306,373):
        site=(ix*100000,iy*100000)
        if available(via(vec(*site),gnd.GetNetCode())):ground_sites.add(site)
for length,start,site in sorted(landings):
    z=vec(*site)
    for angle in (range(0,360,5) if angled or bank_rset or detour else range(0,360,45) if radial else (0,90,180,270)):
        cap.SetOrientationDegrees(angle)
        for d in ([vec(0,0)] if centered else directions):
            if radial and not centered and (d.EuclideanNorm()<550000 or d.EuclideanNorm()+length>2400000):continue
            cap.Move(z+d-rail.GetPosition())
            if courtyard_conflict():continue
            funnel["courtyard"]+=1
            if not all(clear(q,p.B_Cu) for q in (gnd,rail)):continue
            funnel["pads"]+=1
            signal=tr(z,rail.GetPosition(),p.B_Cu,rail.GetNetCode())
            if not clear(signal,p.B_Cu) or signal.GetEffectiveShape(p.B_Cu).Collide(gnd.GetEffectiveShape(p.B_Cu),200000):continue
            funnel["signal"]+=1
            if centered and any(not rail.HitTest(z+vec(round(275000*math.cos(i*math.pi/32)),round(275000*math.sin(i*math.pi/32)))) for i in range(64)):continue
            funnel["cap_land"]+=1
            if both:
                gc=gnd.GetPosition();test=via(gc,gnd.GetNetCode());conflict=set()
                for k in pads+tracks:
                    label=k.GetParentFootprint().GetReference()+'.'+k.GetNumber() if isinstance(k,p.PAD) else k.GetNetname()+' '+b.GetLayerName(k.GetLayer())
                    if isinstance(k,p.PAD) and k.GetBoundingBox().Inflate(326000).Contains(gc):conflict.add(label)
                    if isinstance(k,p.PCB_VIA) and math.dist(tuple(k.GetPosition()),tuple(gc))<800000:conflict.add(label)
                    if k.GetNetCode()!=gnd.GetNetCode() and any(k.IsOnLayer(l) and test.GetEffectiveShape(l).Collide(k.GetEffectiveShape(l),200000) for l in layers):conflict.add(label)
                return_conflicts[tuple(sorted(conflict))]=[site,tuple(gc)]
            offsets=[vec(0,0)] if both else directions
            if radial or angled_return:offsets=[vec(*pt)-gnd.GetPosition() for pt in ground_sites if math.dist(pt,tuple(gnd.GetPosition()))<=1150000]
            if reuse:
                offsets=[]
                for k in existing:
                    pos=k.GetPosition()
                    if isinstance(k,p.PCB_TRACK) and not isinstance(k,p.PCB_VIA):
                        a,z0=k.GetStart(),k.GetEnd();xx,yy=z0-a;g=gnd.GetPosition()
                        ratio=max(0,min(1,((g.x-a.x)*xx+(g.y-a.y)*yy)/max(1,xx*xx+yy*yy)))
                        pos=vec(round(a.x+ratio*xx),round(a.y+ratio*yy))
                    delta=pos-gnd.GetPosition()
                    if delta.EuclideanNorm()<=(1900000 if bent_return else 1500000):offsets.append(delta)
            for e in offsets:
                g=gnd.GetPosition()+e;gv=via(g,gnd.GetNetCode())
                if not reuse and (not available(gv) or math.dist(site,tuple(g))<800000):continue
                funnel["ground_bore"]+=1
                if any(q.GetBoundingBox().Inflate(351000).Contains(a) for q in (rail,gnd) for a in ((z,) if reuse else (z,g)) if not ((centered and a==z and q.GetNumber()=='1') or (both and a==g and q.GetNumber()=='2'))):continue
                if both and any(not gnd.HitTest(g+vec(round(275000*math.cos(i*math.pi/32)),round(275000*math.sin(i*math.pi/32)))) for i in range(64)):continue
                ret=tr(gnd.GetPosition(),g,p.B_Cu,gnd.GetNetCode())
                corner=None
                if not clear(ret,p.B_Cu):
                    if not bent_return:continue
                    a=gnd.GetPosition();x,y=g-a;d=min(abs(x),abs(y));step=vec(int(math.copysign(d,x)),int(math.copysign(d,y)))
                    for c in (a+step,g-step):
                        legs=[tr(k,m,p.B_Cu,gnd.GetNetCode()) for k,m in ((a,c),(c,g)) if k!=m]
                        if legs and sum(t.GetLength() for t in legs)<=1900000 and all(clear(t,p.B_Cu) and not t.GetEffectiveShape(p.B_Cu).Collide(rail.GetEffectiveShape(p.B_Cu),200000) for t in legs):
                            corner=tuple(c);break
                    if corner is None:continue
                opts.append((length+signal.GetLength()+ret.GetLength(),start,site,angle,tuple(cap.GetPosition()),tuple(g),corner))
folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
for n in ('fp-lib-table','phy-joint.kicad_dru','phy-joint.kicad_pro'):shutil.copy2(src.parent/n,folder/n)
change=None
for _,start,site,angle,loc,gs,corner in sorted(opts,key=lambda r:(r[3]%90!=0,r[:6])):
    if fresh:
        assert (bent_return or bank_rset or pmic) and not rotate
        b=p.LoadBoard(str(src))
        for t in list(b.GetTracks()):
            if t.m_Uuid.AsString() in old:b.Remove(t)
        cap=b.FindFootprintByReference(passive)
        cap.Flip(cap.GetPosition(),False)
        rail,gnd=[cap.FindPadByNumber(n) for n in ('1','2')]
    cap.SetOrientationDegrees(angle);cap.SetPosition(vec(*loc))
    if (rotate and not clock_return) or screen(b):continue
    items=[via(vec(*site),rail.GetNetCode()),via(vec(*gs),gnd.GetNetCode()),tr(vec(*start),vec(*site),p.F_Cu,rail.GetNetCode()),tr(vec(*site),rail.GetPosition(),p.B_Cu,rail.GetNetCode()),tr(vec(*gs),gnd.GetPosition(),p.B_Cu,gnd.GetNetCode())]
    if corner is not None:
        items[-1:]=[tr(gnd.GetPosition(),vec(*corner),p.B_Cu,gnd.GetNetCode()),tr(vec(*corner),vec(*gs),p.B_Cu,gnd.GetNetCode())]
    if reuse:items.pop(1)
    items=[t for t in items if isinstance(t,p.PCB_VIA) or t.GetLength()>0]
    for t in items:b.Add(t)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if not delta:
        saved=p.LoadBoard(str(out));pres=verify_preservation(base,saved,replaced_copper=old)
        pad=saved.FindFootprintByReference(passive).FindPadByNumber('1')
        assert pin.m_Uuid.AsString() in {t.m_Uuid.AsString() for t in saved.GetConnectivity().GetConnectedItems(pad)}
        change=dict(location_nm=loc,power_via_nm=site,ground_endpoint_nm=gs,new_ground_barrel=not reuse,preservation=pres);break
    for t in items:b.Remove(t)
if not change:out=src
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],placement_stages=funnel,return_conflicts=[dict(objects=k,sites=v) for k,v in return_conflicts.items()],rotated_load=rotate,load_courtyard_conflicts=load_conflicts,clock_return_found=bool(clock_return),free_barrel_sites=free_sites,bore_conflicts=[dict(objects=k,example=v) for k,v in sorted(bore_conflicts.items(),key=lambda item:(len(item[0]),item[1][0]))[:12]],obstacle_sets=[dict(objects=k,example=v) for k,v in sorted(blockers.items(),key=lambda item:(len(item[0]),item[1][0]))[:12]],local_landings=len(landings),placements=len(opts),change=change,assembly_ready=False),indent=2)+'\n')
print(len(landings),len(opts),bool(change),flush=True);os._exit(0)
