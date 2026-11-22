"""Place R8005 at the new H5 escape with a short branch and a real ground return."""
from pathlib import Path
from collections import Counter
import hashlib,json,math,shutil,subprocess
import pcbnew as p
from pcb_power_leg import make
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
r=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
parent=json.loads((r/'layout-recovery-adc-relocated.json').read_text());candidate=json.loads((r/'emmc-strobe-ca-pwm.json').read_text())
src=r/candidate['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==candidate['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
res=b.FindFootprintByReference('R8005')
v=next(t for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='EMMC_STRB')
at=tuple(v.GetPosition());near=inflated_box(v,6500000)
master=b.FindFootprintByReference('U4').FindPadByNumber('69')
gids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(master)}
fps=[f for f in b.GetFootprints() if f.GetReference()!='R8005']
objs=[o for o in [*b.GetTracks(),*(q for f in fps for q in f.Pads())] if near.Intersects(o.GetBoundingBox())]
holes=[(o.GetNetCode(),o.GetBoundingBox(),o.GetEffectiveHoleShape()) for o in objs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
stats=Counter();options=[];pos=lambda o:tuple(o.GetPosition())
for side in (p.F_Cu,p.B_Cu):
    if res.GetLayer()!=side:res.Flip(res.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
    q1=res.FindPadByNumber('1');q2=res.FindPadByNumber('2')
    geom=[(o.GetNetCode(),o.GetBoundingBox(),o.GetEffectiveShape(side)) for o in objs if o.IsOnLayer(side)]
    courts=[f.GetCourtyard(side) for f in fps if side==f.GetLayer() and near.Intersects(f.GetBoundingBox())]
    ground=set()
    for obj in objs:
        if not obj.IsOnLayer(side) or obj.m_Uuid.AsString() not in gids:continue
        if isinstance(obj,p.PAD) or isinstance(obj,p.PCB_VIA):ground.add(pos(obj));continue
        a,z=tuple(obj.GetStart()),tuple(obj.GetEnd());n=max(1,math.ceil(obj.GetLength()/300000))
        ground.update(tuple(round(u+(v-u)*i/n) for u,v in zip(a,z)) for i in range(n+1))
    zones=[z.Outline() for z in [*b.Zones(),*(z for f in fps for z in f.Zones())] if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(side)]
    def clear(o):
        sh=o.GetEffectiveShape(side);bb=inflated_box(o,300000)
        return not any(c!=o.GetNetCode() and bb.Intersects(box) and sh.Collide(g,202000) for c,box,g in geom) and not any(bb.Intersects(box) and sh.Collide(g,252000) for code,box,g in holes if code!=o.GetNetCode() or isinstance(o,p.PAD)) and not any(z.Collide(sh,0) for z in zones)
    for angle in (0,90,180,270):
        res.SetOrientationDegrees(angle)
        for i in range(-24,25):
         for j in range(-24,25):
            xy=at[0]+i*150000,at[1]+j*150000
            res.SetPosition(p.VECTOR2I(*xy))
            if math.dist(pos(q1),at)>3400000:continue
            court=res.GetCourtyard(side)
            if any(court.Collide(o,100000) for o in courts):continue
            stats['courtyard_fit']+=1
            if not all(clear(q) for q in res.Pads()):continue
            if any(q.GetEffectiveShape(side).Collide(v.GetEffectiveShape(side),100000) for q in res.Pads()):continue
            stats['lands_fit']+=1
            line=make(b,at,pos(q1),200000,q1.GetNetCode(),side)
            if not clear(line) or line.GetEffectiveShape(side).Collide(q2.GetEffectiveShape(side),202000):continue
            stats['strobe_reachable']+=1
            for gp in sorted(ground,key=lambda pt:math.dist(pt,pos(q2))):
                if math.dist(gp,pos(q2))>2400000:break
                ret=make(b,pos(q2),gp,250000,q2.GetNetCode(),side)
                if not clear(ret) or ret.GetEffectiveShape(side).Collide(q1.GetEffectiveShape(side),202000) or ret.GetEffectiveShape(side).Collide(line.GetEffectiveShape(side),202000):continue
                options.append((line.GetLength()+ret.GetLength(),side,angle,xy,gp));break
report=dict(parent_sha256=parent['sha256'],coupon_sha256=candidate['sha256'],stats=dict(stats),solutions=len(options))
(r/'emmc-strobe-pulldown-poses.json').write_text(json.dumps(report,indent=2)+'\n');print(stats,len(options),sorted(options)[:2])
out=r/'runs/emmc-strobe-pulldown';out.mkdir(exist_ok=True,parents=True)
for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),(out/src.name).with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table')
from audit_mount_component_reservations import screen
old=r/parent['board'];original_drc=json.loads((old.parent/'drc.json').read_text());attempts=[]
planes={p.F_Cu:next(z.GetFilledPolysList(p.In1_Cu) for z in b.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(p.In1_Cu)),p.B_Cu:next(z.GetFilledPolysList(p.In4_Cu) for z in b.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(p.In4_Cu))}
def rank(opt):
    length,side,angle,xy,gp=opt
    if res.GetLayer()!=side:res.Flip(res.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
    res.SetOrientationDegrees(angle);res.SetPosition(p.VECTOR2I(*xy));tip=pos(res.FindPadByNumber('1'))
    dist=math.dist(at,tip);count=max(1,math.ceil(dist/25000));missing=0
    for k in range(count):
        pt=p.VECTOR2I(*(round(u+(v-u)*(k+.5)/count) for u,v in zip(at,tip)))
        if not planes[side].Contains(pt):missing+=1
    return (round(dist*missing/count/25000),dist,length)
for _,side,angle,xy,gp in sorted(options,key=rank)[:8]:
    trial=p.LoadBoard(str(src));fp=trial.FindFootprintByReference('R8005')
    if fp.GetLayer()!=side:fp.Flip(fp.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(angle);fp.SetPosition(p.VECTOR2I(*xy))
    retired={'16758ef8-95d8-4812-80d4-826d10c17241','97144719-52a6-4ded-8f27-2c1b1b621ed6'}
    gone=[t for t in trial.GetTracks() if t.m_Uuid.AsString() in retired]
    assert len(gone)==2 and all(t.GetNetname()=='GND' and t.GetLayer()==p.B_Cu for t in gone)
    for t in gone:trial.Remove(t)
    for num,goal,width in [('1',at,200000),('2',gp,250000)]:
        q=fp.FindPadByNumber(num);trial.Add(make(trial,pos(q),goal,width,q.GetNetCode(),side))
    file=out/src.name;p.ZONE_FILLER(trial).Fill(trial.Zones());p.SaveBoard(str(file),trial)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(file)],capture_output=True,check=True)
    db=json.loads((out/'drc.json').read_text());delta=introduced(original_drc,db);attempts.append(dict(angle=angle,xy=xy,delta=delta))
    if delta:continue
    saved=p.LoadBoard(str(file));saved.BuildConnectivity()
    assert not any(o['ref']=='R8005' for o in screen(saved))
    proof=verify_preservation(p.LoadBoard(str(old)),saved,replaced_copper=set(candidate['preservation']['explicitly_replaced_copper'])|retired)
    report.update(board=str(file.relative_to(r)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),preservation=proof,remaining=len(db['unconnected_items']),selected=dict(layer=saved.GetLayerName(side),angle=angle,xy=xy,gp=gp))
    break
report['attempts']=attempts
(r/'emmc-strobe-pulldown-poses.json').write_text(json.dumps(report,indent=2)+'\n')
print(report.get('remaining'),attempts[:1])
