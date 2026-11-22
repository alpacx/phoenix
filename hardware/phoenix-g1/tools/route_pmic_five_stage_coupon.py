"""Clear only conflicts reported on the isolated PMIC floorplan and reconstruct switch power paths."""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import hashlib
import heapq
import json
import math
import os
import shutil
import subprocess
import sys
import pcbnew as p
from pcb_bounds import inflated_box
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-pmic-pwron-filter.json').read_text());src=root/meta['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
idx=next((int(x) for x in sys.argv[1:] if x.isdecimal()),0)
initial=root/f'runs/pmic-five-stage-rotated-{idx}'
layout=json.loads((initial/'placement.json').read_text());assert not layout['mount_conflicts'] and not any('courtyard' in key for key in layout['delta_counts'])
b=p.LoadBoard(str(initial/src.name));alltracks=list(b.GetTracks());byuid={t.m_Uuid.AsString():t for t in alltracks}
assert set(byuid)=={t.m_Uuid.AsString() for t in p.LoadBoard(str(src)).GetTracks()}
removed=set()
for issue in layout['native_delta']:
    if issue['kind'] in ('shorting_items','clearance','solder_mask_bridge','hole_clearance'):
        removed.update(uid for uid in issue['uids'] if uid in byuid)
def part(ref,n):return b.FindFootprintByReference(ref).FindPadByNumber(n)
# Rotating the package invalidates the complete old power-switch chain, even where
# an isolated retained segment happens not to touch the new copper.
for t in alltracks:
    if t.GetNetname() in {f'PMIC_SW{n}' for n in range(1,6)}:removed.add(t.m_Uuid.AsString())
# Native DRC on the rotated but still copper-populated coupon identifies these
# old PMIC input/feedback segments over the new BUCK2 and BUCK4 full-width exits.
sw_exits={'15580e60-5de3-46c9-a451-12447b0979aa':'+1V8_SYS','16e17f9c-ea6d-4f6e-8a94-9be4c5deea17':'+3V3_SYS','98440e80-1094-4194-948f-53cb64d452ac':'+3V3_SYS','dafdd263-dbc3-4bf2-91fe-b2f8f391b6f1':'+3V3_SYS'}
if idx==0:
    for uid,net in sw_exits.items():
        t=byuid[uid];assert t.GetNetname()==net and t.GetLayer()==p.F_Cu
        removed.add(uid)
for uid in removed:b.Remove(byuid[uid])
def make(a,z,w,code,l=p.F_Cu):
    t=p.PCB_TRACK(b);t.SetWidth(w);t.SetNetCode(code);t.SetLayer(l);t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));return t
def router(code,l,start,radius):
    objs=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if o.GetNetCode()!=code and inflated_box(o,radius).Contains(p.VECTOR2I(*start))]
    geom=[(o.GetEffectiveShape(l),o.GetBoundingBox()) for o in objs if o.IsOnLayer(l)]
    holes=[(o.GetEffectiveHoleShape(),o.GetPosition()) for o in objs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.IsOnLayer(l) and z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
    proto=make(start,start,200000,code,l)
    @lru_cache(None)
    def clear(a,z,w):
        proto.SetWidth(w);proto.SetStart(p.VECTOR2I(*a));proto.SetEnd(p.VECTOR2I(*z));s=proto.GetEffectiveShape(l);bb=inflated_box(proto,410000)
        return not(any(bb.Intersects(box) and s.Collide(g,202000) for g,box in geom) or any(bb.Contains(pt) and s.Collide(h,250000) for h,pt in holes) or any(s.Collide(k,0) for k in zones))
    return clear
def astar(starts,end,width,clear,maxlen):
    if not starts:return []
    step=25000;grid=lambda a:tuple(round(z/step)*step for z in a)
    dst=grid(end);dist={};prev={};q=[]
    if not clear(dst,end,width):return []
    for a,(cost,toe) in starts.items():
        g=grid(a)
        for dx,dy in ((0,0),(-1,0),(1,0),(0,1),(0,-1)):
            n=g[0]+dx*step,g[1]+dy*step;nc=cost+math.dist(a,n)
            if clear(a,n,width) and nc<dist.get(n,math.inf):
                dist[n]=nc;prev[n]=('start',a,toe);heapq.heappush(q,(nc+math.dist(n,dst),nc,n))
    while q:
        _,d,pt=heapq.heappop(q)
        if dist[pt]!=d:continue
        if pt==dst:
            path=[end,dst]
            while prev[path[-1]][0]!='start':path.append(prev[path[-1]])
            _,a,toe=prev[path[-1]];path.extend((a,toe));path.reverse();return path
        for dx,dy in ((1,0),(0,1),(-1,0),(0,-1),(1,1),(-1,1),(-1,-1),(1,-1)):
            n=(pt[0]+dx*step,pt[1]+dy*step);nd=d+step*math.hypot(dx,dy);f=nd+math.dist(n,dst)
            if f<=maxlen and nd<dist.get(n,math.inf) and clear(pt,n,width):dist[n]=nd;prev[n]=pt;heapq.heappush(q,(f,nd,n))
    return []
def compact(points):
    out=[]
    for a in points:
        if out and out[-1]==a:continue
        if len(out)>1:
            i,j=out[-2:];u=(j[0]-i[0],j[1]-i[1]);v=(a[0]-j[0],a[1]-j[1])
            if u[0]*v[1]==u[1]*v[0] and u[0]*v[0]+u[1]*v[1]>0:out.pop()
        out.append(a)
    return out
def switch(k,pin):
    q=part('U4',pin);target=part(f'L40{k}','1');code=q.GetNetCode();mid=q.GetPosition();ctr=b.FindFootprintByReference('U4').GetPosition()
    ax,ay=mid.x-ctr.x,mid.y-ctr.y
    nx,ny=(int(math.copysign(1,ax)),0) if abs(ax)>abs(ay) else (0,int(math.copysign(1,ay)))
    tx,ty=-ny,nx
    clear=router(code,p.F_Cu,tuple(mid),6500000)
    starts={};pinshape=q.GetEffectiveShape(p.F_Cu)
    for radial in (440000,445000,450000,455000):
      for lateral in (0,10000,-10000,20000,-20000):
        toe=(mid.x+nx*radial+tx*lateral,mid.y+ny*radial+ty*lateral)
        for length in range(200000,451000,50000):
            for skew in (0,50000,-50000,100000,-100000,175000,-175000,250000,-250000):
                a=(toe[0]+nx*length+tx*skew,toe[1]+ny*length+ty*skew)
                if math.dist(toe,a)<=500000 and clear(toe,a,200000) and clear(a,a,600000) and make(toe,a,200000,code).GetEffectiveShape(p.F_Cu).Collide(pinshape,0):
                    starts[a]=(math.dist(toe,a),toe)
    path=astar(starts,tuple(target.GetPosition()),600000,clear,5300000 if k==5 else 4300000)
    result=dict(stage=k,launch_options=len(starts),width_mm=.60,neck_width_mm=.20,geometry=bool(path))
    if not path:
        result['legal_flare_sites_nm']=list(starts)[:20]
        toe=(mid.x+nx*440000,mid.y+ny*440000);a=(toe[0]+nx*400000,toe[1]+ny*400000)
        checks=[('neck',make(toe,a,200000,code)),('flare',make(a,a,600000,code))]
        result['blocked_by']={}
        for name,test in checks:
            sh=test.GetEffectiveShape(p.F_Cu)
            result['blocked_by'][name]=[dict(net=o.GetNetname(),ref=o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.m_Uuid.AsString()) for o in list(b.GetTracks())+[p0 for f0 in b.GetFootprints() for p0 in f0.Pads()] if o.IsOnLayer(p.F_Cu) and o.GetNetCode()!=code and sh.Collide(o.GetEffectiveShape(p.F_Cu),202000)]
        return result
    neck=make(path[0],path[1],200000,code);b.Add(neck)
    main=compact(path[1:]);wide=[make(a,z,600000,code) for a,z in zip(main,main[1:])]
    for t in wide:b.Add(t)
    result.update(segments_nm=[path[0]]+main,neck_length_mm=neck.GetLength()/1e6,wide_length_mm=sum(t.GetLength() for t in wide)/1e6)
    return result
def reserve_input(k,n):
    pin=part('U4',n);code=pin.GetNetCode();pos=pin.GetPosition();centre=b.FindFootprintByReference('U4').GetPosition()
    dx,dy=pos.x-centre.x,pos.y-centre.y
    nx,ny=(1 if dx>0 else -1,0) if abs(dx)>abs(dy) else (0,1 if dy>0 else -1)
    sw=part('U4',{1:'12',2:'9',3:'25',4:'65',5:'53'}[k]).GetPosition()-pos
    tangent=1 if (-ny*sw.x+nx*sw.y)<0 else -1
    tx,ty=-ny*tangent,nx*tangent;cap=part(f'C42{k}','1').GetPosition()
    widths={1:(127000,740000),2:(127000,740000),3:(127000,940000),4:(150000,590000),5:(127000,685000)}
    width,maxneck=widths[k];safe=router(code,p.F_Cu,tuple(pos),2500000);options=[]
    def loc(out,tan):return pos.x+nx*out+tx*tan,pos.y+ny*out+ty*tan
    for startoff in (250000,320000,360000,390000):
        start=loc(startoff,0)
        for turnoff in (390000,420000,460000,490000):
            if turnoff<=startoff:continue
            turn=loc(turnoff,0)
            for out in (700000,800000,850000,925000):
                for shift in (95000,145000,200000,250000,300000):
                    z=loc(out,shift);length=math.dist(start,turn)+math.dist(turn,z)
                    if length>maxneck or not safe(start,turn,width) or not safe(turn,z,width):continue
                    for ext in (100000,200000,300000):
                        tip=loc(out+ext,shift)
                        if not safe(z,tip,500000):continue
                        seed=make(start,turn,width,code)
                        if not seed.GetEffectiveShape(p.F_Cu).Collide(pin.GetEffectiveShape(p.F_Cu),0):continue
                        options.append((math.dist(tip,tuple(cap))+length+ext,[(start,turn,width),(turn,z,width),(z,tip,500000)]))
    if not options:return dict(stage=k,connected=False)
    # Select a supply flare only when the neighboring phase pin retains a full
    # 0.20 mm escape with a 0.60 mm flare. Keep the QFN pin-level pair together.
    switch_pin=part('U4',{1:'12',2:'9',3:'25',4:'65',5:'53'}[k])
    switch_pos=switch_pin.GetPosition();sc=switch_pin.GetNetCode();sw_safe=router(sc,p.F_Cu,tuple(switch_pos),2300000)
    starts=[]
    for off in (440000,450000,455000):
      for skew0 in (0,-10000,-20000,10000):
        toe=(switch_pos.x+nx*off+tx*skew0,switch_pos.y+ny*off+ty*skew0)
        for dist in (225000,300000,375000,450000):
          for bias in (0,-50000,-100000,-175000,-250000):
            end=(toe[0]+nx*dist+tx*bias,toe[1]+ny*dist+ty*bias)
            w=make(toe,end,200000,sc)
            if math.dist(toe,end)<=500000 and sw_safe(toe,end,200000) and sw_safe(end,end,600000) and w.GetEffectiveShape(p.F_Cu).Collide(switch_pin.GetEffectiveShape(p.F_Cu),0):
                starts.append((w.GetEffectiveShape(p.F_Cu),make(end,end,600000,sc).GetEffectiveShape(p.F_Cu)))
    lines=None
    for _,candidate in sorted(options,key=lambda o:o[0]):
        sh=[make(a,z,w,code).GetEffectiveShape(p.F_Cu) for a,z,w in candidate]
        if any(not any(s.Collide(g,202000) for s in arm for g in sh) for arm in starts):
            lines=candidate;break
    if lines is None:return dict(stage=k,connected=False,supply_options=len(options),switch_options=len(starts))
    for a,z,w in lines:b.Add(make(a,z,w,code))
    return dict(stage=k,connected=True,width_nm=width,lines_nm=lines,terminal_nm=lines[-1][1])
reserve='--reserve-vcc' in sys.argv
def shared_input():
    q,z=part('U4','11'),part('U4','10');a=q.GetPosition();b0=z.GetPosition();mid=((a.x+b0.x)//2,(a.y+b0.y)//2);code=q.GetNetCode()
    centre=b.FindFootprintByReference('U4').GetPosition();dx,dy=mid[0]-centre.x,mid[1]-centre.y
    nx,ny=(1 if dx>0 else -1,0) if abs(dx)>abs(dy) else (0,1 if dy>0 else -1)
    tx,ty=(b0.x-a.x)//350000,(b0.y-a.y)//350000;assert math.hypot(tx,ty)==1
    clear=router(code,p.F_Cu,mid,2900000)
    for inside in (150000,200000,250000,300000):
        x=(a.x+tx*45000+nx*inside,a.y+ty*45000+ny*inside);y=(b0.x-tx*45000+nx*inside,b0.y-ty*45000+ny*inside)
        node=(mid[0]+nx*inside,mid[1]+ny*inside)
        if not clear(x,y,200000):continue
        for length in (1150000,1050000,950000,850000):
            tip=(mid[0]+nx*length,mid[1]+ny*length)
            if not clear(node,tip,350000):continue
            lines=[(x,node,200000),(node,y,200000),(node,tip,350000)]
            for u,v,w in lines:b.Add(make(u,v,w,code))
            return dict(connected=True,common_width_mm=.35,terminal_nm=tip,lines_nm=lines)
    return dict(connected=False)
def transplant_fifth_fanout():
    original=p.LoadBoard(str(src));old_package=original.FindFootprintByReference('U4');new_package=b.FindFootprintByReference('U4')
    shift=(new_package.GetOrientationDegrees()-old_package.GetOrientationDegrees())%360
    assert abs(shift-270)<1e-5
    ox,oy=old_package.GetPosition();ux,uy=new_package.GetPosition()
    def mapxy(pt):return ux-(pt[1]-oy),uy+(pt[0]-ox)
    nets=[('PMIC_SW5',[(62450000,5590000),(62450000,5600000),(62450000,4950000),(62475000,4950000),(62475000,4150000)]),('+3V3_SYS',[(62100000,5590000),(62100000,5600000),(62100000,4925000),(62125000,4900000),(62125000,4550000),(61575000,4000000)])]
    existing={(t.GetNetname(),frozenset((tuple(t.GetStart()),tuple(t.GetEnd())))) for t in original.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu and t.GetWidth()==127000}
    add=[];ports={};block=[]
    for net,pts in nets:
        code=b.FindNet(net).GetNetCode();chain=list(map(mapxy,pts))
        safe=router(code,p.F_Cu,chain[0],4000000)
        for (old_a,old_z),(a,z) in zip(zip(pts,pts[1:]),zip(chain,chain[1:])):
            assert (net,frozenset((old_a,old_z))) in existing
            t=make(a,z,127000,code)
            if not safe(a,z,127000):
                sh=t.GetEffectiveShape(p.F_Cu)
                obs=[(o.GetNetname(),o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.m_Uuid.AsString()) for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if o.IsOnLayer(p.F_Cu) and o.GetNetCode()!=code and sh.Collide(o.GetEffectiveShape(p.F_Cu),202000)]
                block.append((net,a,z,obs))
            add.append(t)
        ports[net]=chain[-1]
    if not block:
        for t in add:b.Add(t)
    return dict(connected=not block,ports=ports,blockers=block)
fifth='--original-fanout' in sys.argv
fifth_shift='--shift-fifth' in sys.argv
shift_result=None
if fifth_shift:
    inductor=b.FindFootprintByReference('L405');start_xy=inductor.GetPosition()
    candidates=sorted([(dx*100000,dy*100000) for dx in range(-4,16) for dy in range(-6,12)],key=lambda d:math.hypot(*d))
    courts=[f.GetCourtyard(p.F_Cu) for f in b.GetFootprints() if f.GetLayer()==p.F_Cu and f.GetReference()!='L405' and inflated_box(f,4000000).Contains(start_xy)]
    rc=router(inductor.FindPadByNumber('1').GetNetCode(),p.F_Cu,tuple(start_xy),4000000)
    # Reserve the old QFN input escape before choosing the new inductor pose.
    rail=b.FindNet('+3V3_SYS').GetNetCode()
    wires=[make(x,z,127000,rail) for x,z in [((64100000,11125000),(64450000,11125000)),((64450000,11125000),(65000000,10575000))]]
    for dx,dy in candidates:
        inductor.SetPosition(start_xy+p.VECTOR2I(dx,dy));sh=inductor.FindPadByNumber('1').GetEffectiveShape(p.F_Cu)
        if any(sh.Collide(w.GetEffectiveShape(p.F_Cu),202000) for w in wires):continue
        if any(inductor.GetCourtyard(p.F_Cu).Collide(c,100000) for c in courts) or screen(b):continue
        # Reject any new old-copper interaction on either land before saving.
        clean=True
        for q in inductor.Pads():
            others=[o for o in list(b.GetTracks())+[a for f in b.GetFootprints() if f.GetReference()!='L405' for a in f.Pads()] if o.GetNetCode()!=q.GetNetCode() and o.IsOnLayer(p.F_Cu) and inflated_box(o,1600000).Contains(q.GetPosition())]
            if any(q.GetEffectiveShape(p.F_Cu).Collide(o.GetEffectiveShape(p.F_Cu),202000) for o in others):clean=False;break
        if clean:shift_result=(dx,dy);break
    if shift_result is None:inductor.SetPosition(start_xy)
old_fan=transplant_fifth_fanout() if fifth else {}
shared=shared_input() if reserve else {}
power_taps=[dict(stage=k,**shared) for k in (1,2)] if reserve and shared.get('connected') else []
power_taps += [reserve_input(k,n) for k,n in ((3,'24'),(1,'11'),(2,'10'),(4,'66'),(5,'54')) if not (k in (1,2) and shared.get('connected')) and not (k==5 and old_fan.get('connected'))] if reserve else []
results=[switch(k,n) for k,n in ((3,'25'),(1,'12'),(2,'9'),(4,'65'),(5,'53')) if not (k==5 and old_fan.get('connected'))]
if old_fan.get('connected'):
    start=old_fan['ports']['PMIC_SW5'];q=part('L405','1');finish=tuple(q.GetPosition());code=q.GetNetCode();safe=router(code,p.F_Cu,start,3000000)
    available=False;chosen_width=None
    for width in (600000,500000):
        if not safe(start,start,width):continue
        found=astar({start:(0,start)},finish,width,safe,2300000)
        if not found:continue
        main=compact(found)
        for x,y in zip(main,main[1:]):b.Add(make(x,y,width,code))
        available=True;chosen_width=width;break
    results.append(dict(stage=5,launch_options=1,geometry=available,reused_fanout=True,wide_width_nm=chosen_width))
    power_taps.append(dict(stage=5,connected=True,terminal_nm=old_fan['ports']['+3V3_SYS']))
folder=root/(f'runs/pmic-five-stage-new-inductor-{idx}' if fifth_shift else f'runs/pmic-five-stage-original-fanout-{idx}' if fifth else f'runs/pmic-five-stage-coupled-{idx}' if reserve else f'runs/pmic-five-stage-copper-{idx}');folder.mkdir(exist_ok=True)
for filename in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/filename,folder/filename)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
rep=json.loads((folder/'drc.json').read_text());delta=introduced(json.loads((src.parent/'drc.json').read_text()),rep);loaded=p.LoadBoard(str(out));loaded.BuildConnectivity()
for row in results:
    k=row['stage'];q=loaded.FindFootprintByReference('U4').FindPadByNumber({1:'12',2:'9',3:'25',4:'65',5:'53'}[k]);z=loaded.FindFootprintByReference(f'L40{k}').FindPadByNumber('1');row['native_connected']=z.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in loaded.GetConnectivity().GetConnectedItems(q)}
counts=Counter()
for r in delta:counts[r['type']]+=r['count']
state=dict(parent_sha256=meta['sha256'],placement_sha256=layout['sha256'],adopted=False,vcc_taps=power_taps,original_fifth_fanout=old_fan,fifth_shift_nm=shift_result,switches=results,removed_copper={u:dict(net=byuid[u].GetNetname(),start_nm=tuple(byuid[u].GetStart()),end_nm=tuple(byuid[u].GetEnd())) for u in sorted(removed)},delta_counts=dict(counts),board_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),mounts=screen(loaded))
(folder/'power-paths.json').write_text(json.dumps(state,indent=2)+'\n')
print([(r['stage'],r['connected']) for r in power_taps],len(removed),[(r['stage'],r['launch_options'],r['native_connected']) for r in results],counts,flush=True);os._exit(0)
