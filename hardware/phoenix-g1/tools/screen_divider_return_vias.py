"""Check legal through-hole launches in the VDC coupon, including each layer's copper."""
from pathlib import Path
import heapq
import hashlib
import json
import math
import os
import itertools
import sys
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
folder=root/'runs/vdc-placement-0';src=folder/'restored.kicad_pcb';b=p.LoadBoard(str(src))
pwron='--pwron' in sys.argv
control='--pmic-control' in sys.argv
if pwron or control:
    meta=json.loads((root/('layout-pmic-pwron-filter.json' if control else 'layout-soc-tx-series.json')).read_text());src=root/meta['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256'];b=p.LoadBoard(str(src))
wireless='--ap-xtal' in sys.argv
coexist='--coexist-sense' in sys.argv
interior='--sense-inner' in sys.argv or coexist
rotated='--rotated-filter' in sys.argv or interior
if rotated:
    folder=root/('runs/pmic-five-stage-feedback-0' if coexist else 'runs/pmic-five-stage-sense-0' if interior else 'runs/pmic-five-stage-filter-0');src=folder/'phy-joint.kicad_pcb'
    assert hashlib.sha256(src.read_bytes()).hexdigest()==json.loads((folder/'output-legs.json').read_text())['board_sha256']
    b=p.LoadBoard(str(src))
if wireless:
    meta=json.loads((root/'layout-pmic-pwron-filter.json').read_text());src=root/meta['board']
    assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
    b=p.LoadBoard(str(src));folder=root/'runs/wifi-crystal-transfer';folder.mkdir(exist_ok=True)
power_key='--rotated-power-key' in sys.argv
feedback3='--adopted-buck3-feedback' in sys.argv
adopted_service='--adopted-pmic-services' in sys.argv or feedback3
extent='--measure-peer-channel' in sys.argv or power_key or adopted_service
cleared='--after-c422' in sys.argv
after_sda='--after-left-sda' in sys.argv or extent or cleared
after_scl='--after-rotated-scl' in sys.argv or after_sda
long_controls='--long-control-exit' in sys.argv or after_scl
retry_controls='--rotated-control-repair' in sys.argv or long_controls
if retry_controls:
    meta=json.loads((root/('rotated-left-sda-complete.json' if after_sda else 'rotated-pmic-scl-complete.json' if after_scl else 'rotated-pmic-cap-ground-pivots.json')).read_text());src=root/meta['board']
    assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
    b=p.LoadBoard(str(src))
if adopted_service:
    meta=json.loads((root/'layout-usb-direction-complete.json').read_text());src=root/meta['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256'];b=p.LoadBoard(str(src))
if power_key:
    meta=json.loads((root/'rotated-bypass-source-mixed.json').read_text());src=root/meta['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256'];b=p.LoadBoard(str(src))
if cleared:
    meta=json.loads((root/'rotated-scl-cap-release.json').read_text())['candidate'];src=root/meta['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256'];b=p.LoadBoard(str(src))
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
allitems=list(b.GetTracks())+[pad for f in b.GetFootprints() for pad in f.Pads()]
zones=list(b.Zones())+[q for f in b.GetFootprints() for q in f.Zones()]
fields=[( 'U4.59 sense', '+1V8_SYS',p.F_Cu,(60300000,4900000),200000),('C481 bypass GND','GND',p.B_Cu,(59520000,4000000),300000),('R410 divider supply','+3V3_SYS',p.B_Cu,tuple(b.FindFootprintByReference('R410').FindPadByNumber('1').GetPosition()),200000)]
if pwron:
    fields=[('PWRON outer toe','PMIC_PWRON_N',p.F_Cu,(62800000,5150000),200000),('PWRON corner toe','PMIC_PWRON_N',p.F_Cu,(62900000,5240000),200000),('PWRON side toe','PMIC_PWRON_N',p.F_Cu,(62910000,5590000),200000)]
if control:
    fields=[]
    for n,offsets in [('44',[(440000,0),(350000,100000),(350000,-100000)]),('46',[(440000,0),(350000,100000),(350000,-100000)]),('48',[(440000,0),(350000,100000),(350000,-100000)]),('7',[(-440000,0),(-350000,100000),(-350000,-100000)]),('67',[(0,-440000),(100000,-350000),(-100000,-350000)]),('49',[(440000,0),(350000,100000),(350000,-100000)])]:
        q=b.FindFootprintByReference('U4').FindPadByNumber(n)
        for dx,dy in offsets:
            toe=tuple(q.GetPosition()+p.VECTOR2I(dx,dy));fields.append((n,q.GetNetname(),p.F_Cu,toe,200000))
if rotated:
    fields=[]
    for n in ('61','59','52','2'):
        f=b.FindFootprintByReference('U4');q=f.FindPadByNumber(n);v=q.GetPosition()-f.GetPosition()
        nx,ny=(int(math.copysign(1,v.x)),0) if abs(v.x)>abs(v.y) else (0,int(math.copysign(1,v.y)))
        toe=tuple(q.GetPosition()+p.VECTOR2I(nx*440000,ny*440000))
        fields.append(('U4.'+n,q.GetNetname(),p.F_Cu,toe,200000))
    for ref,n,w in [('R411','2',300000),('R410','1',200000)]:
        q=b.FindFootprintByReference(ref).FindPadByNumber(n)
        fields.append((ref+'.'+n,q.GetNetname(),p.B_Cu,tuple(q.GetPosition()),w))
if interior:
    fields=[f for f in fields if f[0] in ('U4.61','U4.59')]
    for reference in ('C410.1','R410.2','R411.1','C435.1'):
        ref,n=reference.split('.');q=b.FindFootprintByReference(ref).FindPadByNumber(n)
        fields.append((reference,q.GetNetname(),p.B_Cu,tuple(q.GetPosition()),200000))
if coexist:
    fields=[f for f in fields if f[0] in ('R410.2','R411.1','C410.1')]
    q=b.FindFootprintByReference('U4').FindPadByNumber('61');pos=q.GetPosition()
    for suffix,dx,dy in [('outside',440000,0),('inside',-440000,0),('inside-offset',-370000,100000),('inside-lower',-370000,-100000)]:
        fields.append(('U4.61 '+suffix,q.GetNetname(),p.F_Cu,tuple(pos+p.VECTOR2I(dx,dy)),200000))
if wireless:
    fields=[]
    for n in ('10','11'):
        q=b.FindFootprintByReference('U25').FindPadByNumber(n)
        for name,x in [('center',q.GetPosition().x),('inside',q.GetBoundingBox().GetLeft()+65000),('outside',q.GetBoundingBox().GetRight()-65000)]:
            fields.append(('U25.'+n+' '+name,q.GetNetname(),p.B_Cu,(x,q.GetPosition().y),200000))
if retry_controls:
    fields=[]
    fp=b.FindFootprintByReference('U4')
    for number in ('52','1','2'):
        if after_scl and number!=('52' if power_key else '1' if after_sda else '2'):continue
        q=fp.FindPadByNumber(number)
        pos=q.GetPosition();out=pos-fp.GetPosition()
        nx,ny=(int(math.copysign(1,out.x)),0) if abs(out.x)>abs(out.y) else (0,int(math.copysign(1,out.y)))
        for direction,lat in [(440000,0),(-440000,0),(350000,105000),(350000,-105000),(-350000,105000),(-350000,-105000),(0,110000),(0,-110000)]:
            if long_controls and not power_key and (number=='52' or (not after_scl and (direction,lat)!=(440000,0))):continue
            if extent and (direction,lat)!=(350000,105000):continue
            toe=pos+p.VECTOR2I(nx*direction-ny*lat,ny*direction+nx*lat)
            fields.append((f'U4.{number} at {direction} {lat}',q.GetNetname(),p.F_Cu,tuple(toe),200000))
if adopted_service:
    fields=[]
    fp=b.FindFootprintByReference('U4')
    for n in (('27',) if feedback3 else ('7','67')):
        pad=fp.FindPadByNumber(n);at=pad.GetPosition();delta=at-fp.GetPosition()
        nx,ny=(int(math.copysign(1,delta.x)),0) if abs(delta.x)>abs(delta.y) else (0,int(math.copysign(1,delta.y)))
        for radial,tangent in itertools.product((440000,-440000,350000,-350000),(-100000,0,100000)):
            start=tuple(at+p.VECTOR2I(nx*radial-ny*tangent,ny*radial+nx*tangent))
            fields.append((f'U4.{n} {radial} {tangent}',pad.GetNetname(),p.F_Cu,start,200000))
def sweep(label,net,layer,start,width):
    netcode=b.FindNet(net).GetNetCode()
    allnear=[o for o in allitems if inflated_box(o,10500000 if extent else 7800000 if long_controls else 5400000 if coexist else 3800000).Contains(p.VECTOR2I(*start))]
    near=[o for o in allnear if o.GetNetCode()!=netcode]
    geom={l:[(o.GetEffectiveShape(l),o.GetBoundingBox()) for o in near if o.IsOnLayer(l)] for l in layers}
    drills=[(o.GetEffectiveHoleShape(),o.GetPosition()) for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    same_drills=[o.GetEffectiveHoleShape() for o in allnear if o.GetNetCode()==netcode and (isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x)]
    lands=[o.GetEffectiveShape(o.GetParentFootprint().GetLayer()) for o in allnear if isinstance(o,p.PAD) and o.GetNetCode()==netcode and (o.IsOnLayer(p.F_Cu) or o.IsOnLayer(p.B_Cu))]
    vkeep=[q.Outline() for q in zones if q.GetIsRuleArea() and q.GetDoNotAllowVias()]
    tkeep=[q.Outline() for q in zones if q.GetIsRuleArea() and q.IsOnLayer(layer) and q.GetDoNotAllowTracks()]
    plane=[q for q in b.Zones() if q.GetNetname()=='GND' and q.IsOnLayer(p.In1_Cu) and not q.GetIsRuleArea()]
    t=p.PCB_TRACK(b);t.SetNetCode(netcode);t.SetWidth(width);t.SetLayer(layer)
    v=p.PCB_VIA(b);v.SetNetCode(netcode);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetWidth(450000);v.SetDrill(200000)
    edges=b.GetBoardEdgesBoundingBox()
    edges.Inflate(-252000)
    def edge(a,z):
        t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));s=t.GetEffectiveShape(layer);bb=inflated_box(t,365000)
        return edges.Contains(t.GetBoundingBox()) and not (any(bb.Intersects(box) and s.Collide(g,202000) for g,box in geom[layer]) or any(bb.Contains(pos) and s.Collide(h,250000) for h,pos in drills) or any(q.Collide(s,0) for q in tkeep))
    def via(at):
        v.SetPosition(p.VECTOR2I(*at));s=v.GetEffectiveShape(p.F_Cu);h=v.GetEffectiveHoleShape();bb=inflated_box(v,365000)
        return edges.Contains(v.GetBoundingBox()) and not(any(h.Collide(other,252000) for other in same_drills) or any(bb.Intersects(box) and (s.Collide(g,202000) or h.Collide(g,250000)) for l in layers for g,box in geom[l]) or any(bb.Contains(pos) and s.Collide(h,250000) for h,pos in drills) or any(q.Collide(s,0) for q in vkeep) or any(s.Collide(g,50000) for g in lands))
    if cleared:
        probe=p.VECTOR2I(*meta['site_nm']);v.SetPosition(probe);s=v.GetEffectiveShape(p.F_Cu);h=v.GetEffectiveHoleShape()
        if not hasattr(sweep,'reported'):
            print('released via',via(tuple(probe)), 'edge',edges.Contains(v.GetBoundingBox()),'same drills',sum(h.Collide(x,252000) for x in same_drills),'keepouts',[(z.GetZoneName(),z.GetLayerName()) for z in zones if z.GetIsRuleArea() and z.GetDoNotAllowVias() and z.Outline().Collide(s,0)], 'lands',sum(s.Collide(g,50000) for g in lands),'drills',[(str(pos),s.Collide(hole,250000)) for hole,pos in drills if s.Collide(hole,250000)], 'copper',[(o.m_Uuid.AsString(),o.GetNetname()) for o in near if any(o.IsOnLayer(l) and (s.Collide(o.GetEffectiveShape(l),202000) or h.Collide(o.GetEffectiveShape(l),250000)) for l in layers)],flush=True)
            sweep.reported=True
    step=50000;initial=tuple(round(x/step)*step for x in start);q=[(0,initial)];prev={};dist={initial:0};found=[];seen=0
    while q:
        length,xy=heapq.heappop(q)
        if length!=dist[xy]:continue
        seen+=1
        if (not (interior or wireless or long_controls) or all(math.dist(xy,other['via_nm'])>=(650000 if long_controls else 250000) for other in found)) and via(xy) and edge(start,initial):
            if net!='GND' or any(z.GetFilledPolysList(p.In1_Cu).Contains(p.VECTOR2I(*xy),-1,0) for z in plane):
                path=[xy]
                while path[-1]!=initial:path.append(prev[path[-1]])
                path.append(start);path.reverse();found.append(dict(via_nm=xy,length_mm=length/1e6,track_nm=path))
                if len(found)>=(12 if long_controls else 18 if wireless else 14 if interior else 6):break
        for dx,dy in ((1,0),(0,1),(-1,0),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            nxt=xy[0]+dx*step,xy[1]+dy*step;nd=length+math.hypot(dx,dy)*step
            if nd<=(9000000 if extent else 6500000 if long_controls else 4200000 if coexist and label.startswith('U4.61') else 2600000) and nd<dist.get(nxt,math.inf) and edge(xy,nxt):dist[nxt]=nd;prev[nxt]=xy;heapq.heappush(q,(nd,nxt))
    result=dict(label=label,net=net,width_nm=width,visited=seen,via_paths=found)
    if extent:
        result["max_reached_mm"]=max(dist.values())/1e6
        result["bounds_nm"]=[min(pt[0] for pt in dist),min(pt[1] for pt in dist),max(pt[0] for pt in dist),max(pt[1] for pt in dist)]
        counts={}
        for at in dist:
            v.SetPosition(p.VECTOR2I(*at));s=v.GetEffectiveShape(p.F_Cu);h=v.GetEffectiveHoleShape()
            if not edges.Contains(v.GetBoundingBox()) or any(s.Collide(g,50000) for g in lands) or any(h.Collide(other,252000) for other in same_drills) or any(rule.Collide(s,0) for rule in vkeep):continue
            bb=inflated_box(v,370000)
            blockers=[]
            for o in near:
                if not bb.Intersects(o.GetBoundingBox()):continue
                if any(o.IsOnLayer(l) and (s.Collide(o.GetEffectiveShape(l),202000) or h.Collide(o.GetEffectiveShape(l),250000)) for l in layers):
                    blockers.append(o)
                elif isinstance(o,p.PCB_VIA) and h.Collide(o.GetEffectiveHoleShape(),252000):blockers.append(o)
            if len(blockers)!=1:continue
            o=blockers[0];name=o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.m_Uuid.AsString()
            rec=counts.setdefault(name,dict(net=o.GetNetname(),count=0,first_site_nm=at,type=type(o).__name__))
            rec["count"]+=1
            if feedback3:
                walk=[at]
                while walk[-1] in prev:walk.append(prev[walk[-1]])
                walk.append(start);walk.reverse()
                rec.setdefault('sites',[]).append(dict(via_nm=at,launch_nm=walk,length_mm=dist[at]/1e6))
        result["single_copper_blockers"]=counts
    return result
result=[sweep(*entry) for entry in fields]
print([(i['label'],i['visited'],len(i['via_paths'])) for i in result],flush=True)
((root/'adopted-buck3-feedback-windows.json') if feedback3 else (root/'adopted-pmic-service-windows.json') if adopted_service else (root/'rotated-power-key-channel.json') if power_key else (root/'rotated-c422-scl-exits.json') if cleared else (root/'rotated-left-scl-channel.json') if extent else (root/'rotated-left-scl-exits.json') if after_sda else (root/'rotated-pmic-secondary-control-exits.json') if after_scl else (root/'rotated-pmic-long-control-exits.json') if long_controls else (root/'rotated-pmic-control-repair-launches.json') if retry_controls else (root/'pmic-control-launches.json') if control else (root/'pmic-pwron-launches.json') if pwron else (folder/'alternate-return-vias.json')).write_text(json.dumps(dict(coupon_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),circuits=result),indent=2)+'\n')
os._exit(0)
