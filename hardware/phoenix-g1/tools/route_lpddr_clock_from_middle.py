"""Verify both clock legs from actual signal escape barrels around the common trunk."""
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
from pcb_power_leg import make
from drc_regression import introduced
from pcb_preservation import verify_preservation

tools=Path(__file__).resolve().parent;r=tools.parent/"migration-rk3562/experiments/phy-power-parallel"
base=json.loads((r/"ddr-clock-open-escape-release.json").read_text());src=r/base["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest()==base["sha256"]
channel="A" if "--a" in sys.argv else "B"
core=json.loads((r/("ddr-clock-"+channel.lower()+"-first-middle.json")).read_text())["rows"][0]
assert core["channel"]==channel and core["sha256"]==base["sha256"]
variant = ""
if "--preserve-barrel" in sys.argv:
    assert channel == "B"
    trials = json.loads((r/"ddr-clock-b-barrel-reservations.json").read_text())["trials"]
    best = min((t for t in trials if t["middle"]), key=lambda t:(t["nearby_barrels"], t["middle"]["length_mm"]))
    core["middle"] = best["middle"]
    variant = "-preserved"
offsets=json.loads(subprocess.run(["python3",str(tools/"make_clock_center_offsets.py")],input=json.dumps(core["middle"]),text=True,capture_output=True,check=True).stdout)
forced_flip = "--flip-trunk" in sys.argv
if forced_flip:
    variant += "-flipped"
layer=p.In3_Cu;ref=p.In4_Cu
def pts(geom):return [tuple(geom.CPoint(i)) for i in range(geom.PointCount())]
attempts=[];winner=None
for flip in ((True,) if forced_flip else (False,True)):
    for reverse in (False,True):
        b=p.LoadBoard(str(src));b.BuildConnectivity()
        tracks=list(b.GetTracks());vias={v.m_Uuid.AsString():v for v in tracks if isinstance(v,p.PCB_VIA)}
        plane=next(z.GetFilledPolysList(ref) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(ref))
        plane_shapes=[[pts(plane.Outline(i)),[pts(plane.Hole(i,j)) for j in range(plane.HoleCount(i))]] for i in range(plane.OutlineCount())]
        names=["LPDDR4_CLK"+pol+"_"+channel for pol in ("P","N")];anchors={}
        for n,net in enumerate(names):
            ends=[]
            for refname in ("U1","U2"):
                q=next(q for q in b.FindFootprintByReference(refname).Pads() if q.GetNetname()==net)
                v,=[vias[t.m_Uuid.AsString()] for t in b.GetConnectivity().GetConnectedItems(q) if t.m_Uuid.AsString() in vias]
                ends.append(tuple(v.GetPosition()))
            path=offsets[n^flip];code=b.FindNet(net).GetNetCode()
            for a,z in zip(path,path[1:]):b.Add(make(b,a,z,200000,code,layer))
            anchors[net]=(ends,[path[0],path[-1]])
        diagnostics=[];completed=0
        for net in (names[::-1] if reverse else names):
            code=b.FindNet(net).GetNetCode();ends,tips=anchors[net]
            for idx,(a,z) in enumerate(zip(ends,tips)):
                pads=[q for q in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if q.GetIsRuleArea() and q.IsOnLayer(layer) and q.GetDoNotAllowTracks()]
                ex=[pts(q.Outline().Outline(i)) for q in pads for i in range(q.Outline().OutlineCount())]
                req=dict(via_nm=[a,z],plane=plane_shapes,geometry=[*geometry(b,layer,code,oval_caps=True),ex],compact_45=True,reference_half_width_nm=200000,max_path_nm=3500000)
                found=json.loads(subprocess.run(["python3",str(tools/"ddr_plane_grid.py")],input=json.dumps(req),text=True,capture_output=True,check=True).stdout)
                diagnostics.append({"net":net,"end":idx,"result":found})
                if "path" not in found:continue
                for a,z in zip(found["path"],found["path"][1:]):b.Add(make(b,a,z,200000,code,layer))
                completed+=1
        attempts.append({"flip":flip,"reverse":reverse,"four_leads_routed":completed,"leads":diagnostics})
        if completed!=4:continue
        folder=r/("runs/ddr-clock-"+channel.lower()+variant+"-physical");folder.mkdir(exist_ok=True)
        for f in ("fp-lib-table","phy-joint.kicad_dru","phy-joint.kicad_pro"):shutil.copyfile(src.parent/f,folder/f)
        out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],capture_output=True,check=True)
        delta=introduced(json.loads((src.parent/"drc.json").read_text()),json.loads((folder/"drc.json").read_text()))
        attempts[-1]["native_drc_delta"]=delta
        if delta:continue
        saved=p.LoadBoard(str(out));saved.BuildConnectivity();proof=verify_preservation(p.LoadBoard(str(src)),saved)
        pairs=[]
        for name in names:
            a,z=[next(q for q in saved.FindFootprintByReference(n).Pads() if q.GetNetname()==name) for n in ("U1","U2")]
            assert z.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(a)}
            pairs.append(["U1."+a.GetNumber(),"U2."+z.GetNumber()])
        winner={"board":str(out.relative_to(r)),"sha256":hashlib.sha256(out.read_bytes()).hexdigest(),"pairs":pairs,"preservation":proof};break
    if winner:break
(r/("ddr-clock-"+channel.lower()+variant+"-physical.json")).write_text(json.dumps({"parent_sha256":base["sha256"],"attempts":attempts,"candidate":winner,"adopted":False},indent=2)+"\n")
print(channel,[x["four_leads_routed"] for x in attempts],bool(winner))
