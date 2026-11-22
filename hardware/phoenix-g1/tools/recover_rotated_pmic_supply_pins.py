"""Reconnect a rotated PMIC pin to the existing wide system supply without narrowing its prior escape."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess,sys
import native_front_splice as splice
import pcbnew as p
from pcb_power_leg import make
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
bent='--bent-supply' in sys.argv
src_report=json.loads((root/('rotated-bypass-source-mixed.json' if bent else 'rotated-existing-scl-complete.json')).read_text());src=root/src_report['board'];orig_report=json.loads((root/'layout-pmic-pwron-filter.json').read_text());old=p.LoadBoard(str(root/orig_report['board']));digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
assert digest(src)==src_report['sha256'] and digest(root/orig_report['board'])==orig_report['sha256']
current=src;records=[];failed=[]
def uid(o):return o.m_Uuid.AsString()
def pin(b,r,n):return b.FindFootprintByReference(r).FindPadByNumber(n)
for n in (('30','22') if bent else ('45','33','30','24','22','4','57','66','10','54')):
    b=p.LoadBoard(str(current));b.BuildConnectivity();q=pin(b,'U4',n);oc=pin(old,'U4',n);net=q.GetNetname();code=q.GetNetCode()
    assert net=='+3V3_SYS'
    rail={uid(o) for o in b.GetConnectivity().GetConnectedItems(pin(b,'C1304','1'))}
    if uid(q) in rail:continue
    old_necks=[t for t in old.GetTracks() if not isinstance(t,p.PCB_VIA) and t.IsOnLayer(p.F_Cu) and t.GetNetname()==net and t.GetEffectiveShape(p.F_Cu).Collide(oc.GetEffectiveShape(p.F_Cu),0)]
    old_neck=min(old_necks,key=lambda t:t.GetWidth());minwidth=old_neck.GetWidth();maxlen=old_neck.GetLength()
    center=q.GetPosition();outer=center-b.FindFootprintByReference('U4').GetPosition()
    nx,ny=(int(math.copysign(1,outer.x)),0) if abs(outer.x)>abs(outer.y) else (0,int(math.copysign(1,outer.y)))
    def offset(d,s):return tuple(center+p.VECTOR2I(nx*d-ny*s,ny*d+nx*s))
    objects=[o for o in list(b.GetTracks())+[z for f in b.GetFootprints() for z in f.Pads()] if inflated_box(o,8500000).Contains(center)]
    geom=[(o.GetEffectiveShape(p.F_Cu),o.GetBoundingBox()) for o in objects if o.IsOnLayer(p.F_Cu) and o.GetNetCode()!=code]
    holes=[(o.GetEffectiveHoleShape(),o.GetPosition()) for o in objects if o.GetNetCode()!=code and (isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x)]
    keep=[z.Outline() for z in b.Zones() if z.IsOnLayer(p.F_Cu) and z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
    bb=b.GetBoardEdgesBoundingBox();bb.Inflate(-252000)
    def clear(t):
        shape=t.GetEffectiveShape(p.F_Cu);box=inflated_box(t,375000)
        return bb.Contains(t.GetBoundingBox()) and all(not box.Intersects(o) or not shape.Collide(s,202000) for s,o in geom) and all(not box.Contains(pos) or not shape.Collide(h,252000) for h,pos in holes) and all(not shape.Collide(k,0) for k in keep)
    main=set()
    for t in b.GetTracks():
        if uid(t) not in rail or isinstance(t,p.PCB_VIA) or t.GetLayer()!=p.F_Cu or t.GetWidth()<500000:continue
        x,y=tuple(t.GetStart()),tuple(t.GetEnd());count=max(1,math.ceil(t.GetLength()/175000))
        for i in range(count+1):
            pt=tuple(round(a+(z-a)*i/count) for a,z in zip(x,y))
            if math.dist(pt,tuple(center))<6300000:main.add(pt)
    openings=[]
    for sign in (1,-1):
        for w in sorted({minwidth,150000,200000,250000},reverse=True):
            if w<minwidth:continue
            for d in (200000,300000,350000,400000):
                for tangent in (0,40000,-40000):
                    a=offset(sign*d,tangent)
                    for length in (250000,350000,450000,550000,650000):
                        for skew in (0,100000,-100000,200000,-200000):
                            z=offset(sign*(d+length),skew)
                            neck=make(b,a,z,w,code,p.F_Cu)
                            if neck.GetLength()>maxlen or not neck.GetEffectiveShape(p.F_Cu).Collide(q.GetEffectiveShape(p.F_Cu),0) or not clear(neck):continue
                            if not clear(make(b,z,z,500000,code,p.F_Cu)):continue
                            openings.append((neck,z,w))
    best=None
    for neck,z,w in openings:
        for goal in main:
            dx,dy=goal[0]-z[0],goal[1]-z[1];m=min(abs(dx),abs(dy));ex=int(math.copysign(m,dx));ey=int(math.copysign(m,dy))
            for corner in ((z[0]+ex,z[1]+ey),(goal[0]-ex,goal[1]-ey)):
                segs=[make(b,a,h,500000,code,p.F_Cu) for a,h in zip((z,corner),(corner,goal)) if a!=h]
                if not segs:continue
                length=sum(t.GetLength() for t in segs)
                if length>6500000 or not all(clear(t) for t in segs):continue
                score=length+neck.GetLength()*500000/w
                if best is None or score<best[0]:best=(score,neck,segs,goal)
    if not best and bent:
        # Each unique neck endpoint must be wide enough for the 0.50 mm bus.
        # Retain exact contacts even when the tap lies under another same-net pad.
        by_point={}
        for neck,z,w in openings:
            previous=by_point.get(z)
            rank=neck.GetLength()/w
            if previous is None or rank<previous[0]:by_point[z]=(rank,neck,w)
        taps=[]
        for goal in sorted(main,key=lambda p:min((math.dist(p,z) for z in by_point),default=math.inf)):
            if all(math.dist(goal,t)>450000 for t in taps):taps.append(goal)
        for z,(_,neck,w) in by_point.items():
            for goal in taps:
                pts,info=splice.recover(b,[(z,goal,500000,code)],net,None,True,True,True)
                if not pts or info['length_mm']>6.5:continue
                segs=[make(b,u,v,500000,code,p.F_Cu) for u,v in zip(pts,pts[1:])]
                if not segs or not all(clear(s) for s in segs):continue
                score=info['length_mm']*1e6+neck.GetLength()*500000/w
                if best is None or score<best[0]:best=(score,neck,segs,goal)
    if not best:
        failed.append(dict(pin=n,prior_width_nm=minwidth,prior_length_nm=maxlen,legal_necks=len(openings),wide_targets=len(main)));continue
    _,neck,segs,goal=best
    for tr in [neck,*segs]:b.Add(tr)
    folder=root/'runs'/(('rotated-bent-system-pin-' if bent else 'rotated-sys-supply-pin-')+n);folder.mkdir(exist_ok=True)
    for cfg in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(current.parent/cfg,folder/cfg)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if delta:failed.append(dict(pin=n,new_drc=delta));continue
    prior=p.LoadBoard(str(current));saved=p.LoadBoard(str(out));guard=verify_preservation(prior,saved)
    assert uid(pin(saved,'U4',n)) in {uid(t) for t in saved.GetConnectivity().GetConnectedItems(pin(saved,'C1304','1'))} and not screen(saved)
    record=dict(pin=n,prior_neck_width_mm=minwidth/1e6,actual_neck_width_mm=neck.GetWidth()/1e6,prior_neck_length_mm=maxlen/1e6,actual_neck_length_mm=neck.GetLength()/1e6,trunk_mm=sum(t.GetLength() for t in segs)/1e6,trunk_width_mm=.5,tap_nm=goal,groups=guard['existing_connected_pad_groups_preserved'])
    records.append(record);meta=json.loads((current.parent/'output-legs.json').read_text());meta['board_sha256']=digest(out);meta['system_pin_feeds']=records;(folder/'output-legs.json').write_text(json.dumps(meta,indent=2)+'\n');current=out;print(n,record['trunk_mm'],flush=True)
(root/('rotated-bent-system-pins.json' if bent else 'rotated-system-supply-pins.json')).write_text(json.dumps(dict(parent_sha256=src_report['sha256'],board=str(current.relative_to(root)),sha256=digest(current),records=records,held=failed,assembly_ready=False),indent=2)+'\n');print('closed',len(records),'held',len(failed),flush=True);os._exit(0)
