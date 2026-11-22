"""Adopt a short source-clock leg only with comparable breakout for the adjoining termination."""
from pathlib import Path
from collections import deque,Counter
import math,json,hashlib,subprocess,shutil
import pcbnew as p
from pcb_power_leg import make
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';base=json.loads((r/'layout-npu-c434-paired-load.json').read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
pose=json.loads((r/'rgmii-tx-joint-termination-poses.json').read_text());native=json.loads((r/'interface-copper-edge-candidates.json').read_text());assert pose['parent_sha256']==native['parent_sha256']==base['sha256'];path=[tuple(k) for k in next(row['found']['path_nm'] for row in native['rows'] if row['net']=='ETH_TXCLK' and row['found'])][::-1]
V=lambda xy:p.VECTOR2I(*xy);uid=lambda o:o.m_Uuid.AsString();side=p.F_Cu
def free_stub(b,ref,num):
    f=b.FindFootprintByReference(ref);q=f.FindPadByNumber(num);center=tuple(q.GetPosition());code=q.GetNetCode();box=inflated_box(q,2400000)
    items=[o for o in [*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())] if o.GetNetCode()!=code and box.Intersects(o.GetBoundingBox())]
    ff=[o.GetEffectiveShape(side) for o in items if o.IsOnLayer(side)];holes=[o.GetEffectiveHoleShape() for o in items if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    gnd=[z.GetFilledPolysList(p.In1_Cu) for z in b.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(p.In1_Cu)]
    trace=make(b,center,center,200000,code,side);seeds=set()
    def clear(a,z):
        trace.SetStart(V(a));trace.SetEnd(V(z));sh=trace.GetEffectiveShape(side)
        return not any(sh.Collide(s,202000) for s in ff) and not any(sh.Collide(h,252000) for h in holes) and any(ground.Contains(V(z)) for ground in gnd)
    for i in range(-4,5):
     for j in range(-4,5):
        a=center[0]+i*100000,center[1]+j*100000
        if q.HitTest(V(a)) and clear(a,a):seeds.add(a)
    seen=set(seeds);queue=deque(seeds);best=0
    while queue:
        a=queue.popleft();best=max(best,math.dist(center,a))
        if best>=1000000:return 1.
        for i,j in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
            z=a[0]+i*100000,a[1]+j*100000
            if z not in seen and clear(a,z):seen.add(z);queue.append(z)
    return best/1e6
baseline=p.LoadBoard(str(src));initial={(ref,n):free_stub(baseline,ref,n) for ref,n in [('R502','1'),('R502','2'),('R505','1'),('R505','2'),('R506','2')]};old=json.loads((src.parent/'drc.json').read_text());trials=[];winner=None
rows=sorted([(opt[0],rec['ref'],opt) for rec in pose['results'] for opt in rec['best']]);folder=r/'runs/rgmii-short-source-clock';folder.mkdir(exist_ok=True);file=folder/src.name
for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',folder/'fp-lib-table')
for _,ref,opt in rows:
    b=p.LoadBoard(str(src));length,ds,at,angle,xy,an,idx=opt
    for n,pos,rot in [('R506',at,angle),(ref,xy,an)]:
        f=b.FindFootprintByReference(n);f.SetOrientationDegrees(rot);f.SetPosition(V(pos))
    compact=[]
    for point in path[:idx+1]:
        if len(compact)>1:
            a,z=compact[-2:]
            if (z[0]-a[0])*(point[1]-z[1])==(z[1]-a[1])*(point[0]-z[0]):compact.pop()
        compact.append(point)
    for a,z in zip(compact,compact[1:]):b.Add(make(b,a,z,200000,b.FindNet('ETH_TXCLK').GetNetCode(),side))
    free=[(n,num,initial[n,num],free_stub(b,n,num)) for n,num in [(ref,'1'),(ref,'2'),('R506','2')]]
    row=dict(peer=ref,length_mm=length,clock_at=at,clock_angle=angle,peer_at=xy,peer_angle=an,peer_source_distance_mm=ds,copper_nm=compact,stub_access_before_after=free);trials.append(row)
    if any(after+1e-9<before for _,_,before,after in free):continue
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(file)],check=True,capture_output=True)
    drc=json.loads((folder/'drc.json').read_text());delta=introduced(old,drc);fresh=p.LoadBoard(str(file));fresh.BuildConnectivity()
    def pad(n):
        f,num=n.split('.');return fresh.FindFootprintByReference(f).FindPadByNumber(num)
    cache={}
    def conn(a,z):
        if a not in cache:cache[a]={uid(o) for o in fresh.GetConnectivity().GetConnectedItems(pad(a))}
        return uid(pad(z)) in cache[a]
    poly=[z.GetFilledPolysList(p.In1_Cu) for z in fresh.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(p.In1_Cu)];missing=0;samples=0
    for a,z in zip(compact,compact[1:]):
        dx=z[0]-a[0];dy=z[1]-a[1];dd=math.hypot(dx,dy);ns=math.ceil(dd/25000)
        for i in range(ns+1):
         for off in (-110000,0,110000):
            loc=V((round(a[0]+i*dx/ns-off*dy/dd),round(a[1]+i*dy/ns+off*dx/dd)));samples+=1
            if not any(pg.Contains(loc) for pg in poly):missing+=1
    joins=len(drc['unconnected_items']);row.update(new_drc=delta,joins=joins,missing_reference_samples=missing,reference_samples=samples,mechanical=screen(fresh))
    if delta or missing or row['mechanical'] or not conn('U1.Y2','R506.1') or joins!=base['remaining_minimum_joins']-1:continue
    pairs=sorted({tuple(sorted(pair)) for pair in base['verified_pairs']+[['U1.Y2','R506.1']]});assert all(conn(a,z) for a,z in pairs)
    nets=base['open_nets'].copy();assert len(nets.pop('ETH_TXCLK'))==2
    assert sum(len(gs)-1 for gs in nets.values())==joins
    state=dict(board=str(file.relative_to(r)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),parent_sha256=base['sha256'],verified_pairs=pairs,preservation=verify_preservation(p.LoadBoard(str(src)),fresh),open_nets=nets,remaining_minimum_joins=joins,new_drc=delta,drc_counts=dict(Counter(e['type'] for e in drc['violations'])),assembly_ready=False)
    (r/'layout-rgmii-short-source-clock.json').write_text(json.dumps(state,indent=2)+'\n');winner=row;break
(r/'rgmii-short-source-clock-adoption.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],trials=trials,winner=winner),indent=2)+'\n');print(bool(winner),len(trials),winner and (winner['peer'],winner['length_mm'],winner['joins']),flush=True)
