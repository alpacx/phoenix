"""Try a local CC2/AON dogleg to free an independent reversible-contact via."""
from pathlib import Path
from functools import lru_cache
import hashlib
import heapq
import json
import math
import os
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-cpu-load-sense.json').read_text())
src=root/meta['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
b=p.LoadBoard(str(src))
site=(8800000,19700000)
v=p.PCB_VIA(b);v.SetWidth(450000);v.SetDrill(200000);v.SetPosition(p.VECTOR2I(*site));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu)
replaced=set()
rows=[]
for uid in ('709faf13-4e37-4ff9-954f-30034099ddfb','f32ab76b-213c-40d4-855f-fba2ebf53215'):
    old=next(t for t in b.GetTracks() if t.m_Uuid.AsString()==uid)
    layer=old.GetLayer();a=tuple(old.GetStart());z=tuple(old.GetEnd());width=old.GetWidth();code=old.GetNetCode()
    assert width==200000
    name=old.GetNetname();startlength=old.GetLength();b.Remove(old)
    objects=[k for k in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if k.GetNetCode()!=code and k.IsOnLayer(layer) and inflated_box(k,5500000).Contains(v.GetPosition())]+[v]
    obs=[(k.GetEffectiveShape(layer),k.GetBoundingBox()) for k in objects]
    holes=[(k.GetEffectiveHoleShape(),k.GetPosition()) for k in objects if isinstance(k,p.PCB_VIA)]
    areas=[zona.Outline() for zona in b.Zones() if zona.IsOnLayer(layer) and zona.GetIsRuleArea() and zona.GetDoNotAllowTracks()]
    trace=p.PCB_TRACK(b);trace.SetWidth(width);trace.SetLayer(layer);trace.SetNetCode(code)
    @lru_cache(None)
    def clear(u,end):
        trace.SetStart(p.VECTOR2I(*u));trace.SetEnd(p.VECTOR2I(*end));sh=trace.GetEffectiveShape(layer);box=inflated_box(trace,300000)
        return not (any(box.Intersects(bb) and sh.Collide(s,202000) for s,bb in obs) or any(box.Contains(pos) and sh.Collide(h,250000) for h,pos in holes) or any(area.Collide(sh,0) for area in areas))
    grid=50000
    cost={a:0};parents={};queue=[(math.dist(a,z),0,a)];pts=[]
    while queue:
        _,d,pt=heapq.heappop(queue)
        if cost[pt]!=d:continue
        if pt==z:
            pts=[z]
            while pt!=a:pt=parents[pt];pts.append(pt)
            pts.reverse();break
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            nxt=(pt[0]+dx*grid,pt[1]+dy*grid);nd=d+math.hypot(dx,dy)*grid
            if nd>=cost.get(nxt,math.inf) or nd+math.dist(nxt,z)>startlength+900000 or not clear(pt,nxt):continue
            cost[nxt]=nd;parents[nxt]=pt;heapq.heappush(queue,(nd+math.dist(nxt,z),nd,nxt))
    row=dict(net=name,width_mm=width/1e6,prior_mm=startlength/1e6,visited=len(cost));rows.append(row)
    if not pts:row['found']=False;break
    simplify=[pts[0]]
    for i in range(1,len(pts)-1):
        d=(pts[i][0]-pts[i-1][0],pts[i][1]-pts[i-1][1])
        e=(pts[i+1][0]-pts[i][0],pts[i+1][1]-pts[i][1])
        if d!=e:simplify.append(pts[i])
    simplify.append(pts[-1])
    for u,end in zip(simplify,simplify[1:]):
        t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(width);t.SetStart(p.VECTOR2I(*u));t.SetEnd(p.VECTOR2I(*end));t.SetNetCode(code);b.Add(t)
    row.update(found=True,length_mm=cost[z]/1e6)
    replaced.add(uid)
result=dict(source_sha256=meta['sha256'],reserved_via_nm=site,stages=rows,adopted=False)
if len(replaced)==2:
    folder=root/'runs/usb-contact-corridor';folder.mkdir(exist_ok=True)
    for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/n,folder/n)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    result['new_drc']=delta
    if not delta:
        saved=p.LoadBoard(str(out));result['preservation']=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=replaced);assert not screen(saved)
        result.update(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest())
(root/'usb-contact-corridor.json').write_text(json.dumps(result,indent=2)+'\n')
print(rows,len(result.get('new_drc',[])),flush=True);os._exit(0)
