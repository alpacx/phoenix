"""Fit the VDC RC filter and its ground return together beside the relocated RK809 divider."""
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pcbnew as p
from pcb_bounds import inflated_box
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel/runs'
secondary='--secondary-output' in sys.argv
src=root/('pmic-five-stage-addon-0' if secondary else 'pmic-five-stage-divider-0')
out=root/('pmic-five-stage-secondary-0' if secondary else 'pmic-five-stage-filter-0')
out.mkdir(exist_ok=True)
for f in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src/f,out/f)
j=json.loads((src/'output-legs.json').read_text())
fn='phy-joint.kicad_pcb'
assert hashlib.sha256((src/fn).read_bytes()).hexdigest()==j['board_sha256']
b=p.LoadBoard(str(src/fn));b.BuildConnectivity()
pad=lambda r,n:b.FindFootprintByReference(r).FindPadByNumber(n)
refname='C445' if secondary else 'C410'
cap=b.FindFootprintByReference(refname);orig=tuple(cap.GetPosition());angle=cap.GetOrientationDegrees();side=p.B_Cu
assert cap.GetLayer()==side
via_or_pad=lambda o:isinstance(o,(p.PCB_VIA,p.PAD))
signal,ground=[pad(refname,n) for n in ('1','2')]
ref=pad('C435','1') if secondary else pad('R411','1');ep=pad('U4','69')
newcenter=ref.GetPosition()
orphaned=[]
if secondary:
    for land in (signal,ground):
        members=b.GetConnectivity().GetConnectedItems(land)
        assert not any(isinstance(i,p.PAD) and i.m_Uuid.AsString()!=land.m_Uuid.AsString() for i in members)
        for i in members:
            if isinstance(i,p.PCB_TRACK):
                orphaned.append(i.m_Uuid.AsString())
    displaced=[t for t in b.GetTracks() if t.m_Uuid.AsString() in orphaned]
    for t in displaced:b.Remove(t)
    b.BuildConnectivity()
items=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference()!=refname for q in f.Pads()] if inflated_box(o,8000000).Contains(newcenter)]
obs=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in items if o.IsOnLayer(side)]
holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in items if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
courts=[f.GetCourtyard(side) for f in b.GetFootprints() if f.GetLayer()==side and f.GetReference()!=refname and inflated_box(f,8000000).Contains(newcenter)]
areas=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
def clean(o):
    s=o.GetEffectiveShape(side);box=inflated_box(o,300000);code=o.GetNetCode()
    return not any(code!=c and box.Intersects(x) and s.Collide(y,202000) for c,y,x in obs) and not any(code!=c and s.Collide(h,250000) for c,h in holes) and not any(s.Collide(a,0) for a in areas)
def nodes(q):
    ids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(q)}|{q.m_Uuid.AsString()}
    pts=set()
    for o in items:
        if o.m_Uuid.AsString() in ids and o.IsOnLayer(side):
            if via_or_pad(o):pts.add(tuple(o.GetPosition()))
            else:pts.update((tuple(o.GetStart()),tuple(o.GetEnd())))
    return pts
targets=[nodes(ref),nodes(ep)]
sw,gw=(400000,500000) if secondary else (200000,300000)
if secondary:
    targets[0]={tuple(ref.GetPosition())}
    ground_group={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(ep)}
    targets[1]={tuple(o.GetPosition()) for o in items if o.m_Uuid.AsString() in ground_group and (isinstance(o,p.PCB_VIA) and o.GetDrillValue()>=200000 or isinstance(o,p.PAD) and o.GetDrillSize().x>=200000)}

def route(land,avoid,dests,width):
    a=land.GetPosition()
    for xy in sorted(dests,key=lambda x:math.dist(tuple(a),x)):
        if math.dist(tuple(a),xy)>2500000:break
        z=p.VECTOR2I(*xy);v=z-a;n=min(abs(v.x),abs(v.y));d=p.VECTOR2I(int(math.copysign(n,v.x)),int(math.copysign(n,v.y)))
        for corner in (a+d,z-d):
            pieces=[]
            for u,w in [(a,corner),(corner,z)]:
                if u==w:continue
                t=p.PCB_TRACK(b);t.SetStart(u);t.SetEnd(w);t.SetWidth(width);t.SetLayer(side);t.SetNetCode(land.GetNetCode())
                if not clean(t) or t.GetEffectiveShape(side).Collide(avoid.GetEffectiveShape(side),202000):break
                pieces.append(t)
            else:
                if pieces:return pieces
    return []
options=[];counts=Counter()
for ang in (0,90,180,270):
    cap.SetOrientationDegrees(ang)
    for x in (range(645,728) if secondary else range(586,672)):
        for y in (range(81,157) if secondary else range(54,111)):
            xy=(x*100000,y*100000);cap.SetPosition(p.VECTOR2I(*xy));c=cap.GetCourtyard(side)
            if any(c.Collide(q,100000) for q in courts) or any(c.Collide(h,50000) for _,h in holes):continue
            if not clean(signal) or not clean(ground):continue
            counts['placement']+=1
            s=route(signal,ground,targets[0],sw)
            if not s:continue
            counts['sense']+=1
            g=route(ground,signal,targets[1],gw)
            if not g or any(t.GetEffectiveShape(side).Collide(k.GetEffectiveShape(side),202000) for t in s for k in g):continue
            counts['combined']+=1
            options.append((sum(t.GetLength() for t in s+g),xy,ang))
def check():
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out/fn),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(out/fn)],capture_output=True,check=True)
    return introduced(json.loads((src/'drc.json').read_text()),json.loads((out/'drc.json').read_text()))
selected=None;rejected=[]
for cost,xy,ang in sorted(options):
    cap.SetPosition(p.VECTOR2I(*xy));cap.SetOrientationDegrees(ang)
    if screen(b):continue
    s=route(signal,ground,targets[0],sw);g=route(ground,signal,targets[1],gw)
    for t in s+g:b.Add(t)
    delta=check()
    if not delta:
        selected=dict(xy_nm=xy,angle=ang,sense_mm=sum(t.GetLength() for t in s)/1e6,ground_mm=sum(t.GetLength() for t in g)/1e6);break
    rejected.append(dict(xy_nm=xy,delta=delta))
    for t in s+g:b.Remove(t)
if not selected:
    cap.SetPosition(p.VECTOR2I(*orig));cap.SetOrientationDegrees(angle)
    if secondary:
        for t in displaced:b.Add(t)
        orphaned=[]
    assert not check()
b=p.LoadBoard(str(out/fn));b.BuildConnectivity()
if selected:
    for l,r in [((refname,'1'),('C435','1') if secondary else ('R410','2')),((refname,'2'),('U4','69'))]:
        assert pad(*r).m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pad(*l))}
j['board_sha256']=hashlib.sha256((out/fn).read_bytes()).hexdigest()
key='secondary_output_fit' if secondary else 'filter_fit';j[key]=dict(selected=selected,counts=counts,rejected=rejected,removed_orphan_tracks=orphaned)
(out/'output-legs.json').write_text(json.dumps(j,indent=2)+'\n');print(j[key],flush=True);os._exit(0)
