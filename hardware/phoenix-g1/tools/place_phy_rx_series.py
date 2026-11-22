"""Screen source-side RGMII receive series resistors at the external toe of the PHY land."""
from functools import lru_cache
import heapq
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
tx='--soc-transmit-bank' in sys.argv
dead_stub='--replace-dead-launch' in sys.argv
fine='--adjacent-lanes' in sys.argv or dead_stub or tx
base=json.loads((root/('layout-phy-source-series.json' if fine else 'layout-hanrun-hole-stagger.json')).read_text());src=root/base['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
current=src
results=[]
for ref in (('R501','R502','R504','R506','R503','R505') if tx else ('R510','R512') if dead_stub else ('R509','R507','R511') if fine else ('R509','R508','R507','R511')):
    b=p.LoadBoard(str(current));b.BuildConnectivity()
    f=b.FindFootprintByReference(ref);u=b.FindFootprintByReference('U1' if tx else 'U5')
    signal_pad='1' if tx else '2'
    dest=f.FindPadByNumber(signal_pad)
    obsolete=set()
    if dead_stub:
        attached=list(b.GetConnectivity().GetConnectedItems(dest))
        other_pads=[k for k in attached if isinstance(k,p.PAD) and k.m_Uuid.AsString()!=dest.m_Uuid.AsString()]
        if other_pads:
            results.append(dict(ref=ref,adopted=False,preserved_active_taps=[k.GetParentFootprint().GetReference()+'.'+k.GetNumber() for k in other_pads]))
            continue
        obsolete={k.m_Uuid.AsString() for k in attached if isinstance(k,p.PCB_TRACK)}
        assert obsolete and not b.GetConnectivity().GetConnectedTracks(f.FindPadByNumber('1'))
        for old in b.GetTracks():
            if old.m_Uuid.AsString() in obsolete:b.Remove(old)
    else:
        assert all(not b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads())
    pin=next(q for q in u.Pads() if q.GetNetCode()==dest.GetNetCode());code=pin.GetNetCode()
    pos=pin.GetPosition()
    if tx:
        assert pos.x<u.GetPosition().x and pin.GetSize().x==250000
    else:assert pos.y<u.GetPosition().y and pin.GetOrientationDegrees()==0 and pin.GetSize().y==600000
    if f.IsFlipped():f.Flip(f.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
    side=p.F_Cu;two=f.FindPadByNumber(signal_pad);one=f.FindPadByNumber('2' if tx else '1')
    toe=pos+(p.VECTOR2I(-100000,0) if tx else p.VECTOR2I(0,-349000))
    objects=[k for k in list(b.GetTracks())+[q for other in b.GetFootprints() if other.GetReference()!=ref for q in other.Pads()] if k.IsOnLayer(side) and inflated_box(k,4000000).Contains(pos)]
    obs=[(k,k.GetNetCode(),k.GetEffectiveShape(side),k.GetBoundingBox()) for k in objects]
    holes=[(k.GetNetCode(),k.GetEffectiveHoleShape()) for k in objects if isinstance(k,p.PCB_VIA)]
    courts=[other.GetCourtyard(side).BBox() for other in b.GetFootprints() if other.GetReference()!=ref and other.GetLayer()==side and inflated_box(other,4000000).Contains(pos)]
    copper=[zone.GetFilledPolysList(p.In1_Cu) for zone in b.Zones() if zone.IsOnLayer(p.In1_Cu) and zone.GetNetname()=='GND' and zone.HasFilledPolysForLayer(p.In1_Cu)]
    def clear(obj):
        bb=inflated_box(obj,250000);shape=obj.GetEffectiveShape(side)
        return not any(n!=obj.GetNetCode() and bb.Intersects(box) and shape.Collide(s,202000) for _,n,s,box in obs) and not any(n!=obj.GetNetCode() and shape.Collide(h,250000) for n,h in holes)
    counts=dict(courtyard_clear=0,pads_clear=0,path_clear=0,quiet=0)
    def path(z,mode):
        delta=z-toe;dd=min(abs(delta.x),abs(delta.y))
        diag=p.VECTOR2I(int(math.copysign(dd,delta.x)),int(math.copysign(dd,delta.y)))
        corner=(toe+diag,z-diag)[mode]
        parts=[]
        for start,end in ((toe,corner),(corner,z)):
            if start==end:continue
            t=p.PCB_TRACK(b);t.SetWidth(200000);t.SetLayer(side);t.SetNetCode(code);t.SetStart(start);t.SetEnd(end)
            if not clear(t) or t.GetEffectiveShape(side).Collide(one.GetEffectiveShape(side),202000):return []
            counts['path_clear']+=1
            if any(t.GetEffectiveShape(side).Collide(o,1000000) for k,n,o,bb in obs if k.GetNetname().startswith(('PMIC_SW','CPU_SW','PHY_REG_OUT'))):return []
            counts['quiet']+=1
            dx=end.x-start.x;dy=end.y-start.y;length=math.hypot(dx,dy);steps=max(1,math.ceil(length/50000))
            for i in range(steps+1):
                for off in (-110000,0,110000):
                    pt=p.VECTOR2I(round(start.x+dx*i/steps-off*dy/length),round(start.y+dy*i/steps+off*dx/length))
                    if not any(poly.Contains(pt) for poly in copper):return []
            parts.append(t)
        return parts
    # Search bent traces when the legal component pose has no line-of-sight from the toe.
    def bent(endpad):
        start=tuple(toe);end=tuple(endpad.GetPosition());step=50000
        st=tuple(round(v/step)*step for v in start);target=tuple(round(v/step)*step for v in end)
        trace=p.PCB_TRACK(b);trace.SetWidth(200000);trace.SetLayer(side);trace.SetNetCode(code)
        @lru_cache(None)
        def usable(a,z):
            trace.SetStart(p.VECTOR2I(*a));trace.SetEnd(p.VECTOR2I(*z));shape=trace.GetEffectiveShape(side)
            if not clear(trace) or shape.Collide(one.GetEffectiveShape(side),202000):return False
            if any(shape.Collide(o,1000000) for k,n,o,bb in obs if k.GetNetname().startswith(('PMIC_SW','CPU_SW','PHY_REG_OUT'))):return False
            for dx,dy in ((0,0),(110000,0),(-110000,0),(0,110000),(0,-110000)):
                if not any(poly.Contains(p.VECTOR2I(z[0]+dx,z[1]+dy)) for poly in copper):return False
            return True
        if not usable(start,st) or not usable(target,end):return []
        dist={st:0};prev={};queue=[(math.dist(st,target),0,st)]
        while queue:
            _,cost,pt=heapq.heappop(queue)
            if cost!=dist[pt]:continue
            if pt==target:break
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
                v=(pt[0]+step*dx,pt[1]+step*dy);nd=cost+step*math.hypot(dx,dy);h=math.dist(v,target)
                if nd+h>3200000 or nd>=dist.get(v,math.inf) or not usable(pt,v):continue
                dist[v]=nd;prev[v]=pt;heapq.heappush(queue,(nd+h,nd,v))
        if target not in dist:return []
        pts=[target]
        while pts[-1]!=st:pts.append(prev[pts[-1]])
        pts.reverse();pts=[start]+pts+[end];tracks=[]
        for a,z in zip(pts,pts[1:]):
            if a==z:continue
            if tracks:
                prior=tuple(tracks[-1].GetStart());d=(a[0]-prior[0],a[1]-prior[1]);e=(z[0]-a[0],z[1]-a[1])
                if d[0]*e[1]==d[1]*e[0] and d[0]*e[0]+d[1]*e[1]>0:
                    tracks[-1].SetEnd(p.VECTOR2I(*z));continue
            item=p.PCB_TRACK(b);item.SetWidth(200000);item.SetLayer(side);item.SetNetCode(code);item.SetStart(p.VECTOR2I(*a));item.SetEnd(p.VECTOR2I(*z));tracks.append(item)
        return tracks
    options=[]
    for angle in (0,90,180,270):
        f.SetOrientationDegrees(angle)
        period=100000 if fine else 200000
        for x in (range(-38,39) if fine else range(-15,16)):
            for y in (range(7,40) if fine else range(5,18)):
                position=pos+(p.VECTOR2I(-y*period,x*period) if tx else p.VECTOR2I(x*period,-y*period))
                f.SetPosition(position)
                if any(f.GetCourtyard(side).BBox().Intersects(c) for c in courts):continue
                counts['courtyard_clear']+=1
                if not clear(one) or not clear(two):continue
                counts['pads_clear']+=1
                for mode in (0,1,2):
                    route=bent(two) if mode==2 else path(two.GetPosition(),mode)
                    if route and sum(t.GetLength() for t in route)<=3200000:options.append((sum(t.GetLength() for t in route),angle,tuple(position),mode))
    row=dict(ref=ref,net=pin.GetNetname(),geometric_options=len(options),counts=counts,adopted=False);results.append(row)
    for length,angle,xy,mode in sorted(options)[:6]:
        f.SetPosition(p.VECTOR2I(*xy));f.SetOrientationDegrees(angle)
        if screen(b):continue
        tracks=bent(two) if mode==2 else path(two.GetPosition(),mode)
        assert tracks
        for t in tracks:b.Add(t)
        folder=root/'runs'/(('soc-tx-' if tx else 'phy-dead-' if dead_stub else 'phy-adjacent-' if fine else 'phy-source-')+ref);folder.mkdir(exist_ok=True)
        for filename in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(current.parent/filename,folder/filename)
        out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
        delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
        if not delta:
            saved=p.LoadBoard(str(out));saved.BuildConnectivity();verify_preservation(p.LoadBoard(str(current)),saved,replaced_copper=obsolete)
            a=saved.FindFootprintByReference(ref).FindPadByNumber(signal_pad);z=saved.FindFootprintByReference('U1' if tx else 'U5').FindPadByNumber(pin.GetNumber())
            assert z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(a)}
            current=out;row.update(adopted=True,replaced_ids=sorted(obsolete),pair=[ref+'.'+signal_pad,u.GetReference()+'.'+pin.GetNumber()],length_mm=length/1e6,xy_nm=xy,angle=angle);break
        for t in tracks:b.Remove(t)
(root/('soc-tx-series.json' if tx else 'phy-dead-series.json' if dead_stub else 'phy-adjacent-series.json' if fine else 'phy-source-series.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),records=results,assembly_ready=False),indent=2)+'\n')
print(results,flush=True);os._exit(0)
