"""Place the eMMC VCCQ link and its attached D0 pull-up directly at the existing VCCQ bank."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import pcbnew as p
import native_front_splice as bend
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
fixed_pull='--keep-pullup' in sys.argv
wide_bank='--extended-bank-pullup' in sys.argv or fixed_pull
separate='--independent-pullup' in sys.argv or wide_bank
pivot='--pivot-return' in sys.argv or separate
expanded='--reachable-placements' in sys.argv or pivot
grid_window='--copper-window' in sys.argv or expanded
current='--source-window' in sys.argv or grid_window
cp=json.loads((root/('layout-memory-n12-neighbors.json' if current else 'layout-memory-cap-return.json')).read_text())
if pivot:
    pivot_doc=json.loads((root/'emmc-io-link-return-window.json').read_text())
    assert pivot_doc['parent_sha256']==cp['sha256']
    cp=pivot_doc['candidate']
src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
original=p.LoadBoard(str(src));b=p.LoadBoard(str(src));b.BuildConnectivity();side=p.B_Cu
fp=lambda ref:b.FindFootprintByReference(ref)
q=lambda ref,n:fp(ref).FindPadByNumber(n)
uid=lambda o:o.m_Uuid.AsString()
xy=lambda o:tuple(o.GetPosition())
v=lambda pt:p.VECTOR2I(*pt)
link,pull=fp('R8006'),fp('R8001')
lp,li=q('R8006','2'),q('R8006','1');pp,pd=q('R8001','1'),q('R8001','2')
data_ball=xy(q('U8001','A3'));old_data_span=math.dist(xy(pd),data_ball)
bank=q('C8002','1');bank_members={uid(o) for o in b.GetConnectivity().GetConnectedItems(bank)}
rail=bank.GetNetCode()
source_members={uid(o) for o in b.GetConnectivity().GetConnectedItems(lp)}
old_trace,=[t for t in b.GetTracks() if uid(t) in source_members]
assert old_trace.GetWidth()==500000 and old_trace.GetLayer()==side
retired=uid(old_trace);b.Remove(old_trace)
parts=[f for f in b.GetFootprints() if f.GetReference() not in ('R8001','R8006')]
physical=[*b.GetTracks(),*(pad for f in parts for pad in f.Pads())]
taps=set()
for item in physical:
    if uid(item) not in bank_members or not item.IsOnLayer(side):continue
    if isinstance(item,p.PAD) and item.GetParentFootprint().GetReference().startswith('C'):
        taps.add(xy(item))
        if current:
            center=xy(item)
            taps.update((center[0]+i,center[1]+j) for i in (-175000,0,175000) for j in (-175000,0,175000) if item.HitTest(v((center[0]+i,center[1]+j))))
    elif isinstance(item,p.PCB_TRACK) and not isinstance(item,p.PCB_VIA) and item.GetWidth()>=500000:
        n=max(1,math.ceil(item.GetLength()/300000))
        taps.update(tuple(round(x+(y-x)*k/n) for x,y in zip(item.GetStart(),item.GetEnd())) for k in range(n+1))
cell=1000000;index=defaultdict(list);court_index=defaultdict(list)
def cells(bb):
    return ((i,j) for i in range(bb.GetLeft()//cell,bb.GetRight()//cell+1) for j in range(bb.GetTop()//cell,bb.GetBottom()//cell+1))
for f in parts:
    if f.GetLayer()!=side:continue
    ct=f.GetCourtyard(side)
    if ct.OutlineCount():
        for k in cells(inflated_box(f,200000)):court_index[k].append((uid(f),ct))
for obj in physical:
    shape=obj.GetEffectiveShape(side) if obj.IsOnLayer(side) else None
    hole=obj.GetEffectiveHoleShape() if isinstance(obj,p.PCB_VIA) or isinstance(obj,p.PAD) and obj.GetDrillSize().x else None
    if not shape and not hole:continue
    record=(uid(obj),obj.GetNetCode(),shape,hole)
    for k in cells(inflated_box(obj,350000)):index[k].append(record)
rules=[z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
def clear(item):
    sh=item.GetEffectiveShape(side);seen=set()
    for k in cells(item.GetBoundingBox()):
        for identifier,net,other,hole in index[k]:
            if identifier in seen:continue
            seen.add(identifier)
            if net!=item.GetNetCode() and other and sh.Collide(other,202000) or hole and sh.Collide(hole,252000):return False
    return not any(sh.Collide(zone,0) for zone in rules)
def footprint_clear(f):
    shape=f.GetCourtyard(side);seen=set()
    for k in cells(shape.BBox()):
        for identifier,other in court_index[k]:
            if identifier not in seen and shape.Collide(other,100000):return False
            seen.add(identifier)
    return all(clear(o) for o in f.Pads())
positions=set()
for target in taps:
    cx,cy=(round(k/200000) for k in target)
    positions.update(((cx+i)*200000,(cy+j)*200000) for i in range(-12,13) for j in range(-12,13))
candidates=[];stats=Counter();unserved=[];placement_barriers=[]
if current:
    frontier=json.loads((root/'runs/sys-feed-r8006.1-frontier.json').read_text())
    source_points={(x,y) for layer,x,y in frontier if layer==3}
for angle in (0,90,180,270):
    link.SetOrientationDegrees(angle)
    for pos in sorted(positions):
        link.SetPosition(v(pos))
        if not footprint_clear(link):continue
        stats['link_placements']+=1
        if current:
            center=xy(li)
            reachable=any((x,y) in source_points and li.HitTest(v((x,y))) for x in range(round(center[0]/100000)*100000-500000, round(center[0]/100000)*100000+500001,100000) for y in range(round(center[1]/100000)*100000-500000,round(center[1]/100000)*100000+500001,100000))
            if not reachable:continue
            stats['source_accessible_placements']+=1
        possible=sorted((math.dist(xy(lp),pt),pt) for pt in taps)
        unserved.append((pos,angle,possible))
        for length,target in possible:
            if length>1900000:break
            branch=make(b,xy(lp),target,500000,rail,side)
            if not length or not clear(branch) or branch.GetEffectiveShape(side).Collide(li.GetEffectiveShape(side),202000):continue
            candidates.append((length,pos,angle,target,[xy(lp),target]));break
if grid_window and not candidates:
    import heapq
    grid=100000
    costs={};parents={};starts={};queue=[]
    for at in sorted(taps):
        cell_pt=tuple(round(n/grid)*grid for n in at)
        if clear(make(b,at,cell_pt,500000,rail,side)):
            distance=math.dist(at,cell_pt)
            if distance<costs.get(cell_pt,math.inf):
                costs[cell_pt]=distance;parents[cell_pt]=None;starts[cell_pt]=at;heapq.heappush(queue,(distance,cell_pt))
    while queue:
        cost,pt=heapq.heappop(queue)
        if costs.get(pt)!=cost:continue
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)):
            end=(pt[0]+dx*grid,pt[1]+dy*grid)
            value=cost+math.hypot(dx,dy)*grid
            if value>=costs.get(end,math.inf) or value>(13000000 if wide_bank else 7000000) or not clear(make(b,pt,end,500000,rail,side)):continue
            costs[end]=value;parents[end]=pt;heapq.heappush(queue,(value,end))
    stats['reachable_bank_cells']=len(costs)
    if expanded:
        for pos,angle,_ in unserved:
            link.SetOrientationDegrees(angle);link.SetPosition(v(pos));qpos=xy(lp)
            selected=[]
            for end in sorted(costs,key=lambda pt:math.dist(pt,qpos)):
                if any(math.dist(end,s)<500000 for s in selected):continue
                selected.append(end)
                k=make(b,qpos,end,500000,rail,side);sh=k.GetEffectiveShape(side)
                hits=[]
                for o in physical:
                    if not inflated_box(k,350000).Intersects(o.GetBoundingBox()):continue
                    if (o.GetNetCode()!=rail and o.IsOnLayer(side) and sh.Collide(o.GetEffectiveShape(side),202000)) or ((isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x) and sh.Collide(o.GetEffectiveHoleShape(),252000)):
                        hits.append({'type':o.GetClass(),'net':o.GetNetname(),'ref':o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else None,'uuid':uid(o)})
                placement_barriers.append(dict(pos=pos,angle=angle,bridge=[qpos,end],gap_mm=k.GetLength()/1e6,hits=hits,rules=sum(sh.Collide(z,0) for z in rules)))
                if len(selected)==4:break
        placement_barriers.sort(key=lambda r:(len(r['hits'])+r['rules'],r['gap_mm']))
        unserved=[]
        for angle in (0,90,180,270):
            link.SetOrientationDegrees(angle);link.SetPosition(v((0,0)))
            offset=xy(lp)
            targets={(round((x-offset[0])/200000)*200000,round((y-offset[1])/200000)*200000) for x,y in costs}
            for pos in sorted(targets):
                link.SetPosition(v(pos))
                if not footprint_clear(link):continue
                center=xy(li);cx,cy=(round(n/grid)*grid for n in center)
                if not any((x,y) in source_points and li.HitTest(v((x,y))) for x in range(cx-500000,cx+500001,grid) for y in range(cy-500000,cy+500001,grid)):continue
                unserved.append((pos,angle,None))
        stats['placements_on_both_frontiers']=len(unserved)
    for pos,angle,possible in unserved:
        link.SetOrientationDegrees(angle);link.SetPosition(v(pos))
        at=xy(lp);grid_pt=tuple(round(n/grid)*grid for n in at)
        ends=[(grid_pt[0]+i*grid,grid_pt[1]+j*grid) for i in range(-4,5) for j in range(-4,5)]
        for end in sorted((pt for pt in ends if pt in costs and lp.HitTest(v(pt))),key=lambda pt:costs[pt]):
            route=[end]
            while parents[route[-1]] is not None:route.append(parents[route[-1]])
            target=starts[route[-1]]
            if route[-1]!=target:route.append(target)
            if len(route)<2:continue
            lines=[make(b,a,z,500000,rail,side) for a,z in zip(route,route[1:])]
            if any(k.GetEffectiveShape(side).Collide(li.GetEffectiveShape(side),202000) for k in lines):continue
            candidates.append((sum(k.GetLength() for k in lines),pos,angle,target,route));break
if not candidates and not grid_window:
    bend.side=side
    tried=0
    for pos,angle,possible in unserved:
        link.SetOrientationDegrees(angle);link.SetPosition(v(pos))
        selected=[]
        for length,target in possible:
            if length>3200000:break
            if any(math.dist(target,old)<500000 for old in selected):continue
            selected.append(target);tried+=1
            path,diagnostic=bend.recover(b,[(xy(lp),target,500000,rail)],'EMMC_IO_1V8',None,search_all_obstacles=True,minimum_clearance_nm=202000)
            if path and diagnostic['length_mm']<4 and all(clear(make(b,a,z,500000,rail,side)) for a,z in zip(path,path[1:])):
                candidates.append((diagnostic['length_mm']*1e6,pos,angle,target,path));break
            if len(selected)>=4:break
    stats['bent_routes_tested']=tried
stats['linked_placements']=len(candidates)
solutions=[]
independent=[]
if separate and candidates and not fixed_pull:
    for alpha in (0,90,180,270):
        pull.SetOrientationDegrees(alpha);pull.SetPosition(v((0,0)));offset=xy(pp)
        locations={(round((x-offset[0])/100000)*100000,round((y-offset[1])/100000)*100000) for x,y in costs}
        for at in sorted(locations):
            pull.SetPosition(v(at))
            distance=math.dist(xy(pd),data_ball)
            if not footprint_clear(pull):continue
            stats['clear_pullup_poses']+=1
            stats['minimum_direct_ball_distance_um']=min(stats.get('minimum_direct_ball_distance_um',10**9),round(distance/1000))
            if distance>old_data_span:continue
            stats['clear_pullup_within_original_span']+=1
            px,py=xy(pp);cx,cy=round(px/grid)*grid,round(py/grid)*grid
            ends=[(cx+i*grid,cy+j*grid) for i in range(-2,3) for j in range(-2,3)]
            for end in sorted((pt for pt in ends if pt in costs and pp.HitTest(v(pt))),key=costs.get):
                path=[end]
                while parents[path[-1]] is not None:path.append(parents[path[-1]])
                if path[-1]!=starts[path[-1]]:path.append(starts[path[-1]])
                lines=[make(b,a,z,500000,rail,side) for a,z in zip(path,path[1:])]
                if not lines or any(t.GetEffectiveShape(side).Collide(pd.GetEffectiveShape(side),202000) for t in lines):continue
                independent.append((distance,at,alpha,path));break
    stats['independent_pullup_placements']=len(independent)
for length,pos,angle,target,routing in sorted(candidates):
    link.SetOrientationDegrees(angle);link.SetPosition(v(pos));branches=[make(b,a,z,500000,rail,side) for a,z in zip(routing,routing[1:])]
    if fixed_pull:
        solutions.append((old_data_span,length,pos,angle,tuple(original.FindFootprintByReference('R8001').GetPosition()),original.FindFootprintByReference('R8001').GetOrientationDegrees(),target,routing,[]))
        if len(solutions)>=100:break
        continue
    if separate:
        for distance,at,alpha,path in sorted(independent):
            pull.SetOrientationDegrees(alpha);pull.SetPosition(v(at))
            if pull.GetCourtyard(side).Collide(link.GetCourtyard(side),100000):continue
            lines=[make(b,a,z,500000,rail,side) for a,z in zip(path,path[1:])]
            if any(t.GetEffectiveShape(side).Collide(o.GetEffectiveShape(side),202000) for t in branches+lines for o in (li,pd)):continue
            solutions.append((distance,length+sum(t.GetLength() for t in lines),pos,angle,at,alpha,target,routing,path));break
        if len(solutions)>=30:break
        continue
    for alpha in (0,90,180,270):
        pull.SetOrientationDegrees(alpha)
        for i in range(-10,11):
            for j in range(-10,11):
                if i*i+j*j>100:continue
                at=(pos[0]+i*200000,pos[1]+j*200000);pull.SetPosition(v(at))
                if math.dist(xy(pd),data_ball)>old_data_span or not footprint_clear(pull):continue
                if pull.GetCourtyard(side).Collide(link.GetCourtyard(side),100000):continue
                k=make(b,xy(pp),xy(lp),500000,rail,side)
                if k.GetLength()>2000000 or not clear(k):continue
                if any(t.GetEffectiveShape(side).Collide(o.GetEffectiveShape(side),202000) for t in [*branches,k] for o in (li,pd)):continue
                solutions.append((math.dist(xy(pd),data_ball),length+k.GetLength(),pos,angle,at,alpha,target,routing))
    if len(solutions)>=30:break
stats['solutions']=len(solutions);outcome=None
folder=root/('runs/emmc-bank-link-keep-pullup' if fixed_pull else 'runs/emmc-bank-link-extended-bank' if wide_bank else 'runs/emmc-bank-link-independent-pullup' if separate else 'runs/emmc-bank-link-after-return' if pivot else 'runs/emmc-bank-link-both-frontiers' if expanded else 'runs/emmc-bank-link-copper-window' if grid_window else 'runs/emmc-bank-link-source-window' if current else 'runs/emmc-bank-link-relocated');folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
for rec in sorted(solutions)[:12]:
    distance,total,pos,angle,at,alpha,target,routing=rec[:8]
    link.SetOrientationDegrees(angle);link.SetPosition(v(pos));pull.SetOrientationDegrees(alpha);pull.SetPosition(v(at))
    power_lines=[make(b,a,z,500000,rail,side) for a,z in zip(routing,routing[1:])]
    pull_lines=[make(b,a,z,500000,rail,side) for a,z in zip(rec[8],rec[8][1:])] if separate else [make(b,xy(pp),xy(lp),500000,rail,side)]
    lines=power_lines+pull_lines
    for t in lines:b.Add(t)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    report=lambda path:json.loads((path/'drc.json').read_text())
    delta=introduced(report(src.parent),report(folder));saved=p.LoadBoard(str(out))
    if not delta and not screen(saved):
        if fixed_pull:
            # The link moved to the eMMC capacitor bank. Restore R8001 with a
            # separate branch before this provisional coupon may be adopted.
            outcome=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),link_nm=pos,link_branch_mm=sum(t.GetLength() for t in power_lines)/1e6,retired=retired,pullup_group_pending=True)
            break
        preserved=verify_preservation(original,saved,replaced_copper={retired})
        ids={uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('C8002').FindPadByNumber('1'))}
        assert uid(saved.FindFootprintByReference('R8006').FindPadByNumber('2')) in ids and uid(saved.FindFootprintByReference('R8001').FindPadByNumber('1')) in ids
        outcome=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),link_nm=pos,pullup_nm=at,bank_tap_nm=target,
                     power_leg_mm=sum(t.GetLength() for t in power_lines)/1e6,pullup_leg_mm=sum(t.GetLength() for t in pull_lines)/1e6,old_ball_distance_mm=old_data_span/1e6,
                     new_ball_distance_mm=distance/1e6,new_drc=delta,preservation=preserved)
        break
    for t in lines:b.Remove(t)
(root/('emmc-io-link-keep-pullup.json' if fixed_pull else 'emmc-io-link-extended-bank.json' if wide_bank else 'emmc-io-link-independent-pullup.json' if separate else 'emmc-io-link-after-return.json' if pivot else 'emmc-io-link-both-frontiers.json' if expanded else 'emmc-io-link-copper-window.json' if grid_window else 'emmc-io-link-source-window.json' if current else 'emmc-io-rail-link-placement.json')).write_text(json.dumps(dict(parent_sha256=cp['sha256'],stages=dict(stats),candidate=outcome,placement_barriers=placement_barriers[:12],assembly_ready=False),indent=2)+'\n')
print(stats,bool(outcome),flush=True)
