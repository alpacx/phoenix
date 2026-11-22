"""Reinstate original memory escape barrels wherever the trial clock and its return allow."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import pcbnew as p
from pcb_bounds import inflated_box
from drc_regression import introduced

r=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
def read(n):return json.loads((r/(n+".json")).read_text())
variant = "-preserved" if "--preserve-barrel" in sys.argv else ""
main=read("layout-command-ca1");release=read("ddr-clock-open-escape-release");clock=read("ddr-clock-b"+variant+"-physical")["candidate"]
def load(meta):
    path=r/meta["board"]
    assert hashlib.sha256(path.read_bytes()).hexdigest()==meta["sha256"]
    return p.LoadBoard(str(path))
original=load(main);b=load(clock)
ids={v.m_Uuid.AsString():v for v in original.GetTracks() if isinstance(v,p.PCB_VIA)}
nets={"LPDDR4_CLKP_B","LPDDR4_CLKN_B"}
clocks=[t for t in b.GetTracks() if t.GetNetname() in nets and not isinstance(t,p.PCB_VIA)]
planes={l:next(z.GetFilledPolysList(l) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(l)) for l in (p.In1_Cu,p.In4_Cu)}
projections=[]
for t in clocks:
    area=p.SHAPE_POLY_SET()
    t.TransformShapeToPolygon(area,t.GetLayer(),200000,500,p.ERROR_OUTSIDE)
    area.BooleanIntersection(planes[p.In1_Cu if t.GetLayer() in (p.F_Cu,p.In2_Cu) else p.In4_Cu])
    projections.append(area)
restored=[];held=[]
for entry in release["released"]:
    v=ids[entry["uuid"]];loc=v.GetPosition()
    geometry=[t.GetNetname() for t in clocks if inflated_box(t,700000).Contains(loc) and
              (t.GetEffectiveShape(t.GetLayer()).Collide(v.GetEffectiveShape(t.GetLayer()),202000) or t.GetEffectiveShape(t.GetLayer()).Collide(v.GetEffectiveHoleShape(),252000))]
    plane_conflicts=any(area.Collide(loc,430000) for area in projections)
    if geometry or plane_conflicts:
        held.append(dict(entry,copper=sorted(set(geometry)),reference=plane_conflicts));continue
    copy=v.Duplicate();copy.SetUuid(v.m_Uuid);b.Add(copy);restored.append(entry["uuid"])
folder=r/("runs/ddr-clock-b"+variant+"-recovered");folder.mkdir(exist_ok=True)
src=r/clock["board"]
for fn in ("fp-lib-table","phy-joint.kicad_dru","phy-joint.kicad_pro"):shutil.copyfile(src.parent/fn,folder/fn)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],capture_output=True,check=True)
saved=p.LoadBoard(str(out));saved.BuildConnectivity()
def terminal(name):
    ref,pin=name.split(".");return saved.FindFootprintByReference(ref).FindPadByNumber(pin)
verified=0;cache={}
for a,z in main["verified_pairs"]+clock["pairs"]:
    cache.setdefault(a,None)
    if cache[a] is None:cache[a]={o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(terminal(a))}
    assert terminal(z).m_Uuid.AsString() in cache[a]
    verified+=1
original_drc=json.loads(((r/main["board"]).parent/"drc.json").read_text())
new_drc=json.loads((folder/"drc.json").read_text())
from collections import Counter
report={"parent_sha256":clock["sha256"],"baseline_sha256":main["sha256"],"board":str(out.relative_to(r)),"sha256":hashlib.sha256(out.read_bytes()).hexdigest(),
        "original_vias_recovered":restored,"still_requiring_relocation":held,"verified_pairs":verified,"drc_relative_to_adopted":dict(Counter(v["type"] for v in introduced(original_drc,new_drc))),"adopted":False}
(r/("ddr-clock-b"+variant+"-recovered.json")).write_text(json.dumps(report,indent=2)+"\n")
print(len(restored),len(held),verified,report["drc_relative_to_adopted"])
