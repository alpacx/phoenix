"""Locate the CPU's isolated bulk MLCC beside its existing positive bank and a short plane return."""
from pathlib import Path
from collections import Counter
import hashlib,json,math,shutil,subprocess,sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
new_bank='--peer=C1602' in sys.argv
doc=json.loads((r/('layout-recovery-adc-relocated.json' if new_bank else 'layout-emmc-data-power.json')).read_text());src=r/doc['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==doc['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();f=b.FindFootprintByReference('C1605')
side=p.B_Cu;q1,q2=[f.FindPadByNumber(n) for n in ('1','2')]
assert all(not b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()) and f.GetLayer()==side
peer=next((arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--peer=')),'C1603')
assert peer in ('C1602','C1603','C1608','C1606','C1607')
bank=b.FindFootprintByReference(peer).FindPadByNumber('1');g=b.FindFootprintByReference('U4').FindPadByNumber('69')
uid=lambda o:o.m_Uuid.AsString();xy=lambda o:tuple(o.GetPosition());v=lambda pt:p.VECTOR2I(*pt)
rail_id={uid(o) for o in b.GetConnectivity().GetConnectedItems(bank)};gnd_id={uid(o) for o in b.GetConnectivity().GetConnectedItems(g)}
balls=[xy(q) for q in b.FindFootprintByReference('U1').Pads() if q.GetNetCode()==q1.GetNetCode()]
old_distance=min(math.dist(xy(f),pt) for pt in balls)
old=xy(f)
release='--release-pg' in sys.argv
released=None
if release:
    assert peer=='C1607'
    previous=json.loads((r/'cpu-bulk-to-c1607.json').read_text())
    assert previous['parent_sha256']==doc['sha256']
    row=next(x for x in previous['land_barriers'] if len(x['objects'])==1 and x['objects'][0][1]=='WIFI_VBAT_PG')
    released=row['objects'][0][0];old_seg=next(o for o in b.GetTracks() if uid(o)==released)
    b.Remove(old_seg)

parts=[comp for comp in b.GetFootprints() if uid(comp)!=uid(f)]
all_objects=[*b.GetTracks(),*(pad for comp in parts for pad in comp.Pads())]
rails=set();returns=set()
for obj in all_objects:
    if uid(obj) in rail_id and obj.IsOnLayer(side):
        if isinstance(obj,p.PAD):
            if obj.GetParentFootprint().GetReference() not in ((peer,'C1604') if peer=='C1603' else (peer,)):continue
            at=xy(obj);rails.update((at[0]+i,at[1]+j) for i in (-200000,0,200000) for j in (-300000,0,300000) if obj.HitTest(v((at[0]+i,at[1]+j))))
        elif isinstance(obj,p.PCB_TRACK) and not isinstance(obj,p.PCB_VIA) and obj.GetWidth()>=600000:
            count=max(1,math.ceil(obj.GetLength()/250000));rails.update(tuple(round(a+(z-a)*n/count) for a,z in zip(obj.GetStart(),obj.GetEnd())) for n in range(count+1))
    if uid(obj) in gnd_id and isinstance(obj,p.PCB_VIA) and obj.GetDrillValue()>=300000:returns.add(xy(obj))
cent=(round(sum(x for x,y in rails)/len(rails)),round(sum(y for x,y in rails)/len(rails)))
region=[o for o in all_objects if inflated_box(o,8500000).Contains(v(cent))]
regions=[comp.GetCourtyard(side) for comp in parts if comp.GetLayer()==side and inflated_box(comp,8500000).Contains(v(cent))]
front=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in region if o.IsOnLayer(side)]
holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in region if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
zones=[z.Outline() for z in [*b.Zones(),*(zone for comp in parts for zone in comp.Zones())] if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(side)]
def clear(o):
    shape=o.GetEffectiveShape(side);box=inflated_box(o,350000)
    return not any(code!=o.GetNetCode() and box.Intersects(bounds) and shape.Collide(sh,202000) for code,sh,bounds in front) and not any(code!=o.GetNetCode() and shape.Collide(h,252000) for code,h in holes) and not any(shape.Collide(z,0) for z in zones)
def branch(q,peer,goals,limit):
    x,y=xy(q);opts=[]
    for a,z in sorted(goals,key=lambda pt:math.dist((x,y),pt)):
        if math.dist((x,y),(a,z))>limit:break
        dx=a-x;dy=z-y;d=min(abs(dx),abs(dy));ux=round(math.copysign(d,dx));uy=round(math.copysign(d,dy))
        for mid in (None,(x+ux,y+uy),(a-ux,z-uy)):
            points=[(x,y)]+([mid] if mid is not None else [])+[(a,z)]
            lines=[make(b,i,j,600000,q.GetNetCode(),side) for i,j in zip(points,points[1:]) if i!=j]
            length=sum(t.GetLength() for t in lines)
            if length>limit or not all(clear(t) and not t.GetEffectiveShape(side).Collide(peer.GetEffectiveShape(side),202000) for t in lines):continue
            opts.append((length,points));break
        if len(opts)>=3:break
    return opts
poses=set()
for pt in rails:
    xx,yy=(round(k/200000) for k in pt);poses.update(((xx+i)*200000,(yy+j)*200000) for i in range(-18,19) for j in range(-18,19))
stats=Counter();options=[];land_barriers=Counter();examples={}
for angle in (0,90,180,270):
    f.SetOrientationDegrees(angle)
    for pos in sorted(poses):
        if min(math.dist(pos,pt) for pt in balls)>=old_distance:continue
        stats['closer_to_load']+=1
        f.SetPosition(v(pos));cy=f.GetCourtyard(side)
        if any(cy.Collide(c,100000) for c in regions):continue
        stats['legal_courtyard']+=1
        if not all(clear(q) for q in f.Pads()):
            issues=set()
            for q in f.Pads():
                sh=q.GetEffectiveShape(side);bb=inflated_box(q,350000)
                for o in region:
                    if o.GetNetCode()==q.GetNetCode() or not bb.Intersects(o.GetBoundingBox()):continue
                    if (o.IsOnLayer(side) and sh.Collide(o.GetEffectiveShape(side),202000)) or ((isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x) and sh.Collide(o.GetEffectiveHoleShape(),252000)):
                        issues.add((uid(o),o.GetNetname(),o.GetClass(),o.GetParentFootprint().GetReference() if isinstance(o,p.PAD) else ''))
            key=tuple(sorted(issues))
            land_barriers[key]+=1
            if key not in examples:examples[key]=(pos,angle)
            continue
        stats['land_clearance']+=1
        # No via-in-pad is introduced for this ordinary bulk capacitor, including
        # a pre-existing GND via which would otherwise pass same-net copper checks.
        if any(q.GetEffectiveShape(side).Collide(o.GetEffectiveShape(side),52000) for q in f.Pads() for o in region if isinstance(o,p.PCB_VIA) and q.GetBoundingBox().Intersects(inflated_box(o,100000))):continue
        stats['clear_poses']+=1
        positive=branch(q1,q2,rails,2400000)
        if not positive:continue
        stats['rail_reachable']+=1
        negative=branch(q2,q1,returns,1500000)
        if negative:stats['return_reachable']+=1
        for lp,pp in positive:
            for ln,nn in negative:
                if lp+ln>3600000:continue
                p_lines=[make(b,a,z,600000,q1.GetNetCode(),side) for a,z in zip(pp,pp[1:]) if a!=z]
                n_lines=[make(b,a,z,600000,q2.GetNetCode(),side) for a,z in zip(nn,nn[1:]) if a!=z]
                if any(t.GetEffectiveShape(side).Collide(u.GetEffectiveShape(side),202000) for t in p_lines for u in n_lines):continue
                options.append((lp+ln,pos,angle,pp,nn))
folder=r/'runs'/('cpu-c1607-pg-window' if release else 'cpu-bulk-ground-barrel' if peer=='C1603' else 'cpu-bulk-to-'+peer.lower());folder.mkdir(exist_ok=True)
for fn in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/fn,folder/fn)
winner=None;attempts=[]
for _,pos,angle,pp,nn in sorted(options)[:14]:
    trial=p.LoadBoard(str(src))
    if release:trial.Remove(next(t for t in trial.GetTracks() if uid(t)==released))
    cap=trial.FindFootprintByReference('C1605');cap.SetOrientationDegrees(angle);cap.SetPosition(v(pos))
    for n,points in zip(('1','2'),(pp,nn)):
        for a,z in zip(points,points[1:]):
            if a!=z:trial.Add(make(trial,a,z,600000,cap.FindPadByNumber(n).GetNetCode(),side))
    out=folder/src.name;p.ZONE_FILLER(trial).Fill(trial.Zones());p.SaveBoard(str(out),trial)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    new=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));attempts.append(dict(pos=pos,new_drc=new))
    if new and (not release or any(e['type'] not in ('via_dangling','track_dangling') for e in new)):continue
    saved=p.LoadBoard(str(out));saved.BuildConnectivity();cap=saved.FindFootprintByReference('C1605')
    if any(uid(cap.FindPadByNumber(n)) not in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference(ref).FindPadByNumber(number))} for n,ref,number in [('1',peer,'1'),('2','U4','69')]) or screen(saved):continue
    winner=dict(board=str(out.relative_to(r)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),pos_nm=pos,angle=angle,positive_nm=pp,return_nm=nn,preservation=None if release else verify_preservation(p.LoadBoard(str(src)),saved),pending_signal_restore=released);break
(r/('cpu-c1607-pg-window.json' if release else 'cpu-bulk-ground-barrel.json' if peer=='C1603' else 'cpu-bulk-to-'+peer.lower()+'.json')).write_text(json.dumps(dict(parent_sha256=doc['sha256'],stats=stats,land_barriers=[dict(objects=k,count=land_barriers[k],example=examples[k]) for k in sorted(land_barriers,key=lambda k:(len(k),-land_barriers[k]))[:12]],solutions=len(options),attempts=attempts,candidate=winner,assembly_ready=False),indent=2)+'\n')
print(stats,len(options),bool(winner))
