"""Place the FB3 divider together on the rear, tied to its actual package escape and a nearby return."""
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pcbnew as pcb
import native_front_splice as bend
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
launch=json.loads((root/'adopted-buck3-feedback-relief.json').read_text())['candidate']
src=root/launch['board']
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
assert digest(src)==launch['sha256']
b=pcb.LoadBoard(str(src));prior=pcb.LoadBoard(str(src));b.BuildConnectivity()
refnames=('R431','R432')
small_upper='--small-upper' in sys.argv
if small_upper:
    old=b.FindFootprintByReference('R431')
    other=b.FindFootprintByReference('R1601')
    replacement=pcb.PCB_IO_KICAD_SEXPR().FootprintLoad(str(root.parents[1]/'kicad/Phoenix_Passives.pretty'),'R_0402_1005Metric')
    replacement.SetFPID(other.GetFPID());replacement.SetReference(old.GetReference());replacement.SetValue(old.GetValue());replacement.SetPath(old.GetPath());replacement.SetUuid(old.m_Uuid)
    replacement.SetPosition(old.GetPosition());replacement.SetOrientation(old.GetOrientation())
    for pad0 in replacement.Pads():
        previous=old.FindPadByNumber(pad0.GetNumber());pad0.SetUuid(previous.m_Uuid);pad0.SetNetCode(previous.GetNetCode())
    b.Remove(old);b.Add(replacement)
    for pad0 in replacement.Pads():pad0.SetNet(b.FindNet(old.FindPadByNumber(pad0.GetNumber()).GetNetname()))
parts=[b.FindFootprintByReference(n) for n in refnames]
front='--front-divider' in sys.argv
side=pcb.F_Cu if front else pcb.B_Cu;via=tuple(launch['via_nm']);origin=pcb.VECTOR2I(*via);uid=lambda o:o.m_Uuid.AsString()
for f in parts:
    if f.GetLayer()!=side:f.Flip(f.GetPosition(),False)
groups=[(parts[0].FindPadByNumber('2'),parts[0].FindPadByNumber('1')),(parts[1].FindPadByNumber('1'),parts[1].FindPadByNumber('2'))]
assert groups[0][0].GetNetname()==groups[1][0].GetNetname()=='DDR_FB'
assert groups[0][1].GetNetname()=='+1V1_LPDDR4' and groups[1][1].GetNetname()=='GND'
objects=[o for o in [*list(b.GetTracks()),*(q for f in b.GetFootprints() if f.GetReference() not in refnames for q in f.Pads())] if inflated_box(o,6500000).Contains(origin)]
geom=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in objects if o.IsOnLayer(side)]
holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in objects if isinstance(o,pcb.PCB_VIA) or isinstance(o,pcb.PAD) and o.GetDrillSize().x]
courts=[f.GetCourtyard(side) for f in b.GetFootprints() if f.GetReference() not in refnames and f.GetLayer()==side and inflated_box(f,6500000).Contains(origin)]
courts += [o.GetEffectiveShape(side) for o in objects if isinstance(o,pcb.PAD) and o.GetAttribute() in (pcb.PAD_ATTRIB_PTH,pcb.PAD_ATTRIB_NPTH)]
areas=[a.Outline() for a in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if a.GetIsRuleArea() and a.IsOnLayer(side) and a.GetDoNotAllowTracks()]
switch_nets={b.FindFootprintByReference('L40'+str(i)).FindPadByNumber('1').GetNetname() for i in range(1,6)}
noise=[t.GetEffectiveShape(pcb.F_Cu) for t in objects if t.GetNetname() in switch_nets and t.IsOnLayer(pcb.F_Cu)]
noise+=[b.FindFootprintByReference('L40'+str(i)).GetCourtyard(pcb.F_Cu) for i in range(1,6)]
oldground={uid(o) for o in prior.GetConnectivity().GetConnectedItems(prior.FindFootprintByReference('U4').FindPadByNumber('69'))}
groundpoints=set()
for o in objects:
    if not o.IsOnLayer(side) or uid(o) not in oldground:continue
    if isinstance(o,(pcb.PAD,pcb.PCB_VIA)):groundpoints.add(tuple(o.GetPosition()))
    else:groundpoints.update((tuple(o.GetStart()),tuple(o.GetEnd())))
def clear(item):
    code=item.GetNetCode();sh=item.GetEffectiveShape(side);bb=inflated_box(item,400000)
    if any(code!=n and bb.Intersects(box) and sh.Collide(s,202000) for n,s,box in geom):return False
    if any(code!=n and sh.Collide(h,252000) for n,h in holes):return False
    if any(sh.Collide(area,0) for area in areas):return False
    return code!=groups[0][0].GetNetCode() or not any(sh.Collide(sh_noise,350000) for sh_noise in noise)
def line(a,z,w,net):
    if a==z:return []
    dx=z[0]-a[0];dy=z[1]-a[1];m=min(abs(dx),abs(dy));mx=int(math.copysign(m,dx));my=int(math.copysign(m,dy))
    for mid in ((a[0]+mx,a[1]+my),(z[0]-mx,z[1]-my)):
        ts=[make(b,i,j,w,net,side) for i,j in zip((a,mid),(mid,z)) if i!=j]
        if all(clear(t) for t in ts):return ts
    return None
legal_lands=[]
pose_counts=[]
poses=[]
bend.side=side
for idx,f in enumerate(parts):
    park=f.GetPosition();park_angle=f.GetOrientationDegrees()
    sig,outer=groups[idx];options=[];counts=dict(court=0,pads=0,access=0)
    step=100000 if small_upper else 200000
    ext=34 if small_upper else 17
    for angle,ix,iy in itertools.product((0,90,180,270),range(-ext,ext+1),range(-ext,ext+1)):
        f.SetOrientationDegrees(angle);f.SetPosition(origin+pcb.VECTOR2I(ix*step,iy*step))
        if any(f.GetCourtyard(side).Collide(c,50000) for c in courts):continue
        counts['court']+=1
        if not all(clear(q) for q in f.Pads()):continue
        counts['pads']+=1
        legal_lands.append(dict(part=f.GetReference(),centre_nm=tuple(f.GetPosition()),angle=angle,fb_nm=tuple(sig.GetPosition()),output_or_ground_nm=tuple(outer.GetPosition())))
        at=tuple(sig.GetPosition());outside=tuple(outer.GetPosition())
        branch=line(at,via,200000,sig.GetNetCode())
        if branch is None and math.dist(at,via)<=2800000:
            route,info=bend.recover(b,[(at,via,200000,sig.GetNetCode())],sig.GetNetname(),None,True,True,False,202000)
            if route and info['length_mm']<=2.8:
                branch=[make(b,x,y,200000,sig.GetNetCode(),side) for x,y in zip(route,route[1:])]
                if not all(clear(t) for t in branch):branch=None
        if branch is None or any(t.GetEffectiveShape(side).Collide(outer.GetEffectiveShape(side),202000) for t in branch):continue
        counts['access']+=1
        length=sum(t.GetLength() for t in branch)/1e6
        if length>2.8:continue
        ground=[]
        if idx==1:
            for point in sorted(groundpoints,key=lambda x:math.dist(x,outside)):
                if math.dist(point,outside)>1600000:break
                ground=line(outside,point,300000,outer.GetNetCode())
                if ground and not any(t.GetEffectiveShape(side).Collide(sh,202000) for t in ground for sh in [sig.GetEffectiveShape(side),*(j.GetEffectiveShape(side) for j in branch)]):break
                ground=[]
            if not ground:continue
        options.append((length,angle,tuple(f.GetPosition()),branch,ground))
    poses.append(options);pose_counts.append(counts);f.SetOrientationDegrees(park_angle);f.SetPosition(park)
candidates=[]
for outer,lower in itertools.product(*poses):
    for f,pose in zip(parts,(outer,lower)):
        f.SetOrientationDegrees(pose[1]);f.SetPosition(pcb.VECTOR2I(*pose[2]))
    if parts[0].GetCourtyard(side).Collide(parts[1].GetCourtyard(side),50000):continue
    signal=outer[3]+lower[3];gnd=lower[4]
    if any(t.GetEffectiveShape(side).Collide(sh,202000) for t in signal for sh in [*(x.GetEffectiveShape(side) for x in gnd),*(g[1].GetEffectiveShape(side) for g in groups)]):continue
    if any(t.GetEffectiveShape(side).Collide(groups[0][1].GetEffectiveShape(side),202000) or t.GetEffectiveShape(side).Collide(groups[0][0].GetEffectiveShape(side),202000) for t in gnd):continue
    candidates.append((outer[0]+lower[0]+sum(t.GetLength() for t in gnd)/1e6,outer,lower))
winner=None;held=[];owners=[]
for _,upper,lower in sorted(candidates,key=lambda s:s[0]):
    for f,pose in zip(parts,(upper,lower)):
        f.SetOrientationDegrees(pose[1]);f.SetPosition(pcb.VECTOR2I(*pose[2]))
    if screen(b):continue
    lines=[];seen=set()
    for t in [*upper[3],*lower[3],*lower[4]]:
        key=(t.GetNetCode(),*sorted((tuple(t.GetStart()),tuple(t.GetEnd()))))
        if key in seen:continue
        seen.add(key);lines.append(t);b.Add(t)
    folder=root/('runs/buck3-feedback-small-upper-front' if small_upper and front else 'runs/buck3-feedback-small-upper' if small_upper else 'runs/buck3-feedback-front-divider' if front else 'runs/buck3-feedback-divider-at-pin');folder.mkdir(exist_ok=True)
    for cfg in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/cfg,folder/cfg)
    out=folder/src.name;pcb.ZONE_FILLER(b).Fill(b.Zones());pcb.SaveBoard(str(out),b)
    def drc():
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
        return introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    delta=drc();retired=set()
    saved=pcb.LoadBoard(str(out));owners.append(saved)
    old_pad=prior.FindFootprintByReference('R432').FindPadByNumber('2')
    for step in range(4):
        if not delta or any(issue['type'] not in ('via_dangling','track_dangling') for issue in delta):break
        suspects={u for issue in delta for u in issue['items']}
        copper={uid(t):t for t in saved.GetTracks()};old_items={uid(t) for t in prior.GetTracks()}
        if any(u not in old_items or u not in copper or copper[u].GetNetname()!='GND' or (copper[u].GetStart()-old_pad.GetPosition()).EuclideanNorm()>2800000 for u in suspects):break
        for u in suspects:saved.Remove(copper[u]);owners.append(copper[u])
        retired.update(suspects);pcb.ZONE_FILLER(saved).Fill(saved.Zones());pcb.SaveBoard(str(out),saved);delta=drc();saved=pcb.LoadBoard(str(out));owners.append(saved)
    if not delta:
        guard=verify_preservation(prior,saved,replaced_copper=retired)
        joint={uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('U4').FindPadByNumber('27'))}
        assert all(uid(saved.FindFootprintByReference(r).FindPadByNumber(n)) in joint for r,n in [('R431','2'),('R432','1')])
        assert uid(saved.FindFootprintByReference('R432').FindPadByNumber('2')) in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('U4').FindPadByNumber('69'))}
        winner=dict(board=str(out.relative_to(root)),sha256=digest(out),upper_length_mm=upper[0],lower_length_mm=lower[0],ground_length_mm=sum(t.GetLength() for t in lower[4])/1e6,upper_xy=upper[2],lower_xy=lower[2],retired=list(retired),preservation=guard)
        break
    held.append(delta)
    for t in lines:b.Remove(t)
    if len(held)>=12:break
(root/('buck3-feedback-small-upper-front.json' if small_upper and front else 'buck3-feedback-small-upper.json' if small_upper else 'buck3-feedback-front-divider.json' if front else 'buck3-feedback-divider-at-pin.json')).write_text(json.dumps(dict(parent_sha256=launch['sha256'],upper_0402_coupon=small_upper,pose_counts=pose_counts,legal_lands=legal_lands,upper_sites=len(poses[0]),grounded_lower_sites=len(poses[1]),feasible_pairs=len(candidates),candidate=winner,held=held,assembly_ready=False),indent=2)+'\n')
print(len(poses[0]),len(poses[1]),len(candidates),bool(winner),flush=True);os._exit(0)
