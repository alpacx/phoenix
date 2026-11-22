"""Compare common-surface and symmetric two-via USB2 contact joins on a local coupon."""
from functools import lru_cache
from pathlib import Path
import hashlib
import heapq
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew as p

from pcb_bounds import inflated_box, point_distance_squared
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
release_cc2='--release-cc2-only' in sys.argv
pad_edges='--full-pad-edges' in sys.argv or release_cc2
cc2_cut={'0cd03017-7a47-435c-809c-0932accb433d','cd40213e-5cea-40d0-babe-8dc01d2c5f9d','fbd8e1cb-c4ff-4df4-afbf-80e74d3de64a','4b352c41-58d4-4276-a34f-6cade39070fc','91b792df-6f39-409d-9c58-8d573b6e17a1'}
keep_launch='--keep-launch' in sys.argv
keep_cc2='--keep-cc2' in sys.argv
keep_power='--keep-aon' in sys.argv
steer='--reserved-pair' in sys.argv
paired='--separate-mouths' in sys.argv
capped='--capped-launch' in sys.argv
diagnostic='--connector-only' in sys.argv
launch='--cc2-launch' in sys.argv or diagnostic
corridor='--corridor' in sys.argv or launch
meta=json.loads((root/('layout-npu-c434-paired-load.json' if pad_edges else 'usb-cc2-clearance.json' if launch else 'usb-contact-corridor.json' if corridor else 'layout-cpu-load-sense.json')).read_text())
src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
grid=50000
width=200000
split='--split-access' in sys.argv
limit=7200000 if split else 5600000
def solve(b,net,inner,via_count,contact=None,outer=None):
    j=b.FindFootprintByReference('J1')
    suffix='6' if net=='USB_DP' else '7'
    first,last=(j.FindPadByNumber(row+suffix) for row in ('B','A'))
    if contact is not None:first=j.FindPadByNumber(contact)
    center=first.GetPosition()
    target=tuple(last.GetPosition())
    geometry=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
    if steer:
        geometry=[o for o in geometry if isinstance(o,p.PAD) or (keep_launch and o.GetNetname()=='USB_CC2' and o.IsOnLayer(p.F_Cu)) or o.GetNetname() not in (('USB_CC1','USB_CC2') if keep_power else ('USB_CC1','+3V3_AON') if keep_cc2 else ('USB_CC1','USB_CC2','+3V3_AON'))]
    elif diagnostic:
        geometry=[o for o in geometry if isinstance(o,p.PAD) or o.GetNetname() in ('USB_DP','USB_DM')]
    obs=[o for o in geometry if o.GetNetname()!=net and inflated_box(o,6000000).Contains(center)]
    copper={l:[(o.GetEffectiveShape(l),o.GetBoundingBox()) for o in obs if o.IsOnLayer(l)] for l in layers}
    holes=[(o.GetEffectiveHoleShape(),o.GetPosition()) for o in obs if isinstance(o,p.PCB_VIA)]
    lands=[q.GetEffectiveShape(p.F_Cu) for q in j.Pads() if not (capped and q.GetNetname()==net)]
    zones=list(b.Zones())+[zone for f in b.GetFootprints() for zone in f.Zones()]
    reserve={l:[z.Outline() for z in zones if z.GetIsRuleArea() and z.IsOnLayer(l) and z.GetDoNotAllowTracks()] for l in layers}
    viarules=[z.Outline() for z in zones if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    line=p.PCB_TRACK(b);line.SetWidth(width)
    v=p.PCB_VIA(b);v.SetWidth(450000);v.SetDrill(200000);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu)
    def clear(obj,l):
        s=obj.GetEffectiveShape(l);box=inflated_box(obj,351000)
        return not (any(box.Intersects(bb) and s.Collide(t,202000) for t,bb in copper[l]) or any(box.Contains(pos) and s.Collide(h,250000) for h,pos in holes))
    @lru_cache(None)
    def edge(l,u,z):
        line.SetLayer(l);line.SetStart(p.VECTOR2I(*u));line.SetEnd(p.VECTOR2I(*z))
        return clear(line,l) and not any(keep.Collide(line.GetEffectiveShape(l),0) for keep in reserve[l])
    @lru_cache(None)
    def barrel(pt):
        v.SetPosition(p.VECTOR2I(*pt));shape=v.GetEffectiveShape(p.F_Cu);hole=v.GetEffectiveHoleShape()
        if any(shape.Collide(land,100000) for land in lands) or any(keep.Collide(shape,0) for keep in viarules):return False
        for l in layers:
            if not clear(v,l) or any(point_distance_squared(box,v.GetPosition())<500000**2 and hole.Collide(t,250000) for t,box in copper[l]):return False
        return True
    if contact:
        rootpt=tuple(center)
        parents={};best={rootpt:0};queue=[(0,rootpt)];landings=[]
        while queue:
            d,pt=heapq.heappop(queue)
            if d!=best[pt]:continue
            if barrel(pt):
                steps=[pt];cur=pt
                while cur in parents:cur=parents[cur];steps.append(cur)
                landings.append(dict(site_nm=pt,path_nm=list(reversed(steps)),length_mm=d/1e6))
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
                nxt=(pt[0]+dx*grid,pt[1]+dy*grid)
                nd=d+grid*math.hypot(dx,dy)
                if nd>2000000 or nd>=best.get(nxt,math.inf) or not edge(p.F_Cu,pt,nxt):continue
                best[nxt]=nd;parents[nxt]=pt;heapq.heappush(queue,(nd,nxt))
        return landings,len(best)
    def push(node,length,prev):
        pt,l,n=node
        h=math.dist(pt,target)
        # Keep the fork within the connector neighborhood.
        if length+h>limit+via_count*800000 or length>=best.get(node,math.inf):return
        best[node]=length;parents[node]=prev;heapq.heappush(queue,(length+h,length,node))
    start=tuple(center)
    queue=[];best={};parents={}
    if pad_edges:
        for i in range(-7,8):
            for j in range(-3,4):
                at=(start[0]+i*grid,start[1]+j*grid)
                if first.GetEffectiveShape(p.F_Cu).Collide(p.VECTOR2I(*at),0) and edge(p.F_Cu,at,at):push((at,p.F_Cu,0),0,None)
    else:push((start,p.F_Cu,0),0,None)
    while queue:
        _,cost,node=heapq.heappop(queue)
        if cost!=best[node]:continue
        pt,l,n=node
        if l==p.F_Cu and n==via_count and (pt==target or pad_edges and last.GetEffectiveShape(p.F_Cu).Collide(p.VECTOR2I(*pt),0)):
            nodes=[]
            while node is not None:
                nodes.append(node);node=parents[node]
            nodes.reverse()
            parts=[]
            for (a,oldl,_),(z,newl,_) in zip(nodes,nodes[1:]):
                if oldl!=newl:
                    k=p.PCB_VIA(b);k.SetWidth(450000);k.SetDrill(200000);k.SetViaType(p.VIATYPE_THROUGH);k.SetLayerPair(p.F_Cu,p.B_Cu);k.SetPosition(p.VECTOR2I(*a))
                else:
                    if parts and not isinstance(parts[-1],p.PCB_VIA) and parts[-1].GetLayer()==oldl:
                        prev=parts[-1].GetStart();d=p.VECTOR2I(*a)-prev;e=p.VECTOR2I(*z)-p.VECTOR2I(*a)
                        if d.x*e.y==d.y*e.x and d.x*e.x+d.y*e.y>0:
                            parts[-1].SetEnd(p.VECTOR2I(*z));continue
                    k=p.PCB_TRACK(b);k.SetLayer(oldl);k.SetWidth(width);k.SetStart(p.VECTOR2I(*a));k.SetEnd(p.VECTOR2I(*z))
                k.SetNetCode(first.GetNetCode());parts.append(k)
            return parts,len(best)
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
            nxt=(pt[0]+dx*grid,pt[1]+dy*grid)
            if not (4120000<=nxt[0]<=9980000 and 17300000<=nxt[1]<=22700000):continue
            if edge(l,pt,nxt):push((nxt,l,n),cost+grid*math.hypot(dx,dy),node)
        transition_near_contact=(n==0 and pt[0]<=(7800000 if launch else 6450000)) or (n==1 and pt[0]>=7100000)
        if split and n==1 and outer is not None:
            transition_near_contact=transition_near_contact and ((pt[0]>8500000) if outer else (pt[0]<7800000))
        if paired:
            if n==0:
                transition_near_contact=(pt[0]<7500000 and ((pt[1]>=19800000 if net=='USB_DP' else pt[1]<=19300000) if keep_cc2 else ((pt[0]>=7380000 and pt[1]>=19900000) if net=='USB_DP' else pt[1]<=19550000) if keep_launch else (pt[1]>=20200000 if net=='USB_DP' else pt[1]<=19800000)))
            else:
                transition_near_contact=(pt[0]>8400000 and (keep_cc2 or (pt[1]<=19600000 if net=='USB_DP' else pt[1]>=20400000)))
        if n<via_count and (pad_edges or transition_near_contact) and barrel(pt):
            # A layer change must make forward progress on the inner layer.
            previous=parents[node]
            if (previous and previous[1]==l) or (capped and previous is None):
                push((pt,inner if l==p.F_Cu else p.F_Cu,n+1),cost+800000,node)
    return [],len(best)

if '--landings' in sys.argv:
    board=p.LoadBoard(str(src))
    landings={}
    for name,net in [('A6','USB_DP'),('B6','USB_DP'),('A7','USB_DM'),('B7','USB_DM')]:
        found,visited=solve(board,net,p.In2_Cu,2,contact=name)
        distinct=[]
        for row in found:
            if all(math.dist(row['site_nm'],base['site_nm'])>150000 for base in distinct):distinct.append(row)
        landings[name]=dict(visited=visited,count=len(found),options=distinct)
    (root/('usb-padfield-landings.json' if diagnostic else 'usb-capped-landings.json' if capped else 'usb-cc2-landings.json' if launch else 'usb-protected-corridor-landings.json' if corridor else 'usb-contact-landings.json')).write_text(json.dumps(dict(source_sha256=meta['sha256'],contacts=landings,exit_length_limit_mm=2),indent=2)+'\n')
    print([(n,r['count'],len(r['options'])) for n,r in landings.items()],flush=True)
    os._exit(0)
case=next((int(a.split('=')[1]) for a in sys.argv if a.startswith('--case=')),None);attempt=0
cross=next((n.split('=')[1] for n in sys.argv if n.startswith('--cross-layer=')),None)
rows=[]
for primary,secondary,inside1,inside2 in ([(2,2,p.In2_Cu,p.In3_Cu),(2,2,p.In3_Cu,p.In2_Cu),(2,0,p.In2_Cu,p.In2_Cu),(0,2,p.In2_Cu,p.In2_Cu)] if split else [(0,0,p.In2_Cu,p.In2_Cu),(2,2,p.In2_Cu,p.In2_Cu),(2,2,p.In2_Cu,p.In3_Cu),(0,2,p.In2_Cu,p.In2_Cu),(2,0,p.In2_Cu,p.In2_Cu)]):
    for direction in [('USB_DP','USB_DM'),('USB_DM','USB_DP')]:
        if cross:
            other={'In3':p.In3_Cu,'back':p.B_Cu}[cross];inside1=other;inside2=other
        attempt+=1
        if case is not None and attempt!=case:continue
        b=p.LoadBoard(str(src))
        if release_cc2:
            remove=[t for t in b.GetTracks() if t.m_Uuid.AsString() in cc2_cut]
            assert len(remove)==5 and all(t.GetNetname()=='USB_CC2' for t in remove)
            for t in remove:b.Remove(t)
        row=dict(vias_per_signal=[primary,secondary],order=direction,inside=[b.GetLayerName(inside1),b.GetLayerName(inside2)],signals=[])
        rows.append(row)
        for net,layer,vias in zip(direction,(inside1,inside2),(primary,secondary)):
            parts,count=solve(b,net,layer,vias,outer=(net==direction[0] if primary and secondary else True))
            if not parts:
                row['signals'].append(dict(net=net,visited=count,route=False));break
            for k in parts:b.Add(k)
            row['signals'].append(dict(net=net,route=True,length_mm=sum(k.GetLength() for k in parts if not isinstance(k,p.PCB_VIA))/1e6,barrels_nm=[tuple(k.GetPosition()) for k in parts if isinstance(k,p.PCB_VIA)]))
        else:
            if diagnostic:
                row['original_copper_conflicts']={}
                for net in direction:
                    reference_board=p.LoadBoard(str(src))
                    original_ids={t.m_Uuid.AsString() for t in reference_board.GetTracks()}
                    parts=[t for t in b.GetTracks() if t.GetNetname()==net and t.m_Uuid.AsString() not in original_ids]
                    row.setdefault('segments',{})[net]=[dict(layer=b.GetLayerName(t.GetLayer()),start=list(t.GetStart()),end=list(t.GetEnd()),via=isinstance(t,p.PCB_VIA)) for t in parts]
                    conflicts=set()
                    for t in parts:
                        for original in b.GetTracks():
                            if original.GetNetname() in ('USB_DM','USB_DP'):continue
                            for layer in layers:
                                if t.IsOnLayer(layer) and original.IsOnLayer(layer) and t.GetEffectiveShape(layer).Collide(original.GetEffectiveShape(layer),202000):
                                    conflicts.add((original.GetNetname(),original.m_Uuid.AsString()))
                    row['original_copper_conflicts'][net]=sorted(conflicts)
                (root/('usb-fixed-launch-padfield.json' if keep_launch else 'usb-fixed-cc2-padfield.json' if keep_cc2 else 'usb-cc-only-padfield.json' if keep_power else 'usb-selective-padfield.json' if steer else 'usb-padfield-feasibility.json')).write_text(json.dumps(dict(source_sha256=meta['sha256'],trials=rows,adopted=False,unrestricted_existing_tracks=True),indent=2)+'\n')
                print(row['original_copper_conflicts'],flush=True)
                continue
            row['skew_mm']=abs(row['signals'][0]['length_mm']-row['signals'][1]['length_mm'])
            folder=root/'runs'/(('usb-full-edges-cc2-released-' if release_cc2 else 'usb-full-pad-edges-' if pad_edges else 'usb-capped-span-' if capped else 'usb-cc2-split-span-' if launch and split else 'usb-cc2-span-' if launch else 'usb-split-span-' if split else 'usb-corridor-span-' if corridor else 'usb-contact-span-')+str(attempt));folder.mkdir(exist_ok=True)
            for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/n,folder/n)
            out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
            subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
            row['new_drc']=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
            saved=p.LoadBoard(str(out));saved.BuildConnectivity()
            if not release_cc2:verify_preservation(p.LoadBoard(str(src)),saved)
            else:row['pending_restore']=sorted(cc2_cut)
            assert not screen(saved)
            for n in ('6','7'):
                j=saved.FindFootprintByReference('J1');a,z=[j.FindPadByNumber(r+n) for r in ('A','B')]
                assert z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(a)}
            row.update(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest())
        if diagnostic:
            (root/('usb-fixed-launch-padfield.json' if keep_launch else 'usb-fixed-cc2-padfield.json' if keep_cc2 else 'usb-cc-only-padfield.json' if keep_power else 'usb-selective-padfield.json' if steer else 'usb-padfield-feasibility.json')).write_text(json.dumps(dict(source_sha256=meta['sha256'],trials=rows,adopted=False,unrestricted_existing_tracks=True),indent=2)+'\n')
            continue
        (root/('usb-full-edges-cc2-case-'+str(case)+('-'+cross if cross else '')+'.json' if release_cc2 and case is not None else 'usb-full-edges-cc2-released.json' if release_cc2 else 'usb-full-pad-edges-topologies.json' if pad_edges else 'usb-capped-topologies.json' if capped else 'usb-cc2-split-topologies.json' if launch and split else 'usb-cc2-topologies.json' if launch else 'usb-protected-split-topologies.json' if split else 'usb-corridor-topologies.json' if corridor else 'usb-contact-topologies.json')).write_text(json.dumps(dict(source_sha256=meta['sha256'],width_mm=.2,grid_mm=.05,max_local_path_mm=limit/1e6,via_land_drill_mm=[.45,.20],trials=rows,impedance_qualified=False,adopted=False),indent=2)+'\n')
        print(row['vias_per_signal'],row['order'],[s.get('length_mm') for s in row['signals']],flush=True)
os._exit(0)
