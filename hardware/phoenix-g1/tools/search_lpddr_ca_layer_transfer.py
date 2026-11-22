"""Search for a common returned via between independently reachable CA fanout regions."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import shutil
import pcbnew as p
from phy_corridor_path import geometry
from pcb_bounds import inflated_box
from pcb_power_leg import barrel, make
from drc_regression import introduced
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
base=json.loads((root/"layout-command-ca1.json").read_text())
src=root/base["board"];assert hashlib.sha256(src.read_bytes()).hexdigest()==base["sha256"]
b=p.LoadBoard(str(src));b.BuildConnectivity()
info=json.loads((root/"ddr-reference-command-ca1.json").read_text());assert info["source_sha256"]==base["sha256"]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
refs={p.F_Cu:p.In1_Cu,p.In2_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu,p.B_Cu:p.In4_Cu}
def points(line):return [tuple(line.CPoint(i)) for i in range(line.PointCount())]
planes={}
for l in (p.In1_Cu,p.In4_Cu):
    poly=next(z.GetFilledPolysList(l) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(l))
    planes[l]=[[points(poly.Outline(i)),[points(poly.Hole(i,j)) for j in range(poly.HoleCount(i))]] for i in range(poly.OutlineCount())]
all_tracks=list(b.GetTracks());all_pads=[q for f in b.GetFootprints() for q in f.Pads()]
ground={t.m_Uuid.AsString() for t in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('U4').FindPadByNumber('69'))}
returns=[t for t in all_tracks if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in ground]
keepouts=[z for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea()]
all_shapes={l:[(o.GetNetCode(),o.GetBoundingBox(),o.GetEffectiveShape(l)) for o in all_tracks+all_pads if o.IsOnLayer(l)] for l in layers}
all_holes=[(o.GetBoundingBox(),o.GetEffectiveHoleShape()) for o in all_tracks+all_pads if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
protect="--protect-reference" in sys.argv
sensitive_prefixes=("LPDDR4_","USB_","MUX_","SOC_USB_","ADDON_USB_","EMMC_","SOC_EMMC_","ETH_","PHY_","WIFI_")
guard_traces=[t for t in all_tracks if not isinstance(t,p.PCB_VIA) and t.GetLayer() in refs and t.GetNetname().startswith(sensitive_prefixes)]
covered_cache={}
poly_zones={l:next(z.GetFilledPolysList(l) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(l)) for l in (p.In1_Cu,p.In4_Cu)}
def projected_clear(pt,code):
    at=p.VECTOR2I(*pt)
    for t in guard_traces:
        if t.GetNetCode()==code or not inflated_box(t,680000).Contains(at):continue
        key=t.m_Uuid.AsString()
        if key not in covered_cache:
            poly=p.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(poly,t.GetLayer(),200000,500,p.ERROR_OUTSIDE)
            poly.BooleanIntersection(poly_zones[refs[t.GetLayer()]])
            covered_cache[key]=poly
        if covered_cache[key].Collide(at,430000):return False
    return True
def valid_via(pt,code):
    v=barrel(b,pt,code);bb=inflated_box(v,350000);metal=v.GetEffectiveShape(p.F_Cu);drill=v.GetEffectiveHoleShape()
    if any(bb.Intersects(box) and drill.Collide(h,252000) for box,h in all_holes):return False
    if any(q.HitTest(p.VECTOR2I(*pt)) for q in all_pads):return False
    if any(z.GetDoNotAllowVias() and z.Outline().Collide(metal,0) for z in keepouts):return False
    if protect and not projected_clear(pt,code):return False
    return not any(n!=code and bb.Intersects(box) and (metal.Collide(sh,202000) or drill.Collide(sh,252000)) for l in layers for n,box,sh in all_shapes[l])
def backtrack(mapping,point,start):
    result=[point];seen=set()
    while point!=start:
        assert point not in seen
        seen.add(point);point=mapping[point][0];result.append(point)
    return result[::-1]
rows=[]
compare="--record-returned" in sys.argv
reserve="--reserve-group" in sys.argv
requested=set(sys.argv[1:])-{"--record-returned","--reserve-group","--protect-reference"}
for netrow in info["nets"]:
    name=netrow["net"]
    if not name.startswith(("LPDDR4_A","LPDDR4_CKE","LPDDR4_CS")) or netrow["escape_via_counts"]!=[1,1] or requested and name not in requested:continue
    ends=[tuple(q) for q in netrow["via_nm"]];code=b.FindNet(name).GetNetCode();maps={}
    requests={}
    for l,reference in refs.items():
        blocks=[points(z.Outline().Outline(i)) for z in keepouts if z.IsOnLayer(l) and z.GetDoNotAllowTracks() for i in range(z.Outline().OutlineCount())]
        args=dict(plane=planes[reference],geometry=[*geometry(b,l,code,oval_caps=True),blocks],collect_frontier=True,reference_half_width_nm=200000)
        if l in (p.In2_Cu,p.In3_Cu):
            other=p.In3_Cu if l==p.In2_Cu else p.In2_Cu
            args["projected_foreign"]=[[tuple(t.GetStart()),tuple(t.GetEnd()),t.GetWidth()] for t in all_tracks if not isinstance(t,p.PCB_VIA) and t.GetLayer()==other and t.GetNetCode()!=code]
        requests[l]=args.copy()
        for i in (0,1):
            args["via_nm"]=[ends[i],ends[1-i]]
            f=json.loads(subprocess.run(["python3",str(Path(__file__).with_name("ddr_plane_grid.py"))],input=json.dumps(args),text=True,capture_output=True,check=True).stdout)
            maps[l,i]={tuple(pt):(tuple(prev),cost) for pt,prev,cost in f.get("frontier",[])}
    trials=[];best=None
    for x in refs:
        for y in refs:
            if x==y:continue
            first,second=maps[x,0],maps[y,1];common=first.keys() & second.keys();legal=0; metal_clear=0;returned=0;shortest_returned=None
            for at in common:
                if not valid_via(at,code):continue
                metal_clear+=1
                dist=min(math.dist(at,tuple(v.GetPosition())) for v in returns)
                if dist>1000000:continue
                returned+=1
                length=first[at][1]+second[at][1]
                if shortest_returned is None or length<shortest_returned:shortest_returned=length
                if not compare and length>1.35*math.dist(*ends):continue
                legal+=1
                if not best or length<best["length_nm"]:
                    best={"via_nm":at,"layers":[b.GetLayerName(x),b.GetLayerName(y)],"length_nm":length,
                          "return_via_mm":dist/1e6,"paths":[backtrack(first,at,ends[0]),backtrack(second,at,ends[1])]}
            trials.append([b.GetLayerName(x),b.GetLayerName(y),len(common),legal,metal_clear,returned,shortest_returned])
    if reserve and best:
        pts=[];items=[];via_xy=tuple(best["via_nm"])
        for i,layer_name in enumerate(best["layers"]):
            l=b.GetLayerID(layer_name);args=requests[l].copy()
            args.update(collect_frontier=False,compact_45=True,via_nm=ends,preset_path=best["paths"][i])
            routed=json.loads(subprocess.run(["python3",str(Path(__file__).with_name("ddr_plane_grid.py"))],input=json.dumps(args),text=True,capture_output=True,check=True).stdout)
            if not routed.get("path"):break
            pts.append(routed["path"])
            items.extend(make(b,a0,a1,200000,code,l) for a0,a1 in zip(routed["path"],routed["path"][1:]))
        if len(pts)==2:
            v=barrel(b,via_xy,code);items.append(v)
            for item in items:
                b.Add(item);all_tracks.append(item)
                for l in layers:
                    if item.IsOnLayer(l):all_shapes[l].append((code,item.GetBoundingBox(),item.GetEffectiveShape(l)))
            all_holes.append((v.GetBoundingBox(),v.GetEffectiveHoleShape()))
            best["paths"]=pts
            best["reserved"]=True
            best["length_nm"]=sum(t.GetLength() for t in items if not isinstance(t,p.PCB_VIA))
        else:
            best["reserved"]=False
    rows.append({"net":name,"frontier_sizes":{b.GetLayerName(l):[len(maps[l,i]) for i in (0,1)] for l in refs},"layer_changes":trials,"candidate":best})
    print(name,len([k for k in trials if k[2]]),bool(best),flush=True)
label="-"+"-".join(sorted(requested)) if requested else ""
if compare:label+="-returned"
if protect:label+="-shielded"
if reserve:
    label+="-group"
    folder=root/("runs/ddr-ca-group-shielded" if protect else "runs/ddr-ca-group-corridor")
    folder.mkdir(exist_ok=True)
    for filename in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):
        shutil.copyfile(src.parent/filename,folder/filename)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/"drc.json").read_text()),json.loads((folder/"drc.json").read_text()))
    saved=p.LoadBoard(str(out));saved.BuildConnectivity()
    proof=verify_preservation(p.LoadBoard(str(src)),saved)
    joined=[]
    for row in rows:
        if not row["candidate"] or not row["candidate"].get("reserved"):continue
        a,z=[next(q for q in saved.FindFootprintByReference(n).Pads() if q.GetNetname()==row["net"]) for n in ("U1","U2")]
        assert any(o.m_Uuid.AsString()==z.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(a))
        joined.append(["U1."+a.GetNumber(),"U2."+z.GetNumber()])
    report={"parent_sha256":base["sha256"],"sha256":hashlib.sha256(out.read_bytes()).hexdigest(),"board":str(out.relative_to(root)),
            "preservation":proof,"joined":joined,"native_drc_delta":delta,"adopted":False}
    (root/("ddr-ca-group-shielded.json" if protect else "ddr-ca-group-corridor.json")).write_text(json.dumps(report,indent=2)+"\n")
(root/("ddr-ca-transfer"+label+".json")).write_text(json.dumps({"parent_sha256":base["sha256"],"rows":rows,"adopted":False},indent=2)+"\n")
