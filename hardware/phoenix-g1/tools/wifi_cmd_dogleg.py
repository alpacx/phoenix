"""Place the module CMD pull-up on its own side using a bounded multi-segment tap."""
from pathlib import Path
import hashlib,json,math,subprocess,shutil,os
import pcbnew as p
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'integrated-fixture-trunk.json').read_text());src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
import sys
capped='--capped' in sys.argv
inner='--inner' in sys.argv or capped
via_escape='--front' in sys.argv or inner
b=p.LoadBoard(str(src));f=b.FindFootprintByReference('R2014');mod=b.FindFootprintByReference('U25');q=mod.FindPadByNumber('16');origin=q.GetPosition();layer=p.F_Cu if via_escape and not inner else p.B_Cu
basegeom=geometry(b,layer,q.GetNetCode())
if f.GetLayer()!=layer:f.Flip(f.GetPosition(),False)
fp=[g for g in b.GetFootprints() if g.GetReference()!='R2014']
boxes=[g.GetCourtyard(layer).BBox() for g in fp if g.GetLayer()==layer and g.GetCourtyard(layer).BBox().Inflate(9000000).Contains(origin)]
obs=[(o.GetNetCode(),o.GetEffectiveShape(layer)) for o in list(b.GetTracks())+[pad for g in fp for pad in g.Pads()] if o.IsOnLayer(layer) and o.GetBoundingBox().Inflate(9000000).Contains(origin)]
goals={};choices={}
for angle in (0,90,180,270):
    f.SetOrientationDegrees(angle)
    for i in range(-22,23):
        for j in range(-12,25):
            pos=origin+p.VECTOR2I(i*200000,j*200000);f.SetPosition(pos)
            if any(f.GetCourtyard(layer).BBox().Intersects(z) for z in boxes):continue
            if any(pad.GetNetCode()!=n and pad.GetEffectiveShape(layer).Collide(s,200000) for pad in f.Pads() for n,s in obs):continue
            idx=str(len(goals));goals[idx]=tuple(f.FindPadByNumber('1').GetPosition());choices[idx]=(tuple(pos),angle)
print('placements',len(goals),flush=True)
# Search one F/B face without any transition. A second empty seed set is deliberately omitted.
pts=[tuple(origin+p.VECTOR2I(0,dy)) for dy in range(-450000,450001,50000)]
starts={}
if via_escape:
    near=[o for o in list(b.GetTracks())+[q for g in b.GetFootprints() if g.GetReference()!='R2014' for q in g.Pads()] if o.GetNetCode()!=q.GetNetCode() and o.GetBoundingBox().Inflate(4000000).Contains(origin)]
    layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
    shapes={l:[o.GetEffectiveShape(l) for o in near if o.IsOnLayer(l)] for l in layers}
    via=p.PCB_VIA(b);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetViaType(p.VIATYPE_THROUGH);via.SetWidth(450000);via.SetDrill(200000);via.SetNetCode(q.GetNetCode())
    for i in range(-30,31):
        for j in range(-30,31):
            end=origin+p.VECTOR2I(i*50000,j*50000);via.SetPosition(end)
            if any(via.GetEffectiveShape(l).Collide(s,200000) for l in layers for s in shapes[l]):continue
            if capped:
                if not q.GetBoundingBox().Contains(via.GetBoundingBox()):continue
            elif q.GetBoundingBox().Inflate(225000).Contains(end):continue
            for start in sorted(pts,key=lambda x:math.dist(x,tuple(end))):
                t=p.PCB_TRACK(b);t.SetLayer(p.B_Cu);t.SetWidth(200000);t.SetStart(p.VECTOR2I(*start));t.SetEnd(end)
                if not any(t.GetEffectiveShape(p.B_Cu).Collide(s,200000) for s in shapes[p.B_Cu]):
                    starts[tuple(end)]=start;break
    pts=list(starts)
secondary={}
if inner:
    basegeom=geometry(b,p.In3_Cu,q.GetNetCode())
    old_goals=goals;goals={}
    cache={}
    for idx,goal in old_goals.items():
        loc,angle=choices[idx];f.SetPosition(p.VECTOR2I(*loc));f.SetOrientationDegrees(angle)
        p1=f.FindPadByNumber('1');p2=f.FindPadByNumber('2')
        for dx,dy in [(i,j) for i in range(-6,7,2) for j in range(-6,7,2) if abs(i)+abs(j)>=6]:
            landing=(goal[0]+dx*150000,goal[1]+dy*150000)
            if landing not in cache:
                via.SetPosition(p.VECTOR2I(*landing))
                cache[landing]=all(not via.GetEffectiveShape(l).Collide(s,200000) for l in layers for s in shapes[l])
            if not cache[landing]:continue
            via.SetPosition(p.VECTOR2I(*landing))
            if any(via.GetEffectiveShape(layer).Collide(pad.GetEffectiveShape(layer),100000) for pad in (p1,p2)):continue
            trace=p.PCB_TRACK(b);trace.SetLayer(layer);trace.SetWidth(200000);trace.SetStart(p.VECTOR2I(*landing));trace.SetEnd(p1.GetPosition())
            if any(trace.GetEffectiveShape(layer).Collide(s,200000) for s in shapes[layer]+[p2.GetEffectiveShape(layer)]):continue
            key=idx+":"+str(dx)+","+str(dy);secondary[key]=idx;goals[key]=landing
    print('primary vias',len(starts),'secondary sites',len(goals),flush=True)
obj=dict(geometry=basegeom,goals=goals,seeds=pts,origin=tuple(origin))
search=Path(__file__).with_name('local_pad_grid.py')
sols=json.loads(subprocess.run(['python3',str(search)],input=json.dumps(obj),capture_output=True,text=True,check=True).stdout)
print('reachable',len(sols),flush=True)
records=[];held=[];tried=0
for sol in sols:
    loc,angle=choices[secondary[sol['index']] if inner else sol['index']];f.SetOrientationDegrees(angle);f.SetPosition(p.VECTOR2I(*loc))
    if any(r['ref']=='R2014' for r in screen(b)):continue
    traces=[]
    for a,z in zip(sol['path'],sol['path'][1:]):
        t=p.PCB_TRACK(b);t.SetNetCode(q.GetNetCode());t.SetWidth(200000);t.SetLayer(p.In3_Cu if inner else layer);t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));traces.append(t)
    if not inner and any(t.GetEffectiveShape(layer).Collide(f.FindPadByNumber('2').GetEffectiveShape(layer),200000) for t in traces):continue
    tried+=1
    if tried>16:break
    if inner:
        land=p.VECTOR2I(*sol['path'][-1]);v2=p.PCB_VIA(b);v2.SetLayerPair(p.F_Cu,p.B_Cu);v2.SetViaType(p.VIATYPE_THROUGH);v2.SetWidth(450000);v2.SetDrill(200000);v2.SetNetCode(q.GetNetCode());v2.SetPosition(land)
        t2=p.PCB_TRACK(b);t2.SetNetCode(q.GetNetCode());t2.SetWidth(200000);t2.SetLayer(layer);t2.SetStart(land);t2.SetEnd(f.FindPadByNumber('1').GetPosition());traces.extend([v2,t2])
    if via_escape:
        pos=tuple(sol['path'][0]);via.SetPosition(p.VECTOR2I(*pos))
        if via.GetEffectiveShape(layer).Collide(f.FindPadByNumber('2').GetEffectiveShape(layer),200000):continue
        t=p.PCB_TRACK(b);t.SetNetCode(q.GetNetCode());t.SetLayer(p.B_Cu);t.SetWidth(200000);t.SetStart(p.VECTOR2I(*starts[pos]));t.SetEnd(p.VECTOR2I(*pos))
        traces.extend([via,t])
    for t in traces:b.Add(t)
    dest=root/('runs/wifi-cmd-capped-path' if capped else 'runs/wifi-cmd-inner-path' if inner else 'runs/wifi-cmd-front-path' if via_escape else 'runs/wifi-cmd-dogleg');dest.mkdir(exist_ok=True)
    for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,dest/file)
    out=dest/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dest/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((dest/'drc.json').read_text()))
    if not delta:
        saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved)
        assert q.m_Uuid.AsString() in {t.m_Uuid.AsString() for t in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('R2014').FindPadByNumber('1'))}
        records.append(dict(preservation=pres,length_mm=sum(t.GetLength() for t in traces)/1e6))
        cp=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),records=records);break
    for t in traces:b.Remove(t);held.append(t)
(root/('wifi-cmd-capped-path.json' if capped else 'wifi-cmd-inner-path.json' if inner else 'wifi-cmd-front-path.json' if via_escape else 'wifi-cmd-dogleg.json')).write_text(json.dumps(dict(board=cp['board'],sha256=cp['sha256'],records=records,placements=len(goals),reachable=len(sols)),indent=2)+'\n')
print('accepted',bool(records),flush=True);os._exit(0)
