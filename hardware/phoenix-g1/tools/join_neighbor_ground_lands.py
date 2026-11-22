"""Join adjacent package ground lands sharing a row or column without vias or added neckdowns."""
from pathlib import Path
import hashlib
import json
import math
import sys
import shutil
import subprocess

import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
from drc_regression import introduced
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
cp=json.loads((root/"layout-command-ca1.json").read_text())
src=root/cp["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp["sha256"]
b=p.LoadBoard(str(src))
b.BuildConnectivity()
ids=lambda pad:{o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(pad)}
ref_ground=ids(b.FindFootprintByReference("U10").FindPadByNumber("B4"))
edge="--offset-edge" in sys.argv
name="ground-package-edge-links" if edge else "ground-package-adjacent-lands"
results=[];blocked=[]
for ref in ("U1","U2","U8001"):
    f=b.FindFootprintByReference(ref)
    layer=f.GetLayer()
    lands=[q for q in f.Pads() if q.GetNetname()=="GND"]
    foreign=[o for o in list(b.GetTracks())+[q for fp in b.GetFootprints() for q in fp.Pads()] if o.IsOnLayer(layer) and o.GetNetname()!="GND"]
    guarded=[(o,o.GetBoundingBox(),o.GetEffectiveShape(layer)) for o in foreign]
    cases=[]
    for i,a in enumerate(lands):
        for z in lands[i+1:]:
            u,v=tuple(a.GetPosition()),tuple(z.GetPosition())
            if u[0]!=v[0] and u[1]!=v[1]:continue
            if not 1<math.dist(u,v)<=800001:continue
            cases.append((math.dist(u,v),a,z))
    for _,a,z in sorted(cases,key=lambda c:c[0]):
        if z.m_Uuid.AsString() in ids(a):continue
        u,v=tuple(a.GetPosition()),tuple(z.GetPosition())
        trace=make(b,u,v,250000,a.GetNetCode(),layer)
        sh=trace.GetEffectiveShape(layer);bb=inflated_box(trace,260000)
        hits=[o for o,box,shape in guarded if bb.Intersects(box) and (sh.Collide(shape,202000) or isinstance(o,p.PCB_VIA) and sh.Collide(o.GetEffectiveHoleShape(),252000))]
        used_offset=0
        if hits and edge:
            for offset in (25000,-25000,50000,-50000,75000,-75000):
                def shifted(at):
                    return (at[0],at[1]+offset) if u[1]==v[1] else (at[0]+offset,at[1])
                line=make(b,shifted(u),shifted(v),250000,a.GetNetCode(),layer)
                swept=line.GetEffectiveShape(layer)
                guard=inflated_box(line,260000)
                if any(guard.Intersects(box) and (swept.Collide(sh_other,202000) or isinstance(o,p.PCB_VIA) and swept.Collide(o.GetEffectiveHoleShape(),252000)) for o,box,sh_other in guarded):
                    continue
                if not all(q.GetEffectiveShape(layer).Collide(p.VECTOR2I(*shifted(at)),0) for q,at in ((a,u),(z,v))):continue
                hits=[];trace=line;used_offset=offset;break
        pair=[ref+"."+q.GetNumber() for q in (a,z)]
        if hits:
            blocked.append(dict(pair=pair,obstacles=sorted({t.GetNetname() for t in hits})))
            continue
        b.Add(trace)
        b.BuildConnectivity()
        assert z.m_Uuid.AsString() in ids(a)
        results.append(dict(pair=pair,offset_mm=used_offset/1e6,trace_uuid=trace.m_Uuid.AsString(),length_mm=math.dist(u,v)/1e6,group_grounded=bool(ids(a)&ref_ground)))
report={"parent_sha256":cp["sha256"],"added":results,"held":blocked,"adopted":False}
if results:
    folder=root/"runs"/name;folder.mkdir(exist_ok=True)
    for f in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):shutil.copyfile(src.parent/f,folder/f)
    file=folder/src.name
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(file)],capture_output=True,check=True)
    drc=json.loads((folder/"drc.json").read_text())
    report.update(board=str(file.relative_to(root)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),remaining=len(drc["unconnected_items"]),native_delta=introduced(json.loads((src.parent/"drc.json").read_text()),drc))
    reloaded=p.LoadBoard(str(file));reloaded.BuildConnectivity()
    report["preservation"]=verify_preservation(p.LoadBoard(str(src)),reloaded)
(root/(name+".json")).write_text(json.dumps(report,indent=2)+"\n")
print(len(results),len(blocked),sum(r["group_grounded"] for r in results),report.get("remaining"),len(report.get("native_delta",[])))
