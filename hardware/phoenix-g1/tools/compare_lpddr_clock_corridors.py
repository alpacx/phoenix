"""Test whether exploratory CA copper consumes the central routing corridor of each clock pair."""
from pathlib import Path
import hashlib
import json
import math
import subprocess
import sys
import pcbnew as p


root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
report=[];transfers=[]
pair_route="--route-both" in sys.argv
reverse="--b-first" in sys.argv
bridge="--reserve-bridge" in sys.argv
release="--freed-escapes" in sys.argv or pair_route
transfer = "--split-a" in sys.argv
labels = ("ddr-clock-b-preserved-recovered", "ddr-clock-b-preserved-physical") if transfer else (("ddr-clock-open-escape-release",) if release else ("layout-command-ca1","ddr-ca-group-shielded"))
for label in labels:
    meta=json.loads((root/(label+".json")).read_text())
    if "candidate" in meta: meta = meta["candidate"]
    src=root/meta["board"];assert hashlib.sha256(src.read_bytes()).hexdigest()==meta["sha256"]
    b=p.LoadBoard(str(src));b.BuildConnectivity()
    vias={t.m_Uuid.AsString():t for t in b.GetTracks() if isinstance(t,p.PCB_VIA)}
    reserved=[]
    for channel in (("A",) if transfer else (("B","A") if reverse else ("A","B"))):
        clock_names=["LPDDR4_CLK"+pol+"_"+channel for pol in ("P","N")]
        source=[];sink=[]
        for name in clock_names:
            for ref,arr in (("U1",source),("U2",sink)):
                ball=next(q for q in b.FindFootprintByReference(ref).Pads() if q.GetNetname()==name)
                group=b.GetConnectivity().GetConnectedItems(ball)
                v,=[vias[t.m_Uuid.AsString()] for t in group if t.m_Uuid.AsString() in vias]
                arr.append(tuple(v.GetPosition()))
        centers=[[round(sum(a[i] for a in arr)/2) for i in (0,1)] for arr in (source,sink)]
        codes={b.FindNet(n).GetNetCode() for n in clock_names}
        fronts={}
        for face,reference in ((p.F_Cu,p.In1_Cu),(p.In2_Cu,p.In1_Cu),(p.In3_Cu,p.In4_Cu),(p.B_Cu,p.In4_Cu)):
            seg=[(tuple(t.GetStart()),tuple(t.GetEnd()),t.GetWidth(face) if isinstance(t,p.PCB_VIA) else t.GetWidth()) for t in b.GetTracks() if t.IsOnLayer(face) and t.GetNetCode() not in codes]
            pads=[]
            for fp in b.GetFootprints():
                for pad in fp.Pads():
                    if pad.IsOnLayer(face) and pad.GetNetCode() not in codes:
                        bb=pad.GetBoundingBox();pads.append([bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()])
            zones=[q for q in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if q.GetIsRuleArea() and q.IsOnLayer(face) and q.GetDoNotAllowTracks()]
            def points(poly):return [tuple(poly.CPoint(i)) for i in range(poly.PointCount())]
            excludes=[points(z.Outline().Outline(i)) for z in zones for i in range(z.Outline().OutlineCount())]
            poly=next(z.GetFilledPolysList(reference) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(reference))
            plane=[[points(poly.Outline(i)),[points(poly.Hole(i,j)) for j in range(poly.HoleCount(i))]] for i in range(poly.OutlineCount())]
            if pair_route and face!=p.In3_Cu:continue
            if bridge and not reserved and channel==("B" if reverse else "A"):
                prior="ddr-clock-b-first-middle.json" if reverse else "ddr-clock-a-first-middle.json"
                unresolved=json.loads((root/prior).read_text())["rows"][1]
                u,v=unresolved["nearest_gap"]["positions_nm"]
                seg.append((u,v,650000))
            if pair_route:seg.extend((u,v,650000) for path in reserved for u,v in zip(path,path[1:]))
            req={"centers":centers,"geometry":[seg,pads,excludes],"plane":plane}
            if pair_route:req.update(route=True,released_nm=[row["location_nm"] for row in meta["released"]])
            if transfer and label.endswith("recovered") and face in (p.F_Cu, p.In2_Cu):
                (Path("/tmp")/("phoenix-clock-a-"+b.GetLayerName(face)+".json")).write_text(json.dumps(req))
            if "--export-b" in sys.argv and channel=="B" and face==p.In3_Cu:
                print(json.dumps(req));sys.exit()
            result=json.loads(subprocess.run(["python3",str(Path(__file__).with_name("lpddr_clock_corridor_grid.py"))],input=json.dumps(req),text=True,capture_output=True,check=True).stdout)
            if pair_route and result["middle"]:reserved.append(result["middle"]["points_nm"])
            fronts[b.GetLayerName(face)]=[set(map(tuple,p)) for p in result.pop("reachable")]
            report.append(dict(checkpoint=label,sha256=meta["sha256"],channel=channel,layer=b.GetLayerName(face),**result))
        intersections=[]
        for layer,initial in fronts.items():
            for dest,final in fronts.items():
                if layer==dest:continue
                common=initial[0] & final[1]
                if transfer and label.endswith("recovered") and (layer,dest)==("F.Cu","In2.Cu"):
                    (Path("/tmp")/"phoenix-clock-a-transfer-centers.json").write_text(json.dumps({"sha256":meta["sha256"],"centers":sorted(common)}))
                intersections.append({"layers":[layer,dest],"common_grid_centers":len(common),"sample_nm":sorted(common)[::max(1,len(common)//5)][:5]})
        transfers.append({"checkpoint":label,"channel":channel,"transfers":intersections})
(root/("ddr-clock-a-split-after-b.json" if transfer else "ddr-clock-b-first-bridge.json" if bridge and reverse else "ddr-clock-a-first-bridge.json" if bridge else "ddr-clock-b-first-middle.json" if reverse else "ddr-clock-a-first-middle.json" if pair_route else "ddr-clock-released-corridors.json" if release else "ddr-ca-clock-corridor-comparison.json")).write_text(json.dumps({"rows":report,"optimistic_transfers":transfers,"assumptions":"Centerline screens a 0.20+0.25+0.20 mm pair envelope with 0.202 mm outside copper clearance and 0.10 mm lateral return margin. Accessible ideal gates within 1.5 mm of each pair of barrels; specific pair fanout, equal electrical length, differential conversion and impedance remain untested."},indent=2)+"\n")
print([(r["checkpoint"],r["channel"],r["layer"],r["gates_connected"]) for r in report])
