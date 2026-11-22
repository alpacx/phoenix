"""Rebuild the three copper corridors around two reserved USB contact joins on a copy."""
import hashlib
import heapq
import json
import math
import os
import shutil
import subprocess
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
import sys

import pcbnew as p

from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'usb-cc2-clearance.json').read_text())
source=root/meta['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==meta['sha256']
target=json.loads((root/'usb-selective-padfield.json').read_text())
assert target['source_sha256']==meta['sha256']
variant=int(sys.argv[1]) if len(sys.argv)>1 else 0
row=target['trials'][variant]
b=p.LoadBoard(str(source))
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
def vector(point):
    return p.VECTOR2I(*point)
def make_via(x,code):
    v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetWidth(450000);v.SetDrill(200000);v.SetPosition(vector(x));v.SetNetCode(code);return v
def make_track(a,z,l,code):
    t=p.PCB_TRACK(b);t.SetWidth(200000);t.SetLayer(l);t.SetStart(vector(a));t.SetEnd(vector(z));t.SetNetCode(code);return t
def endpoint(x,y):
    return (round(x*1e6),round(y*1e6))
# Each chain has two explicit terminals. Disallow any intermediate branch or retained pad.
chains=[('+3V3_AON',p.In3_Cu,endpoint(8.4,17.1),endpoint(8.4,23.35)),
        ('USB_CC1',p.F_Cu,endpoint(7.94,19),endpoint(10,18.4)),
        ('USB_CC1',p.B_Cu,endpoint(9.3,17),endpoint(11.6,20.85)),
        ('USB_CC2',p.F_Cu,endpoint(6.24,20.75),endpoint(9.6,19.15))]
all_tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
removed=set()
for net,layer,a,z in chains:
    graph=defaultdict(list)
    for t in all_tracks.values():
        if t.GetNetname()!=net:continue
        x,y=tuple(t.GetStart()),tuple(t.GetEnd())
        if isinstance(t,p.PCB_VIA):
            if net!='USB_CC2':continue
            u,w=(x,p.F_Cu),(x,p.B_Cu)
        else:
            l=t.GetLayer()
            if l!=layer and not (net=='USB_CC2' and l==p.B_Cu):continue
            u,w=(x,l),(y,l)
        uid=t.m_Uuid.AsString();graph[u].append((w,uid));graph[w].append((u,uid))
    start=(a,layer);end=(z,p.B_Cu if net=='USB_CC2' else layer)
    stack=[(start,[])];seen=set();path=None
    while stack:
        loc,edges=stack.pop()
        if loc in seen:continue
        seen.add(loc)
        if loc==end:path=edges;break
        for loc2,t in graph[loc]:
            if loc2 not in seen:stack.append((loc2,edges+[t]))
    assert path and len(path)>=3,(net,start,end)
    for uid in path:
        t=all_tracks[uid]
        assert (isinstance(t,p.PCB_VIA) or t.GetWidth()==200000)
        removed.add(uid)
for uid in sorted(removed):b.Remove(all_tracks[uid])
for net,parts in row['segments'].items():
    code=b.FindNet(net).GetNetCode()
    for o in parts:
        t=make_via(o['start'],code) if o['via'] else make_track(o['start'],o['end'],b.GetLayerID(o['layer']),code)
        b.Add(t)

def recover(net,l0,start,end):
    l1=p.B_Cu if net=='USB_CC2' else l0
    code=b.FindNet(net).GetNetCode()
    items=[k for k in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if k.GetNetCode()!=code and inflated_box(k,11000000).Contains(vector(start))]
    keep=list(b.Zones())+[zone for f in b.GetFootprints() for zone in f.Zones()]
    shapes={l:[(k.GetEffectiveShape(l),k.GetBoundingBox()) for k in items if k.IsOnLayer(l)] for l in layers}
    holes=[(k.GetEffectiveHoleShape(),k.GetPosition()) for k in items if isinstance(k,p.PCB_VIA)]
    areas={l:[z.Outline() for z in keep if z.IsOnLayer(l) and z.GetIsRuleArea() and z.GetDoNotAllowTracks()] for l in layers}
    vareas=[z.Outline() for z in keep if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    lands=[q.GetEffectiveShape(p.F_Cu) for q in b.FindFootprintByReference('J1').Pads()]
    t=make_track(start,end,l0,code);v=make_via(start,code)
    def free(s,box,l):
        return not (any(box.Intersects(bb) and s.Collide(o,202000) for o,bb in shapes[l]) or any(box.Contains(pos) and s.Collide(h,250000) for h,pos in holes))
    @lru_cache(None)
    def edge(a,z,l):
        t.SetLayer(l);t.SetStart(vector(a));t.SetEnd(vector(z));s=t.GetEffectiveShape(l)
        return free(s,inflated_box(t,365000),l) and not any(k.Collide(s,0) for k in areas[l])
    @lru_cache(None)
    def barrel(at):
        v.SetPosition(vector(at));s=v.GetEffectiveShape(p.F_Cu);h=v.GetEffectiveHoleShape();box=inflated_box(v,365000)
        return (not any(k.Collide(s,0) for k in vareas) and not any(s.Collide(land,100000) for land in lands) and
                all(free(s,box,l) and not any(box.Intersects(bb) and h.Collide(o,250000) for o,bb in shapes[l]) for l in layers))
    step=50000
    initial=tuple(round(c/step)*step for c in start);final=tuple(round(c/step)*step for c in end)
    assert edge(start,initial,l0) and edge(final,end,l1),(net,start,end)
    st=(initial,l0);goal=(final,l1);dist={st:0};prev={};queue=[(math.dist(initial,final),0,st)]
    while queue:
        _,d,node=heapq.heappop(queue)
        if d!=dist[node]:continue
        if node==goal:break
        at,l=node
        candidates=[]
        for dx,dy in ((1,0),(0,1),(-1,0),(0,-1),(1,1),(-1,-1),(-1,1),(1,-1)):
            pt=(at[0]+dx*step,at[1]+dy*step)
            if not (5000000<=pt[0]<=14000000 and 14500000<=pt[1]<=25000000):continue
            if edge(at,pt,l):candidates.append(((pt,l),d+math.hypot(dx,dy)*step))
        if l!=l1 and barrel(at):candidates.append(((at,l1),d+700000))
        for n,nd in candidates:
            h=math.dist(n[0],final)
            if nd>=dist.get(n,math.inf) or nd+h>math.dist(initial,final)+6500000:continue
            dist[n]=nd;prev[n]=node;heapq.heappush(queue,(nd+h,nd,n))
    if goal not in dist:
        choices={}
        for (point,l),length in dist.items():
            if l!=l0:continue
            v.SetPosition(vector(point));sh=v.GetEffectiveShape(p.F_Cu);hole=v.GetEffectiveHoleShape()
            if any(area.Collide(sh,0) for area in vareas) or any(sh.Collide(land,100000) for land in lands):continue
            box=inflated_box(v,365000)
            block=set()
            for obj in items:
                if not box.Intersects(obj.GetBoundingBox()):continue
                for ly in layers:
                    if obj.IsOnLayer(ly) and (sh.Collide(obj.GetEffectiveShape(ly),202000) or hole.Collide(obj.GetEffectiveShape(ly),250000)):
                        block.add((obj.GetNetname(),'pad '+obj.GetNumber() if isinstance(obj,p.PAD) else obj.m_Uuid.AsString()))
            key=tuple(sorted(block))
            if key not in choices or length<choices[key][0]:choices[key]=(length,point)
        ranked=sorted(choices.items(),key=lambda kv:(len(kv[0]),kv[1][0]))
        return dict(net=net,visited=len(dist),found=False,nearest_via_conflicts=[dict(blockers=items,position_nm=point) for items,(_,point) in ranked[:8]])
    nodes=[goal]
    while nodes[-1]!=st:nodes.append(prev[nodes[-1]])
    nodes.reverse();nodes=[(start,l0)]+nodes+[(end,l1)]
    tracks=[]
    for (a,l),(z,l2) in zip(nodes,nodes[1:]):
        if l!=l2:tracks.append(make_via(a,code));continue
        if a==z:continue
        if tracks and not isinstance(tracks[-1],p.PCB_VIA) and tracks[-1].GetLayer()==l:
            earlier=tuple(tracks[-1].GetStart());d=(a[0]-earlier[0],a[1]-earlier[1]);e=(z[0]-a[0],z[1]-a[1])
            if d[0]*e[1]==d[1]*e[0] and d[0]*e[0]+d[1]*e[1]>0:
                tracks[-1].SetEnd(vector(z));continue
        tracks.append(make_track(a,z,l,code))
    for t in tracks:b.Add(t)
    return dict(net=net,visited=len(dist),found=True,length_mm=sum(t.GetLength() for t in tracks if not isinstance(t,p.PCB_VIA))/1e6)
rows=[]
for i in (3,1,2,0):
    rows.append(recover(*chains[i]));print(rows[-1],flush=True)
    if not rows[-1]['found']:break
result=dict(parent_sha256=meta['sha256'],variant=variant,trials=rows,adopted=False)
if len(rows)==4 and all(r['found'] for r in rows):
    folder=root/'runs'/('usb-restored-pair-'+str(variant));folder.mkdir(exist_ok=True)
    for filename in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/filename,folder/filename)
    output=folder/source.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(output),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(output)],check=True,capture_output=True)
    result['new_drc']=introduced(json.loads((source.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if not result['new_drc']:
        saved=p.LoadBoard(str(output));saved.BuildConnectivity();result['preservation']=verify_preservation(p.LoadBoard(str(source)),saved,replaced_copper=removed);assert not screen(saved)
        j=saved.FindFootprintByReference('J1')
        for name in ('6','7'):
            left,right=[j.FindPadByNumber(r+name) for r in ('A','B')]
            assert right.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(left)}
        result.update(board=str(output.relative_to(root)),sha256=hashlib.sha256(output.read_bytes()).hexdigest())
(root/('usb-restored-pair-'+str(variant)+'.json')).write_text(json.dumps(result,indent=2)+'\n')
os._exit(0)
