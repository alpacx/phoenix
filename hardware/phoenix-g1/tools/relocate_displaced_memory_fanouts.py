"""Repair missing BGA escape barrels by extending their existing supply-independent F.Cu tips."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make,barrel
from drc_regression import introduced

r=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
read=lambda name:json.loads((r/(name+".json")).read_text())
cp=read("ddr-clock-b-recovered");src=r/cp["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp["sha256"]
b=p.LoadBoard(str(src));d=read("layout-command-ca1");baseline=p.LoadBoard(str(r/d["board"]))
old={v.m_Uuid.AsString():v for v in baseline.GetTracks() if isinstance(v,p.PCB_VIA)}
layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
reference={p.F_Cu:p.In1_Cu,p.In2_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu,p.B_Cu:p.In4_Cu}
planes={l:next(z.GetFilledPolysList(l) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(l)) for l in (p.In1_Cu,p.In4_Cu)}
fast=("LPDDR4_","USB_","MUX_","SOC_USB_","ADDON_USB_","EMMC_","SOC_EMMC_","ETH_","PHY_","WIFI_")
held=cp["still_requiring_relocation"];records=[];saved_parts=[]
for entry in held:
    via0=old[entry["uuid"]];anchor=tuple(via0.GetPosition());net=entry["net"];code=b.FindNet(net).GetNetCode()
    near=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if inflated_box(o,1650000).Contains(via0.GetPosition())]
    pads=[q for q in near if isinstance(q,p.PAD)]
    shapes={l:[(o.GetNetCode(),o.GetBoundingBox(),o.GetEffectiveShape(l)) for o in near if o.IsOnLayer(l)] for l in layers}
    drills=[(o.GetNetCode(),o.GetBoundingBox(),o.GetEffectiveHoleShape()) for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    tips=[t for t in near if isinstance(t,p.PCB_TRACK) and not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu and t.GetNetCode()==code and anchor in (tuple(t.GetStart()),tuple(t.GetEnd()))]
    stops=[t for t in near if isinstance(t,p.PCB_TRACK) and not isinstance(t,p.PCB_VIA) and t.GetNetCode()!=code and t.GetNetname().startswith(fast) and t.GetLayer() in reference]
    guards=[]
    for t in stops:
        poly=p.SHAPE_POLY_SET();t.TransformShapeToPolygon(poly,t.GetLayer(),200000,500,p.ERROR_OUTSIDE)
        poly.BooleanIntersection(planes[reference[t.GetLayer()]]);guards.append(poly)
    ks=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    xy=p.VECTOR2I;options=[];stats=Counter()
    if tips:
        for dx in range(-24,25):
            for dy in range(-24,25):
                length=math.hypot(dx,dy)*50000
                if length>1200000 or length<50000:continue
                a=(anchor[0]+dx*50000,anchor[1]+dy*50000);v=barrel(b,a,code);bb=inflated_box(v,355000)
                if any(v.GetEffectiveShape(p.F_Cu).Collide(q.GetEffectiveShape(q.GetParentFootprint().GetLayer()),100000) for q in pads):continue
                if any(bb.Intersects(box) and (v.GetEffectiveHoleShape().Collide(h,252000) or v.GetEffectiveShape(p.F_Cu).Collide(h,252000)) for n,box,h in drills):continue
                if any(n!=code and bb.Intersects(box) and (v.GetEffectiveHoleShape().Collide(sh,252000) or v.GetEffectiveShape(l).Collide(sh,202000)) for l in layers for n,box,sh in shapes[l]):continue
                if any(z.Collide(v.GetEffectiveShape(p.F_Cu),0) for z in ks):continue
                stats["clears_copper_and_holes"]+=1
                if any(poly.Collide(xy(*a),430000) for poly in guards):continue
                stats["preserves_projected_reference"]+=1
                diagonal=min(abs(dx),abs(dy))*50000
                ex=int(math.copysign(diagonal,dx));ey=int(math.copysign(diagonal,dy))
                for turn in ((anchor[0]+ex,anchor[1]+ey),(a[0]-ex,a[1]-ey)):
                    lines=[make(b,u,z,200000,code,p.F_Cu) for u,z in zip((anchor,turn),(turn,a)) if u!=z]
                    if any(t.GetEffectiveShape(p.F_Cu).Collide(sh,202000) for t in lines for n,box,sh in shapes[p.F_Cu] if n!=code and inflated_box(t,260000).Intersects(box)):continue
                    if any(t.GetEffectiveShape(p.F_Cu).Collide(h,252000) for t in lines for n,box,h in drills if n!=code and inflated_box(t,260000).Intersects(box)):continue
                    options.append((sum(t.GetLength() for t in lines),a,turn));break
    picked=None
    if options:
        length,at,elbow=min(options);v=barrel(b,at,code);v.SetUuid(via0.m_Uuid)
        for u,z in zip((anchor,elbow),(elbow,at)):
            if u!=z:b.Add(make(b,u,z,200000,code,p.F_Cu))
        b.Add(v);saved_parts.append(v)
        picked={"position_nm":at,"length_mm":length/1e6}
    records.append({"net":net,"retired_location_nm":anchor,"original_uuid":entry["uuid"],"terminal_tracks":len(tips),"stages":dict(stats),"candidate":picked})
folder=r/"runs/ddr-clock-b-fanout-shifts";folder.mkdir(exist_ok=True)
for fn in ("fp-lib-table","phy-joint.kicad_dru","phy-joint.kicad_pro"):shutil.copyfile(src.parent/fn,folder/fn)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],capture_output=True,check=True)
delta=introduced(json.loads((src.parent/"drc.json").read_text()),json.loads((folder/"drc.json").read_text()))
saved=p.LoadBoard(str(out));saved.BuildConnectivity();reconstructed=[]
for row in records:
    if not row["candidate"]:continue
    v=next(v for v in saved.GetTracks() if v.m_Uuid.AsString()==row["original_uuid"])
    contacts=[o for o in saved.GetConnectivity().GetConnectedItems(v) if o.GetClass()=="PCB_PAD" or o.GetClass()=="PAD"]
    assert len(contacts)>=1
    reconstructed.append(row["net"])
(r/"ddr-clock-b-fanout-shifts.json").write_text(json.dumps({"parent_sha256":cp["sha256"],"sha256":hashlib.sha256(out.read_bytes()).hexdigest(),"board":str(out.relative_to(r)),
    "cases":records,"recovered":reconstructed,"drc_delta":delta,"adopted":False},indent=2)+"\n")
print(len(reconstructed),len(held),dict(Counter(v["type"] for v in delta)))
