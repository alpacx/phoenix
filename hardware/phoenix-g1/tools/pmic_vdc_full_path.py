"""Search from the PMIC's VDC land to the verified divider at full width on both faces."""
from functools import lru_cache
from pathlib import Path
import hashlib
import heapq
import json
import math
import sys
import os
import shutil
import subprocess
import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-soc-tx-series.json').read_text());src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
def pad(ref,n):return b.FindFootprintByReference(ref).FindPadByNumber(n)
pin=pad('U4','61');entry=pin.GetPosition();code=pin.GetNetCode()
passives=[pad('C410','1'),pad('R410','2'),pad('R411','1')]
assert len({q.GetNetCode() for q in passives+[pin]})==1
current={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(passives[0])}
assert all(q.m_Uuid.AsString() in current for q in passives)
inner_corridor='--inner-divider' in sys.argv
pivot=next((int(x.split('=')[1]) for x in sys.argv if x.startswith('--pivot-c481=')),0)
power_corridor='--power-corridor' in sys.argv or bool(pivot)
cluster_index=next((int(x.split('=')[1]) for x in sys.argv if x.startswith('--cluster-index=')),None)
ground_rework='--return-corridor' in sys.argv or inner_corridor or power_corridor or cluster_index is not None
joint='--reserve-divider' in sys.argv or ground_rework
removed=set()
if joint:
    # Only the same 0.2 mm distribution segment chain; retain 0.127 mm pin neck and endpoints.
    adjacency={}
    for t0 in b.GetTracks():
        if isinstance(t0,p.PCB_VIA) or t0.GetLayer()!=p.F_Cu or t0.GetNetname()!='+1V8_SYS' or t0.GetWidth()!=200000:continue
        a,z=tuple(t0.GetStart()),tuple(t0.GetEnd());uid=t0.m_Uuid.AsString()
        adjacency.setdefault(a,[]).append((z,uid));adjacency.setdefault(z,[]).append((a,uid))
    rail_start=(59300000,2650000);rail_end=(60300000,4900000)
    loc=rail_start;prevloc=None
    # Explicitly follow the path toward the toe, away from the regulator source.
    while loc!=rail_end:
        options=[(pt,uid) for pt,uid in adjacency[loc] if pt!=prevloc and pt[1]>=loc[1] and pt[0]>=loc[0]]
        assert len(options)==1,(loc,options)
        pt,uid=options[0];removed.add(uid);prevloc,loc=loc,pt
    old=[t0 for t0 in b.GetTracks() if t0.m_Uuid.AsString() in removed]
    original_rail_length=sum(t0.GetLength() for t0 in old)
    for t0 in old:b.Remove(t0)
if ground_rework:
    ground_removed={'271a02a1-76cb-4f5b-a020-e8d66558e0ce','cd7aab4a-1a87-4a93-8686-33994d0d4d25'}
    gtracks=[x for x in b.GetTracks() if x.m_Uuid.AsString() in ground_removed]
    assert len(gtracks)==2 and all(x.GetNetname()=='GND' and x.GetLayer()==p.B_Cu and x.GetWidth()==300000 for x in gtracks)
    for x in gtracks:b.Remove(x)
    removed.update(ground_removed)
if power_corridor:
    rear_ids={'912ad462-b391-465b-b54f-02db061aeabf','c0fe9ed4-f11d-45cc-8807-4dc601b9e864'}
    rear=[x for x in b.GetTracks() if x.m_Uuid.AsString() in rear_ids]
    assert len(rear)==2 and all(x.GetNetname()=='+3V3_SYS' and x.GetWidth()==300000 and x.GetLayer()==p.B_Cu for x in rear)
    for x in rear:b.Remove(x)
    removed.update(rear_ids)
if pivot:
    pivot_part=b.FindFootprintByReference('C481')
    pivot_point=pivot_part.FindPadByNumber('1').GetPosition()
    pivot_part.Rotate(pivot_point,p.EDA_ANGLE(pivot,p.DEGREES_T))
    assert pivot_part.FindPadByNumber('1').GetPosition()==pivot_point
if cluster_index is not None:
    row=json.loads((root/'pmic-divider-cluster-placement.json').read_text())['options'][cluster_index]
    ends={'e368d717-6558-4efc-bde9-454409fb5346','4d30df45-7da8-46e1-aee4-ac886ba88828','32e4042f-2d47-4672-8bb1-2a5349dcf2c0','a58de702-292d-4cee-ae3b-9e57e84f1585'}
    original=[o for o in b.GetTracks() if o.GetNetCode()==code or o.m_Uuid.AsString() in ends]
    assert len(original)==10
    for o in original:
        removed.add(o.m_Uuid.AsString());b.Remove(o)
    pts=[]
    for name,(x,y,angle) in row['placements'].items():
        f=b.FindFootprintByReference(name);f.SetOrientationDegrees(angle);f.SetPosition(p.VECTOR2I(x*100000,y*100000))
        pts.append(f.FindPadByNumber('2' if name=='R410' else '1').GetPosition())
    for a,z in zip(pts,pts[1:]):
        line=p.PCB_TRACK(b);line.SetStart(a);line.SetEnd(z);line.SetWidth(200000);line.SetNetCode(code);line.SetLayer(p.B_Cu);b.Add(line);current.add(line.m_Uuid.AsString())
tracks=list(b.GetTracks())
targets=[q.GetEffectiveShape(p.B_Cu) for q in passives]+[t.GetEffectiveShape(p.B_Cu) for t in tracks if t.IsOnLayer(p.B_Cu) and t.m_Uuid.AsString() in current]
items=[o for o in tracks+[q for f in b.GetFootprints() for q in f.Pads()] if o.GetNetCode()!=code and inflated_box(o,8000000).Contains(entry)]
obs={l:[(o,o.GetEffectiveShape(l),o.GetBoundingBox()) for o in items if o.IsOnLayer(l)] for l in layers}
holes=[(o.GetEffectiveHoleShape(),o.GetPosition()) for o in items if isinstance(o,p.PCB_VIA)]
zones=list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()]
keep={l:[z.Outline() for z in zones if z.GetIsRuleArea() and z.IsOnLayer(l) and z.GetDoNotAllowTracks()] for l in layers}
vkeep=[z.Outline() for z in zones if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
pinshape=pin.GetEffectiveShape(p.F_Cu);t=p.PCB_TRACK(b);t.SetWidth(200000);t.SetNetCode(code)
v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(code);v.SetWidth(450000);v.SetDrill(200000)
noise=[o for o in items if o.GetNetname().startswith(('PMIC_SW','CPU_SW','WIFI_BUCK_SW','PHY_REG_OUT'))]
def where(o):
    return o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.m_Uuid.AsString()
@lru_cache(None)
def edge(l,a,z):
    t.SetLayer(l);t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));sh=t.GetEffectiveShape(l);bb=inflated_box(t,360000)
    return not (any(bb.Intersects(box) and sh.Collide(s,202000) for _,s,box in obs[l]) or any(bb.Contains(pos) and sh.Collide(h,250000) for h,pos in holes) or any(k.Collide(sh,0) for k in keep[l]) or any(o.IsOnLayer(l) and sh.Collide(o.GetEffectiveShape(l),500000) for o in noise))
@lru_cache(None)
def evaluate(pt):
    v.SetPosition(p.VECTOR2I(*pt));sh=v.GetEffectiveShape(p.F_Cu);bb=inflated_box(v,360000);hole=v.GetEffectiveHoleShape()
    failures=set()
    if sh.Collide(pinshape,100000) or any(k.Collide(sh,0) for k in vkeep):return ('keepout/land',)
    for l in layers:
        for o,s,box in obs[l]:
            if bb.Intersects(box) and (sh.Collide(s,202000) or hole.Collide(s,250000)):failures.add(o.GetNetname()+' '+where(o))
    if any(bb.Contains(pos) and sh.Collide(h,250000) for h,pos in holes):failures.add('adjacent drill')
    return tuple(sorted(failures))
def tap(pt):
    vpt=p.VECTOR2I(*pt)
    # Put the track centre directly on existing same-net copper.
    return any(s.Collide(vpt,0) for s in targets)
def ptgrid(x,y):return (round(x/50000)*50000,round(y/50000)*50000)
moves=((1,0),(0,1),(-1,0),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1))
def solve():
    queue=[];dist={};prev={};missing={};legal=set();via_origins={}
    for offset in (-450000,-440000,-435000,435000,440000,450000):
        toe=(entry.x,entry.y+offset);node=(ptgrid(*toe),p.F_Cu)
        t.SetLayer(p.F_Cu);t.SetStart(p.VECTOR2I(*toe));t.SetEnd(p.VECTOR2I(*node[0]))
        if not t.GetEffectiveShape(p.F_Cu).Collide(pinshape,0) or not edge(p.F_Cu,toe,node[0]):continue
        d=math.dist(toe,node[0])
        if d<dist.get(node,math.inf):dist[node]=d;prev[node]=(toe,None);heapq.heappush(queue,(d,node))
    while queue:
        length,node=heapq.heappop(queue)
        if dist[node]!=length:continue
        pt,l=node
        if l==p.B_Cu and tap(pt):
            nodes=[node]
            while prev[nodes[-1]][1] is not None:nodes.append(prev[nodes[-1]])
            nodes.append((prev[nodes[-1]][0],p.F_Cu));nodes.reverse()
            return nodes,dist,missing,legal
        for dx,dy in moves:
            nxt=(pt[0]+dx*50000,pt[1]+dy*50000);nd=length+50000*math.hypot(dx,dy);nn=(nxt,l)
            if nd>(8000000 if ground_rework else 5500000) or nd>=dist.get(nn,math.inf) or not edge(l,pt,nxt):continue
            dist[nn]=nd;prev[nn]=node
            if node in via_origins:via_origins[nn]=via_origins[node]
            heapq.heappush(queue,(nd,nn))
        if l==p.F_Cu or (inner_corridor and l in (p.In2_Cu,p.In3_Cu) and math.dist(via_origins[node],pt)>=700000):
            fail=evaluate(pt)
            if fail:
                if fail!=('keepout/land',) and (fail not in missing or length<missing[fail][0]):missing[fail]=(length,pt)
            else:
                legal.add(pt);nd=length+400000;v.SetPosition(p.VECTOR2I(*pt))
                if any(v.GetEffectiveShape(p.B_Cu).Collide(q.GetEffectiveShape(p.B_Cu),50000) for q in passives):continue
                for destination in ((p.B_Cu,p.In2_Cu,p.In3_Cu) if inner_corridor and l==p.F_Cu else (p.B_Cu,)):
                    nn=(pt,destination)
                    if nd<dist.get(nn,math.inf):
                        dist[nn]=nd;prev[nn]=node;via_origins[nn]=pt
                        heapq.heappush(queue,(nd,nn))
    return [],dist,missing,legal
if '--divider-bank' in sys.argv:
    # Search the interior of each existing divider resistor/capacitor land, allowing
    # a capped via only if the complete 0.45 mm copper disk fits on the same-net land.
    options=[]
    for q in passives:
        pos=q.GetPosition()
        for dx in range(-4,5):
            for dy in range(-4,5):
                pt=tuple(pos+p.VECTOR2I(dx*25000,dy*25000));v.SetPosition(p.VECTOR2I(*pt))
                if not all(q.HitTest(p.VECTOR2I(pt[0]+round(225000*math.cos(i*math.tau/64)),pt[1]+round(225000*math.sin(i*math.tau/64)))) for i in range(64)):continue
                options.append(dict(ref=q.GetParentFootprint().GetReference(),via_nm=pt,blockers=evaluate(pt)))
    for xy in ((57150000,6400000),(57200000,6400000),(59450000,3250000),(59650000,4890000)):
        options.append(dict(ref='prior or projected landing',via_nm=xy,blockers=evaluate(xy)))
    options.sort(key=lambda x:len(x['blockers']))
    (root/'pmic-divider-capped-sites.json').write_text(json.dumps(dict(parent_sha256=meta['sha256'],considered=len(options),sites=options[:12]),indent=2)+'\n')
    print(options[:3],flush=True);os._exit(0)
nodes,dist,missing,legal=solve()
result=dict(parent_sha256=meta['sha256'],visited_front=sum(l==p.F_Cu for pt,l in dist),visited_back=sum(l==p.B_Cu for pt,l in dist),legal_via_sites=len(legal),adopted=False,obstacles_at_best_sites=[dict(items=items,via_nm=point,length_mm=length/1e6) for items,(length,point) in sorted(missing.items(),key=lambda row:(len(row[0]),row[1][0]))[:12]])
if not nodes:
    back_points=[(min(s.Distance(p.VECTOR2I(*pt)) for s in targets),pt,d) for (pt,l),d in dist.items() if l==p.B_Cu]
    if back_points:result['nearest_reachable_back_node']=min(back_points)
    probes=[]
    for offset in (-440000,440000):
        pt=(entry.x,entry.y+offset);ahead=(pt[0],pt[1]+(-100000 if offset<0 else 100000))
        t.SetLayer(p.F_Cu);t.SetStart(p.VECTOR2I(*pt));t.SetEnd(p.VECTOR2I(*ahead));sh=t.GetEffectiveShape(p.F_Cu)
        probes.append(dict(toe_nm=pt,touches_pin=sh.Collide(pinshape,0),copper=[(o.GetNetname(),where(o)) for o,geom,box in obs[p.F_Cu] if sh.Collide(geom,202000)],coupling=[(o.GetNetname(),where(o)) for o in noise if o.IsOnLayer(p.F_Cu) and sh.Collide(o.GetEffectiveShape(p.F_Cu),500000)],hole=[tuple(pos) for h,pos in holes if sh.Collide(h,250000)]))
    result['toe_probes']=probes
if nodes:
    parts=[]
    for (a,l),(z,m) in zip(nodes,nodes[1:]):
        if l!=m:
            launch=p.PCB_VIA(b);launch.SetViaType(p.VIATYPE_THROUGH);launch.SetLayerPair(p.F_Cu,p.B_Cu);launch.SetWidth(450000);launch.SetDrill(200000);launch.SetNetCode(code);launch.SetPosition(p.VECTOR2I(*a));parts.append(launch);continue
        if a==z:continue
        if parts and not isinstance(parts[-1],p.PCB_VIA) and parts[-1].GetLayer()==l:
            prior=tuple(parts[-1].GetStart());d=(a[0]-prior[0],a[1]-prior[1]);e=(z[0]-a[0],z[1]-a[1])
            if d[0]*e[1]==d[1]*e[0] and d[0]*e[0]+d[1]*e[1]>0:parts[-1].SetEnd(p.VECTOR2I(*z));continue
        seg=p.PCB_TRACK(b);seg.SetWidth(200000);seg.SetNetCode(code);seg.SetLayer(l);seg.SetStart(p.VECTOR2I(*a));seg.SetEnd(p.VECTOR2I(*z));parts.append(seg)
    for part in parts:b.Add(part)
    if joint:
        # Record the reserved contact path. It is not electrically valid until the original supply is restored.
        result['reserved_path_nm']=nodes;result['removed_supply_objects']=sorted(removed)
        (root/(f'pmic-divider-placement-{cluster_index}.json' if cluster_index is not None else f'pmic-divider-c481-pivot-{pivot}.json' if pivot else 'pmic-divider-power-corridor.json' if power_corridor else 'pmic-divider-inner.json' if inner_corridor else 'pmic-reroute-returns.json' if ground_rework else 'pmic-reserved-divider.json')).write_text(json.dumps(result,indent=2)+'\n')
        if cluster_index is not None:
            folder=root/f'runs/vdc-placement-{cluster_index}';folder.mkdir(exist_ok=True)
            for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/n,folder/n)
            p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(folder/src.name),b)
        print('Separated path',len(nodes),len(legal),flush=True);os._exit(0)
    folder=root/'runs/pmic-startup-divider';folder.mkdir(exist_ok=True)
    for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/n,folder/n)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    result['new_drc']=delta
    if not delta:
        saved=p.LoadBoard(str(out));saved.BuildConnectivity();verify_preservation(original:=p.LoadBoard(str(src)),saved);assert not screen(saved)
        p61=saved.FindFootprintByReference('U4').FindPadByNumber('61');ids={o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(p61)}
        assert all(q.m_Uuid.AsString() in ids for q in passives)
        result.update(adopted=True,board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),pairs=[['U4.61',q.GetParentFootprint().GetReference()+'.'+q.GetNumber()] for q in passives],path_nm=nodes)
(root/(f'pmic-divider-placement-{cluster_index}.json' if cluster_index is not None else f'pmic-divider-c481-pivot-{pivot}.json' if pivot else 'pmic-divider-power-corridor.json' if power_corridor else 'pmic-divider-inner.json' if inner_corridor else 'pmic-reroute-returns.json' if ground_rework else 'pmic-reserved-divider.json' if joint else 'pmic-startup-divider.json')).write_text(json.dumps(result,indent=2)+'\n')
print(result['adopted'],result['visited_front'],len(legal),result['obstacles_at_best_sites'][:2],flush=True);os._exit(0)
