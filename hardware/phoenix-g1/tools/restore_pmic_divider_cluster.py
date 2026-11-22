"""Restore the full power and return chains around the relocated VDC filter coupon."""
from functools import lru_cache
from pathlib import Path
import hashlib
import heapq
import json
import math
import os
import subprocess
import sys
import pcbnew as p
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
index=int(sys.argv[1]) if len(sys.argv)>1 else 0
meta=json.loads((root/'layout-soc-tx-series.json').read_text())
src=root/meta['board'];folder=root/f'runs/vdc-placement-{index}'
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
b=p.LoadBoard(str(folder/src.name))
def pad(ref,n):return tuple(b.FindFootprintByReference(ref).FindPadByNumber(n).GetPosition())
def route(net,layer,start,end,width,budget):
    code=b.FindNet(net).GetNetCode()
    items=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if o.GetNetCode()!=code and inflated_box(o,round(budget*1e6)+1000000).Contains(p.VECTOR2I(*start))]
    obs=[(o.GetEffectiveShape(layer),o.GetBoundingBox()) for o in items if o.IsOnLayer(layer)]
    holes=[(o.GetEffectiveHoleShape(),o.GetPosition()) for o in items if isinstance(o,p.PCB_VIA)]
    keep=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks()]
    t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetNetCode(code);t.SetWidth(width)
    @lru_cache(None)
    def clear(a,z):
        t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));s=t.GetEffectiveShape(layer);box=inflated_box(t,365000)
        return not(any(box.Intersects(o) and s.Collide(h,202000) for h,o in obs) or any(box.Contains(o) and s.Collide(h,250000) for h,o in holes) or any(k.Collide(s,0) for k in keep))
    step=50000
    if not clear(start,start) or not clear(end,end):return [],'terminal'
    grid=lambda a:tuple(round(x/step)*step for x in a)
    a,z=grid(start),grid(end)
    if not clear(start,a) or not clear(end,z):return [],'terminal-grid'
    prev={};dist={a:0};q=[(math.dist(a,z),0,a)]
    while q:
        _,length,n=heapq.heappop(q)
        if dist[n]!=length:continue
        if n==z:
            nodes=[end,z]
            while nodes[-1]!=a:nodes.append(prev[nodes[-1]])
            nodes.append(start);nodes.reverse();compact=[]
            for pt in nodes:
                if compact and compact[-1]==pt:continue
                if len(compact)>1:
                    i,j=compact[-2:];d=(j[0]-i[0],j[1]-i[1]);e=(pt[0]-j[0],pt[1]-j[1])
                    if d[0]*e[1]==d[1]*e[0] and d[0]*e[0]+d[1]*e[1]>0:compact.pop()
                compact.append(pt)
            for a0,z0 in zip(compact,compact[1:]):
                seg=p.PCB_TRACK(b);seg.SetWidth(width);seg.SetLayer(layer);seg.SetNetCode(code);seg.SetStart(p.VECTOR2I(*a0));seg.SetEnd(p.VECTOR2I(*z0));b.Add(seg)
            return compact,'restored'
        for dx,dy in ((1,0),(0,1),(-1,0),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            nxt=n[0]+dx*step,n[1]+dy*step;nd=length+step*math.hypot(dx,dy);score=nd+math.dist(nxt,z)
            if score>budget*1e6 or nd>=dist.get(nxt,math.inf) or not clear(n,nxt):continue
            prev[nxt]=n;dist[nxt]=nd;heapq.heappush(q,(score,nd,nxt))
    return [],'blocked'
jobs=[('+1V8_SYS',p.F_Cu,(59300000,2650000),(60300000,4900000),200000,5.0),('GND',p.B_Cu,pad('C481','2'),(58120000,1400000),300000,4.6),('+3V3_SYS',p.B_Cu,pad('R410','1'),(59100000,4800000),200000,4.0),('GND',p.B_Cu,pad('R411','2'),(59000000,8000000),300000,4.0),('GND',p.B_Cu,pad('C410','2'),(59000000,9000000),300000,4.0)]
def terminal_candidates(ref,num,layer,origin,maximum):
    b.BuildConnectivity()
    q=b.FindFootprintByReference(ref).FindPadByNumber(num)
    ids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(q)}
    points=set()
    for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]:
        if o.m_Uuid.AsString() not in ids or not o.IsOnLayer(layer):continue
        if isinstance(o,p.PAD) or isinstance(o,p.PCB_VIA):
            points.add(tuple(o.GetPosition()))
        else:
            points.update([tuple(o.GetStart()),tuple(o.GetEnd())])
    return [q for q in sorted(points,key=lambda x:math.dist(x,origin)) if math.dist(q,origin)<=maximum*1e6][:22]
results=[]
for net,l,a,z,w,budget in jobs:
    path,status=route(net,l,a,z,w,budget)
    if not path:
        if net=='+1V8_SYS':a,z=z,a
        ref,num= {'+1V8_SYS':('L405','2'),'+3V3_SYS':('C481','1'),'GND':('C410','2')}[net]
        # Original ground returns join the PMIC exposed-land plane.
        if net=='GND':ref,num='U4','69'
        for target in terminal_candidates(ref,num,l,a,budget):
            if target==z:continue
            path,status=route(net,l,a,target,w,budget)
            if path:z=target;break
    results.append(dict(net=net,start_nm=a,end_nm=z,width_nm=w,maximum_mm=budget,status=status,path_nm=path))
out=folder/'restored.kicad_pcb';p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
# Running via the project's filename applies the original board-specific custom rules.
from tempfile import TemporaryDirectory
import shutil
with TemporaryDirectory(dir=folder.parent) as temp:
    stage=Path(temp)
    for nm in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/nm,stage/nm)
    shutil.copy2(out,stage/src.name)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'restored-drc.json'),str(stage/src.name)],capture_output=True,check=True)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'restored-drc.json').read_text()))
b=p.LoadBoard(str(out));b.BuildConnectivity()
pin=b.FindFootprintByReference('U4').FindPadByNumber('61')
ids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(pin)}
sense_ok=all(b.FindFootprintByReference(ref).FindPadByNumber(n).m_Uuid.AsString() in ids for ref,n in [('R410','2'),('R411','1'),('C410','1')])
audit=dict(source_sha256=meta['sha256'],adopted=False,vdc_pad_group_on_reload=sense_ok,routes=results,delta=delta)
(folder/'restore-status.json').write_text(json.dumps(audit,indent=2)+'\n')
print(sense_ok,[(r['net'],r['status']) for r in results],[(r['type'],r['count']) for r in delta],flush=True);os._exit(0)
