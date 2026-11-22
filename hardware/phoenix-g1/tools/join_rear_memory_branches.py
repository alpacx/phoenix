"""Route 0.5-mm taps between existing rear LPDDR bypass islands with a multisource copper search."""
import hashlib
import heapq
import json
import math
import shutil
import sys
import subprocess
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
zq='--ram-zq-supply' in sys.argv
ramfront=next((n for n in ('vdd1','vddq') if '--ram-front-'+n in sys.argv),None)
if zq:ramfront='zq'
ram_report='ram-n12-neighbors' if '--after-n12' in sys.argv else 'ram-front-'+str(ramfront)
investigate='--identify-obstruction' in sys.argv
power_bank=next((n for n in ('cpu','logic','gpu','npu','vdd1') if '--soc-'+n+'-bank' in sys.argv),None)
power_groups={'vdd1':('C2305',['C2303','C2302','C2301','L405']),
              'cpu':('C1603',['C1601','C1602','C1605','C1606','C1607','C1608']),
              'logic':('C1610',['C1609','C1611','C1612','C1613','C1614','C1615']),
              'gpu':('C1619',['C1616','C1617','C1618','C1620']),
              'npu':('C1621',['C1622','C1623','C1624'])}
link_cap='--emmc-link-bypass' in sys.argv
emmc=link_cap or '--emmc-io' in sys.argv or '--emmc-core' in sys.argv
emmc_core='--emmc-core' in sys.argv
package_feed='--emmc-package-feed' in sys.argv
current_emmc='--after-vccq-link' in sys.argv or package_feed
entry=json.loads((root/('layout-memory-trunk-widths.json' if ramfront else 'layout-memory-cap-return.json' if emmc or power_bank else 'layout-memory-bank-rear-taps.json' if investigate else 'layout-memory-ab4-bank.json')).read_text());src=root/entry['board']
checkpoint_override=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--checkpoint=')),None)
if checkpoint_override:
    assert power_bank or ramfront or current_emmc
    entry=json.loads((root/(checkpoint_override+'.json')).read_text());src=root/entry['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==entry['sha256']
board=p.LoadBoard(str(src));old=p.LoadBoard(str(src));side=p.F_Cu if ramfront else p.B_Cu
anchor=board.FindFootprintByReference(power_groups[power_bank][0] if power_bank else 'C8003' if link_cap else 'C8007' if emmc_core else 'C8002' if emmc else 'C1666').FindPadByNumber('1')
if ramfront:anchor=board.FindFootprintByReference('R201' if zq else 'U2').FindPadByNumber('2' if zq else 'F1' if ramfront=='vdd1' else 'AB4')
code=anchor.GetNetCode();width=600000 if power_bank and power_bank!="vdd1" else 500000;step=50000;cell=500000;limit=14000000 if package_feed else 8000000
def point(x):return tuple(x.GetPosition())
def v(pt):return p.VECTOR2I(*pt)
def uid(x):return x.m_Uuid.AsString()
physical=[*board.GetTracks(),*(q for f in board.GetFootprints() for q in f.Pads())]
obstacles=defaultdict(list)
for item in physical:
    if item.GetNetCode()==code:continue
    shape=item.GetEffectiveShape(side) if item.IsOnLayer(side) else None
    hole=item.GetEffectiveHoleShape() if isinstance(item,p.PCB_VIA) or isinstance(item,p.PAD) and item.GetDrillSize().x else None
    if not shape and not hole:continue
    bb=inflated_box(item,650000)
    for ix in range(bb.GetLeft()//cell,bb.GetRight()//cell+1):
        for iy in range(bb.GetTop()//cell,bb.GetBottom()//cell+1):
            obstacles[ix,iy].append((shape,hole))
keep=[z.Outline() for z in board.Zones() if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
wire=make(board,(0,0),(0,0),width,code,side)
@lru_cache(maxsize=300000)
def clear(a,z):
    wire.SetStart(v(a));wire.SetEnd(v(z));sh=wire.GetEffectiveShape(side)
    return not any((shape and sh.Collide(shape,202000)) or (hole and sh.Collide(hole,252000)) for shape,hole in obstacles[a[0]//cell,a[1]//cell]) and not any(sh.Collide(k,0) for k in keep)
def grid(pt):return tuple(round(x/step)*step for x in pt)
def group_samples(pad,land_only=False):
    board.BuildConnectivity()
    members={uid(o) for o in board.GetConnectivity().GetConnectedItems(pad)}
    samples={}
    for item in physical:
        if uid(item) not in members or not item.IsOnLayer(side) or land_only and uid(item)!=uid(pad):continue
        if isinstance(item,p.PAD) or isinstance(item,p.PCB_VIA):
            at=point(item);pts=[(at[0]+dx,at[1]+dy) for dx in (-100000,0,100000) for dy in (-100000,0,100000) if item.HitTest(v((at[0]+dx,at[1]+dy)))]
        else:
            if item.GetWidth()<width:continue
            count=max(1,math.ceil(item.GetLength()/100000))
            pts=[tuple(round(x+(y-x)*k/count) for x,y in zip(item.GetStart(),item.GetEnd())) for k in range(count+1)]
        for at in pts:
            aligned=grid(at)
            if clear(aligned,at):samples[aligned]=at
    return samples
def compact(path):
    clean=[]
    for at in path:
        if clean and clean[-1]==at:continue
        if len(clean)>1:
            a,b=clean[-2:]
            dx,dy=b[0]-a[0],b[1]-a[1];ex,ey=at[0]-b[0],at[1]-b[1]
            if dx*ey==dy*ex and dx*ex+dy*ey>0:clean.pop()
        clean.append(at)
    return clean
def route(start,end):
    queue=[(0,pt) for pt in start];heapq.heapify(queue)
    dist={pt:0 for pt in start};prev={}
    while queue:
        cost,pt=heapq.heappop(queue)
        if cost!=dist[pt]:continue
        if pt in end:
            back=[pt]
            while back[-1] in prev:back.append(prev[back[-1]])
            path=compact([start[back[-1]],*reversed(back),end[pt]])
            return path,len(dist)
        for dx,dy in ((0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)):
            target=pt[0]+dx*step,pt[1]+dy*step
            length=cost+math.hypot(dx,dy)*step
            if length>limit or length>=dist.get(target,math.inf):continue
            if clear(pt,target):
                dist[target]=length;prev[target]=pt;heapq.heappush(queue,(length,target))
    return None,len(dist)
if investigate:
    blocked_ref=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--blocked-ref=')),None)
    first=group_samples(board.FindFootprintByReference(blocked_ref or ('R8006' if link_cap else 'C1663')).FindPadByNumber('2' if link_cap else '1'),land_only=link_cap)
    end=group_samples(anchor)
    def separated(raw):
        kept=[]
        for pt in sorted(raw):
            if all(math.dist(pt,old)>180000 for old in kept):kept.append(pt)
        return kept
    sources=separated(first);goals=separated(end)
    candidates=sorted((math.dist(x,y),x,y) for x in sources for y in goals if math.dist(x,y)<4200000)
    groups={}
    for length,a,z in candidates:
        wire.SetStart(v(a));wire.SetEnd(v(z));sh=wire.GetEffectiveShape(side);bb=inflated_box(wire,350000)
        offenders=[]
        for obj in physical:
            if obj.GetNetCode()==code or not bb.Intersects(obj.GetBoundingBox()):continue
            copper=obj.IsOnLayer(side) and sh.Collide(obj.GetEffectiveShape(side),202000)
            drill=(isinstance(obj,p.PCB_VIA) or isinstance(obj,p.PAD) and obj.GetDrillSize().x) and sh.Collide(obj.GetEffectiveHoleShape(),252000)
            if copper or drill:
                offenders.append((uid(obj),obj.GetClass(),obj.GetNetname(),obj.GetParentFootprint().GetReference() if isinstance(obj,p.PAD) else '',point(obj)))
        if any(sh.Collide(poly,0) for poly in keep):continue
        key=tuple(sorted(offenders))
        if key not in groups:groups[key]=dict(length_mm=length/1e6,start_nm=a,end_nm=z,blockers=key)
    result=sorted(groups.values(),key=lambda row:(len(row['blockers']),row['length_mm']))
    (root/('vdd1-'+blocked_ref.lower()+'-obstructions.json' if blocked_ref else 'emmc-link-bypass-obstructions.json' if link_cap else 'memory-bank-rear-obstructions.json')).write_text(json.dumps(dict(parent_sha256=entry['sha256'],candidate_chords=len(candidates),shortest_obstructions=result[:30]),indent=2)+'\n')
    print(len(candidates),[(len(row['blockers']),[e[1:4] for e in row['blockers']]) for row in result[:4]],flush=True)
    sys.exit(0)
steps=[]
tried_topologies=set()
if zq:tasks=[('U2','A4')]
elif ramfront:
    tasks=[('U2',q.GetNumber()) for q in board.FindFootprintByReference('U2').Pads() if q.GetNetCode()==code]*2
elif power_bank:
    tasks=[(ref,'2' if ref=='L405' else '1') for ref in power_groups[power_bank][1]]*2
elif link_cap:
    tasks=[('R8006','2')]
elif emmc_core:
    tasks=[('U8001',num) for num in ('E6','F5','J10','K9')]
elif emmc:
    tasks=[('C8003','1'),('R8001','1')]+[('U8001',num) for num in ('C6','M4','N4','P3','P5')]
else:
    tasks=[('C1663','1'),('C1669','1'),('C1663','1')]
for ref,number in tasks:
    if not ramfront and not emmc and not power_bank and len(steps)==2 and not steps[-1]['path_nm']:break
    pad=board.FindFootprintByReference(ref).FindPadByNumber(number)
    board.BuildConnectivity()
    if uid(anchor) in {uid(o) for o in board.GetConnectivity().GetConnectedItems(pad)}:continue
    topology=(uid(pad),frozenset(uid(o) for o in board.GetConnectivity().GetConnectedItems(anchor)))
    if topology in tried_topologies:continue
    tried_topologies.add(topology)
    starts=group_samples(pad,land_only=link_cap);ends=group_samples(anchor)
    necks={}
    if package_feed and ref=='U8001':
        x,y=point(pad)
        for dx,dy in ((0,1),(0,-1),(1,0),(-1,0),(1,1),(-1,-1),(1,-1),(-1,1)):
            for units in (300000,400000,500000):
                fraction=units/math.hypot(dx,dy)
                end=grid((x+round(dx*fraction),y+round(dy*fraction)))
                lead=make(board,(x,y),end,300000,code,side);sh=lead.GetEffectiveShape(side)
                bb=inflated_box(lead,350000)
                obstacles_here=[o for o in physical if o.GetNetCode()!=code and bb.Intersects(o.GetBoundingBox())]
                if not clear(end,end) or any(sh.Collide(k,0) for k in keep):continue
                if any(o.IsOnLayer(side) and sh.Collide(o.GetEffectiveShape(side),202000) or (isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x) and sh.Collide(o.GetEffectiveHoleShape(),252000) for o in obstacles_here):continue
                starts[end]=end;necks[end]=((x,y),end)
    path,count=route(starts,ends)
    row=dict(ref=ref,pad=number,source_land_sites=len(starts),target_land_sites=len(ends),cells=count,path_nm=path)
    if package_feed:row['package_exits']=list(necks)
    steps.append(row)
    if path:
        if path[0] in necks:
            a,z=necks[path[0]]
            tr=make(board,a,z,300000,code,side);board.Add(tr);physical.append(tr)
            row['package_neck_nm']=[a,z]
        for a,z in zip(path,path[1:]):
            tr=make(board,a,z,width,code,side);board.Add(tr);physical.append(tr)
        board.BuildConnectivity()
        assert uid(anchor) in {uid(x) for x in board.GetConnectivity().GetConnectedItems(pad)}
result=dict(parent_sha256=entry['sha256'],width_mm=width/1e6,grid_mm=step/1e6,limit_mm=limit/1e6,steps=steps)
if any(row['path_nm'] for row in steps):
    folder=root/'runs'/('emmc-package-'+('core' if emmc_core else 'io') if package_feed else 'emmc-powered-bank-taps' if current_emmc else ram_report if ramfront else 'soc-'+power_bank+'-rear-bank' if power_bank else 'emmc-link-bypass' if link_cap else 'emmc-core-rear-taps' if emmc_core else 'emmc-io-rear-taps' if emmc else 'memory-bank-rear-taps');folder.mkdir(exist_ok=True)
    for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
    out=folder/src.name;p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(out),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    drc=lambda path:json.loads((path/'drc.json').read_text())
    saved=p.LoadBoard(str(out))
    result.update(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),new_drc=introduced(drc(src.parent),drc(folder)),preservation=verify_preservation(old,saved),mounts=screen(saved))
(root/('emmc-package-'+('core' if emmc_core else 'io')+'.json' if package_feed else 'emmc-powered-bank-taps.json' if current_emmc else ram_report+'.json' if ramfront else 'soc-'+power_bank+'-rear-bank.json' if power_bank else 'emmc-link-bypass.json' if link_cap else 'emmc-core-rear-taps.json' if emmc_core else 'emmc-io-rear-taps.json' if emmc else 'memory-bank-rear-taps.json')).write_text(json.dumps(result,indent=2)+'\n')
print([(r['ref'],r['cells'],bool(r['path_nm'])) for r in steps],result.get('new_drc'),flush=True)
