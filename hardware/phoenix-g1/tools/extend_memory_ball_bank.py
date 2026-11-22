"""Grow the fixed-width 1.1-V package bank onto nearby memory balls using existing copper."""
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'layout-memory-ab4-bank.json').read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));src_board=p.LoadBoard(str(src))
anchor=b.FindFootprintByReference('U2').FindPadByNumber('AB4')
code=anchor.GetNetCode();layer=p.F_Cu
uid=lambda o:o.m_Uuid.AsString()
def group():
    b.BuildConnectivity()
    return {uid(o) for o in b.GetConnectivity().GetConnectedItems(anchor)}
objects=[*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())]
rules=[z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks()]
def search(pad,connected):
    at=tuple(pad.GetPosition())
    nearby=[o for o in objects if inflated_box(o,3100000).Contains(pad.GetPosition())]
    surfaces=[(o.GetEffectiveShape(layer),o.GetBoundingBox()) for o in nearby if o.GetNetCode()!=code and o.IsOnLayer(layer)]
    holes=[o.GetEffectiveHoleShape() for o in nearby if o.GetNetCode()!=code and (isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x)]
    targets=set()
    for o in nearby:
        if uid(o) not in connected or not o.IsOnLayer(layer):continue
        if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD):targets.add(tuple(o.GetPosition()));continue
        if o.GetWidth()<500000:continue
        count=max(1,math.ceil(o.GetLength()/100000))
        targets.update(tuple(round(x+(y-x)*k/count) for x,y in zip(o.GetStart(),o.GetEnd())) for k in range(count+1))
    v=lambda pt:p.VECTOR2I(*pt)
    wire=make(b,at,at,500000,code,layer)
    def clear(a,z):
        wire.SetStart(v(a));wire.SetEnd(v(z));shape=wire.GetEffectiveShape(layer)
        bounds=inflated_box(wire,350000)
        return not any(bounds.Intersects(bb) and shape.Collide(sh,202000) for sh,bb in surfaces) and not any(shape.Collide(h,252000) for h in holes) and not any(shape.Collide(poly,0) for poly in rules)
    starts=[(at[0]+dx,at[1]+dy) for dx in (-100000,-50000,0,50000,100000) for dy in (-100000,-50000,0,50000,100000) if pad.HitTest(v((at[0]+dx,at[1]+dy)))]
    rays=sorted((math.dist(a,z),a,z) for z in targets for a in starts if math.dist(a,z)<=2400000)
    for distance,a,z in rays:
        if clear(a,z):return [a,z]
        dx,dy=z[0]-a[0],z[1]-a[1]
        diag=min(abs(dx),abs(dy));q=(int(math.copysign(diag,dx)),int(math.copysign(diag,dy)))
        for m in ((a[0]+q[0],a[1]+q[1]),(z[0]-q[0],z[1]-q[1])):
            if m not in (a,z) and math.dist(a,m)+math.dist(m,z)<=2400000 and clear(a,m) and clear(m,z):return [a,m,z]
    return None
added=[]
for iteration in range(10):
    new=0
    ids=group()
    pending=[q for q in b.FindFootprintByReference('U2').Pads() if q.GetNetCode()==code and uid(q) not in ids]
    for pad in sorted(pending,key=lambda x:math.dist(tuple(x.GetPosition()),tuple(anchor.GetPosition()))):
        if uid(pad) in ids:continue
        path=search(pad,ids)
        if not path:continue
        for a,z in zip(path,path[1:]):
            tr=make(b,a,z,500000,code,layer);b.Add(tr);objects.append(tr)
        ids=group()
        assert uid(pad) in ids
        added.append(dict(pin=pad.GetNumber(),path_nm=path));new+=1
    if not new:break
result=dict(parent_sha256=cp['sha256'],width_mm=.5,added=added)
if added:
    folder=root/'runs/memory-surface-bank';folder.mkdir(exist_ok=True)
    for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
    out=folder/src.name
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    dr=lambda folder:json.loads((folder/'drc.json').read_text())
    result.update(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),new_drc=introduced(dr(src.parent),dr(folder)))
    check=p.LoadBoard(str(out));result['preservation']=verify_preservation(src_board,check);result['mounts']=screen(check)
    ids={uid(o) for o in check.GetConnectivity().GetConnectedItems(check.FindFootprintByReference('C1666').FindPadByNumber('1'))}
    assert all(uid(check.FindFootprintByReference('U2').FindPadByNumber(item['pin'])) in ids for item in added)
(root/'memory-surface-bank.json').write_text(json.dumps(result,indent=2)+'\n')
print(len(added),result.get('new_drc'),flush=True)
