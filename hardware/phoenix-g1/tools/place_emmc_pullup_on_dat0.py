"""Place the DAT0 pull-up where its rail and the eMMC DAT0 ball are both reachable."""
import hashlib,heapq,json,math,shutil,subprocess,sys
from collections import defaultdict,Counter
from functools import lru_cache
from pathlib import Path
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((root/(n+'.json')).read_text())
from_launch='--from-launch' in sys.argv
cp=read('emmc-d0-socket-launch')['candidate'] if from_launch else read('emmc-vccq-moved-link-source');src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));before=p.LoadBoard(str(src));b.BuildConnectivity()
fp=b.FindFootprintByReference('R8001'); supply=fp.FindPadByNumber('1'); data=fp.FindPadByNumber('2')
pin=b.FindFootprintByReference('U8001').FindPadByNumber('A3');bank=b.FindFootprintByReference('C8002').FindPadByNumber('1')
v=lambda k:p.VECTOR2I(*k);uid=lambda o:o.m_Uuid.AsString()
side=p.B_Cu;cell=1000000;step=100000
others=[f for f in b.GetFootprints() if f.GetReference()!='R8001']
objs=[*b.GetTracks(),*(q for f in others for q in f.Pads())]
def tiles(box):
    return ((x,y) for x in range(box.GetLeft()//cell,box.GetRight()//cell+1) for y in range(box.GetTop()//cell,box.GetBottom()//cell+1))
index=defaultdict(list)
for o in objs:
    shape=o.GetEffectiveShape(side) if o.IsOnLayer(side) else None
    hole=o.GetEffectiveHoleShape() if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x else None
    if shape or hole:
        for key in tiles(inflated_box(o,700000)):index[key].append((o.GetNetCode(),shape,hole))
keep=[z.Outline() for z in [*b.Zones(),*(z for f in others for z in f.Zones())] if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(side)]
def clear(item):
    shape=item.GetEffectiveShape(side);checked=set()
    for key in tiles(item.GetBoundingBox()):
        for net,body,hole in index[key]:
            identity=id(body),id(hole)
            if identity in checked:continue
            checked.add(identity)
            if body and net!=item.GetNetCode() and shape.Collide(body,202000) or hole and shape.Collide(hole,252000):return False
    return not any(shape.Collide(g,0) for g in keep)
def frontier(pad,width,limit):
    code=pad.GetNetCode()
    connected={uid(o) for o in b.GetConnectivity().GetConnectedItems(pad)}
    samples=set()
    for o in objs:
        if uid(o) not in connected or not o.IsOnLayer(side):continue
        if isinstance(o,(p.PAD,p.PCB_VIA)):
            x,y=o.GetPosition()
            samples.update((x+i,y+j) for i in (-100000,0,100000) for j in (-100000,0,100000) if o.HitTest(v((x+i,y+j))))
        elif o.GetWidth()>=width:
            count=max(1,math.ceil(o.GetLength()/150000))
            samples.update(tuple(round(a+(z-a)*i/count) for a,z in zip(o.GetStart(),o.GetEnd())) for i in range(count+1))
    cost={};parents={};queue=[]
    wire=make(b,(0,0),(0,0),width,code,side)
    @lru_cache(80000)
    def edge(a,z):
        wire.SetStart(v(a));wire.SetEnd(v(z));return clear(wire)
    for at in samples:
        aligned=tuple(round(x/step)*step for x in at)
        if edge(at,aligned):
            d=math.dist(at,aligned)
            if d<cost.get(aligned,math.inf):
                cost[aligned]=d;parents[aligned]=(None,at);heapq.heappush(queue,(d,aligned))
    while queue:
        d,pt=heapq.heappop(queue)
        if d!=cost[pt]:continue
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)):
            end=(pt[0]+dx*step,pt[1]+dy*step)
            nd=d+math.hypot(dx,dy)*step
            if not (22000000<=end[0]<=56000000 and 600000<=end[1]<=25000000) or nd>limit or nd>=cost.get(end,math.inf) or not edge(pt,end):continue
            parents[end]=(pt,None);cost[end]=nd;heapq.heappush(queue,(nd,end))
    return cost,parents
def collect(q,cost):
    x,y=q.GetPosition();cx,cy=round(x/step)*step,round(y/step)*step
    pts=((cx+i*step,cy+j*step) for i in range(-3,4) for j in range(-3,4))
    return sorted((at for at in pts if at in cost and q.HitTest(v(at))),key=cost.get)
def recover(pt,parents):
    out=[pt]
    while parents[out[-1]][0] is not None:out.append(parents[out[-1]][0])
    start=parents[out[-1]][1]
    if start!=out[-1]:out.append(start)
    result=[]
    for x in out:
        if len(result)>1:
            a,z=result[-2:];u=(z[0]-a[0],z[1]-a[1]);v1=(x[0]-z[0],x[1]-z[1])
            if u[0]*v1[1]==u[1]*v1[0] and u[0]*v1[0]+u[1]*v1[1]>0:result.pop()
        result.append(x)
    return result
signal,si=frontier(pin,200000,18000000);power,pi=frontier(bank,500000,14000000)
if '--barrel-access' in sys.argv:
    within=[o for o in objs if inflated_box(o,6000000).Contains(pin.GetPosition())]
    layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
    foreign=[o.GetEffectiveShape(layer) for o in within if o.GetNetCode()!=pin.GetNetCode() for layer in layers if o.IsOnLayer(layer)]
    holes=[o.GetEffectiveHoleShape() for o in within if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    lands=[o.GetEffectiveShape(o.GetParentFootprint().GetLayer()) for o in within if isinstance(o,p.PAD)]
    zones=[z.Outline() for z in [*b.Zones(),*(zone for f in others for zone in f.Zones())] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    gnd_ids={uid(o) for o in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('U4').FindPadByNumber('69'))}
    gnd_pts=[tuple(o.GetPosition()) for o in b.GetTracks() if uid(o) in gnd_ids and isinstance(o,p.PCB_VIA)]
    options=[];status=Counter()
    for at in signal:
        barrel=p.PCB_VIA(b);barrel.SetWidth(450000);barrel.SetDrill(200000);barrel.SetLayerPair(p.F_Cu,p.B_Cu);barrel.SetViaType(p.VIATYPE_THROUGH);barrel.SetPosition(v(at))
        sh=barrel.GetEffectiveShape(p.B_Cu);hole=barrel.GetEffectiveHoleShape()
        if any(sh.Collide(x,52000) for x in lands):status['assembly_pads']+=1;continue
        if any(sh.Collide(x,202000) or hole.Collide(x,252000) for x in foreign):status['copper']+=1;continue
        if any(sh.Collide(x,252000) or hole.Collide(x,252000) for x in holes):status['drills']+=1;continue
        if any(sh.Collide(x,0) for x in zones):status['keepout']+=1;continue
        options.append(dict(pos=at,trace_nm=recover(at,si),length_mm=signal[at]/1e6,return_distance_mm=min(math.dist(at,g) for g in gnd_pts)/1e6))
    (root/'emmc-dat0-barrel-access.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],status=status,options=sorted(options,key=lambda row:row['length_mm']),assembly_ready=False),indent=2)+'\n')
    if '--launch' in sys.argv:
        folder=root/'runs/emmc-d0-socket-launch';folder.mkdir(exist_ok=True)
        for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
        candidate=None;tested=[]
        for row in sorted(options,key=lambda row:(row['length_mm']+row['return_distance_mm'],row['return_distance_mm'])):
            if row['return_distance_mm']>1:continue
            trial=p.LoadBoard(str(src));at=row['pos'];path=row['trace_nm'];code=pin.GetNetCode()
            for a,z in zip(path,path[1:]):trial.Add(make(trial,a,z,200000,code,p.B_Cu))
            via=p.PCB_VIA(trial);via.SetWidth(450000);via.SetDrill(200000);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetViaType(p.VIATYPE_THROUGH);via.SetPosition(v(at));via.SetNetCode(code);trial.Add(via)
            out=folder/src.name;p.ZONE_FILLER(trial).Fill(trial.Zones());p.SaveBoard(str(out),trial)
            subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
            new=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));tested.append(dict(pos=at,new_drc=new))
            if any(e['type']!='via_dangling' for e in new):continue
            saved=p.LoadBoard(str(out));saved.BuildConnectivity()
            if uid(via) not in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('U8001').FindPadByNumber('A3'))}:continue
            candidate=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),via_uid=uid(via),via_nm=at,signal_mm=row['length_mm'],nearest_return_mm=row['return_distance_mm'],preservation=verify_preservation(before,saved));break
        (root/'emmc-d0-socket-launch.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],attempts=tested,candidate=candidate,assembly_ready=False),indent=2)+'\n')
    print(len(signal),status,len(options));sys.exit()
courts=[f.GetCourtyard(side) for f in others if f.GetLayer()==side and f.GetCourtyard(side).OutlineCount()]
if from_launch:
    from phy_corridor_path import geometry
    from pcb_power_leg import barrel
    stack=[p.F_Cu,p.In3_Cu,p.In2_Cu,p.B_Cu];layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
    poses=defaultdict(list)
    for angle in (0,90,180,270):
        fp.SetOrientationDegrees(angle);fp.SetPosition(v((0,0)));offset=tuple(supply.GetPosition())
        positions={(round((x-offset[0])/200000)*200000,round((y-offset[1])/200000)*200000) for x,y in power}
        for pos in sorted(positions):
            fp.SetPosition(v(pos));starts=collect(supply,power)
            if not starts:continue
            cy=fp.GetCourtyard(side)
            if any(cy.Collide(f,100000) for f in courts) or not all(clear(q) for q in fp.Pads()):continue
            dest=tuple(data.GetPosition())
            if math.dist(dest,tuple(pin.GetPosition()))>15000000:continue
            poses[dest].append((power[starts[0]],pos,angle,starts[0]))
    oldfp=before.FindFootprintByReference('R8001');fp.SetPosition(oldfp.GetPosition());fp.SetOrientationDegrees(oldfp.GetOrientationDegrees());b.Remove(fp)
    code=pin.GetNetCode();geos={}
    for layer in layers:
        tracks,boxes=geometry(b,layer,code,oval_caps=True)
        polygons=[]
        for zone in [*b.Zones(),*(zone for f in b.GetFootprints() for zone in f.Zones())]:
            if zone.GetIsRuleArea() and zone.IsOnLayer(layer) and (zone.GetDoNotAllowTracks() or zone.GetDoNotAllowVias()):
                for i in range(zone.Outline().OutlineCount()):
                    outline=zone.Outline().Outline(i);polygons.append([tuple(outline.CPoint(j)) for j in range(outline.PointCount())])
        geos[layer]=[tracks,boxes,polygons]
    holes=[[tuple(t.GetPosition()),tuple(t.GetPosition()),t.GetDrillValue()+400000] for t in b.GetTracks() if isinstance(t,p.PCB_VIA)]
    boxes=[q.GetBoundingBox() for f in b.GetFootprints() for q in f.Pads()]
    req=dict(start=[[cp['via_nm']] for layer in stack],end=[[],[],[],list(poses)],layers=[geos[l] for l in stack],through=list(geos.values()),via_keepouts=[holes,[(z.GetLeft(),z.GetTop(),z.GetRight(),z.GetBottom()) for z in boxes]],via_nm=450000,width_nm=200000,grid_nm=100000,via_cost_nm=4500000,bounds=[24000000,500000,56500000,26000000],explain=True)
    folder=root/'runs/emmc-data-pullup-complete';folder.mkdir(exist_ok=True)
    for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
    tests=[];candidate=None
    for attempt in range(16):
        solution=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('control_board_grid.py'))],input=json.dumps(req),text=True,capture_output=True,check=True).stdout)
        if 'path' not in solution:tests.append(solution);break
        path=solution['path'];dest=tuple(path[-1][1:]);states=poses[dest]
        for length,pos,angle,end in sorted(states):
            trial=p.LoadBoard(str(src));f=trial.FindFootprintByReference('R8001');f.SetOrientationDegrees(angle);f.SetPosition(v(pos))
            rail_path=recover(end,pi);added=[];rails=[];vias=[]
            for a,z in zip(rail_path,rail_path[1:]):
                t=make(trial,a,z,500000,bank.GetNetCode(),p.B_Cu);trial.Add(t);rails.append(t)
            for (l,x,y),(k,u,vv) in zip(path,path[1:]):
                if l==k:t=make(trial,(x,y),(u,vv),200000,code,stack[l])
                else:
                    t=barrel(trial,(x,y),code);vias.append(uid(t))
                trial.Add(t);added.append(t)
            if any(t.IsOnLayer(p.B_Cu) and (t.GetEffectiveShape(p.B_Cu).Collide(f.FindPadByNumber('1').GetEffectiveShape(p.B_Cu),202000) or any(t.GetEffectiveShape(p.B_Cu).Collide(rr.GetEffectiveShape(p.B_Cu),202000) for rr in rails)) for t in added):
                tests.append(dict(pos=pos,reason='rail crossing'));continue
            out=folder/src.name;p.ZONE_FILLER(trial).Fill(trial.Zones());p.SaveBoard(str(out),trial)
            subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
            delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));tests.append(dict(pos=pos,new_drc=delta))
            if delta:continue
            saved=p.LoadBoard(str(out));saved.BuildConnectivity();f=saved.FindFootprintByReference('R8001')
            if any(uid(f.FindPadByNumber(n)) not in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference(ref).FindPadByNumber(num))} for n,ref,num in [('1','C8002','1'),('2','U8001','A3')]) or screen(saved):continue
            candidate=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),signal_nm=path,supply_nm=rail_path,signal_vias=vias,pos_nm=pos,angle=angle,preservation=verify_preservation(before,saved));break
        if candidate:break
        req['end'][-1]=[k for k in req['end'][-1] if math.dist(k,dest)>500000]
        if not req['end'][-1]:break
    (root/'emmc-d0-data-pullup.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],candidate=candidate,initial_placements=len(poses),tests=tests,assembly_ready=False),indent=2)+'\n')
    print(len(poses),len(tests),bool(candidate));sys.exit()
cases=[];stats=Counter()
for angle in (0,90,180,270):
    fp.SetOrientationDegrees(angle);fp.SetPosition(v((0,0)));offset=tuple(data.GetPosition())
    poses={(round((x-offset[0])/100000)*100000,round((y-offset[1])/100000)*100000) for x,y in signal}
    for pos in sorted(poses):
        fp.SetPosition(v(pos));ends=collect(supply,power)
        if not ends:continue
        starts=collect(data,signal)
        if not starts:continue
        stats['both_lands']+=1
        cy=fp.GetCourtyard(side)
        if any(cy.Collide(f,100000) for f in courts) or not all(clear(q) for q in fp.Pads()):continue
        stats['clear_footprint']+=1
        cases.append((signal[starts[0]]+power[ends[0]],pos,angle,starts[0],ends[0]))
folder=root/'runs/emmc-dat0-pullup';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
attempted=[];winner=None
for _,pos,angle,start,end in sorted(cases)[:100]:
    trial=p.LoadBoard(str(src));f=trial.FindFootprintByReference('R8001');f.SetOrientationDegrees(angle);f.SetPosition(v(pos));paths=[]
    for pt,par,width,num in ((start,si,200000,'2'),(end,pi,500000,'1')):
        coords=recover(pt,par);lines=[]
        q=f.FindPadByNumber(num)
        for a,z in zip(coords,coords[1:]):
            t=make(trial,a,z,width,q.GetNetCode(),side);trial.Add(t);lines.append(t)
        paths.append(lines)
    if any(t.GetEffectiveShape(side).Collide(o.GetEffectiveShape(side),202000) for t in paths[0] for o in paths[1]):continue
    if any(t.GetEffectiveShape(side).Collide(f.FindPadByNumber(other).GetEffectiveShape(side),202000) for lines,other in zip(paths,('1','2')) for t in lines):continue
    out=folder/src.name;p.ZONE_FILLER(trial).Fill(trial.Zones());p.SaveBoard(str(out),trial)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    attempted.append(dict(pos=pos,angle=angle,new_drc=delta))
    if delta:continue
    saved=p.LoadBoard(str(out));saved.BuildConnectivity()
    groups=[{uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference(ref).FindPadByNumber(n))} for ref,n in [('U8001','A3'),('C8002','1')]]
    f=saved.FindFootprintByReference('R8001')
    if any(uid(f.FindPadByNumber(n)) not in group for n,group in zip(('2','1'),groups)) or screen(saved):continue
    winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),preservation=verify_preservation(before,saved),pos=pos,angle=angle,signal_mm=sum(t.GetLength() for t in paths[0])/1e6,supply_mm=sum(t.GetLength() for t in paths[1])/1e6);break
(root/'emmc-dat0-pullup.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],signal_cells=len(signal),power_cells=len(power),stats=stats,attempts=attempted,candidate=winner,assembly_ready=False),indent=2)+'\n')
print(len(signal),len(power),stats,bool(winner))
