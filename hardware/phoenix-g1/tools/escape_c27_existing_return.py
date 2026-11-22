"""Try the only through-via site sharing a close ground with the U1.C27 DDR data escape."""
from pathlib import Path
import hashlib
import json
import subprocess

import pcbnew as p
from phy_corridor_path import geometry

tools=Path(__file__).resolve().parent
r=tools.parent/"migration-rk3562/experiments/phy-power-parallel"
read=lambda n:json.loads((r/(n+".json")).read_text())
cp=read("layout-bga-referenced-barrel")
path=r/cp["board"]
assert hashlib.sha256(path.read_bytes()).hexdigest()==cp["sha256"]
b=p.LoadBoard(str(path));b.BuildConnectivity()
sites=next(row["positions_nm"] for row in read("bga-existing-returns")["trials"] if row["pad"]=="U1.C27")
pad=b.FindFootprintByReference("U1").FindPadByNumber("C27")
connected={t.m_Uuid.AsString() for t in b.GetConnectivity().GetConnectedItems(pad)}
via,=[v for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and v.m_Uuid.AsString() in connected]
ground=next(z.GetFilledPolysList(p.In1_Cu) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(p.In1_Cu))
def pts(q):return [tuple(q.CPoint(i)) for i in range(q.PointCount())]
plane=[[pts(ground.Outline(i)),[pts(ground.Hole(i,j)) for j in range(ground.HoleCount(i))]] for i in range(ground.OutlineCount())]
keepout=[pts(z.Outline().Outline(i)) for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(p.F_Cu) for i in range(z.Outline().OutlineCount())]
req=dict(plane=plane,geometry=[*geometry(b,p.F_Cu,pad.GetNetCode(),oval_caps=True),keepout],max_path_nm=6500000,reference_half_width_nm=200000,compact_45=True)
rows=[]
for site in sites:
    for pos in (tuple(via.GetPosition()),tuple(pad.GetPosition())):
        proc=subprocess.run(["python3",str(tools/"ddr_plane_grid.py")],input=json.dumps(dict(req,via_nm=[pos,site])),text=True,capture_output=True,check=True)
        rows.append({"origin":pos,"site":site,"result":json.loads(proc.stdout)})
(r/"bga-c27-offset-return.json").write_text(json.dumps({"board_sha256":cp["sha256"],"rows":rows},indent=2)+"\n")
print(rows)
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
import shutil
from collections import Counter
options=[row for row in rows if "path" in row["result"] and tuple(row["origin"])==tuple(via.GetPosition())]
if options:
    chosen=options[0];via.SetPosition(p.VECTOR2I(*chosen["site"]))
    route=chosen["result"]["path"]
    for a,z in zip(route,route[1:]):b.Add(make(b,a,z,200000,pad.GetNetCode(),p.F_Cu))
    folder=r/"runs/bga-c27-offset-return";folder.mkdir(exist_ok=True)
    for f in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):shutil.copyfile(path.parent/f,folder/f)
    file=folder/path.name
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(file)],check=True,capture_output=True)
    saved=p.LoadBoard(str(file));saved.BuildConnectivity()
    native=json.loads((folder/"drc.json").read_text())
    delta=introduced(json.loads((path.parent/"drc.json").read_text()),native)
    audit=verify_preservation(p.LoadBoard(str(path)),saved,replaced_copper=[via.m_Uuid.AsString()])
    report={"board":str(file.relative_to(r)),"sha256":hashlib.sha256(file.read_bytes()).hexdigest(),"parent_sha256":cp["sha256"],"preservation":audit,"native_delta":delta,"counts":dict(Counter(v["type"] for v in native["violations"])),"mechanical_conflicts":screen(saved),"moved":[{"pad":"U1.C27","uuid":via.m_Uuid.AsString(),"via_site_nm":chosen["site"],"tail_start_nm":chosen["origin"]}],"adopted":False}
    (r/"bga-c27-referenced-barrel.json").write_text(json.dumps(report,indent=2)+"\n")
    print(len(delta),report["mechanical_conflicts"])
