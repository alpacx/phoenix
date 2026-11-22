"""Measure the filled RF image plane under each trace for both six-layer stack widths."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pcbnew as p

from drc_regression import introduced

root = Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
rebased = "--usb-direction" in sys.argv
checkpoint = "rf-external-usb-direction" if rebased else "rf-external-return-cleanup"
suffix = "-usb-direction" if rebased else ""
cp = json.loads((root/(checkpoint + ".json")).read_text())
src = root/cp["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest() == cp["sha256"]
records = {}
live = []
for label,width in [("7628",None),("3313",154000)]:
    b = p.LoadBoard(str(src))
    live.append(b)
    trace = [t for t in b.GetTracks() if t.GetNetname() in ("WIFI_RF","WIFI_ANT")]
    assert trace and all(t.GetLayer()==p.B_Cu and not isinstance(t,p.PCB_VIA) for t in trace)
    candidate=src
    findings=[]
    if width:
        for t in trace:t.SetWidth(width)
        folder=root/("runs/rf-external-3313-normalized" + suffix);folder.mkdir(exist_ok=True)
        for name in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):
            shutil.copy2(src.parent/name,folder/name)
        candidate=folder/src.name
        p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(candidate),b)
        subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(candidate)],capture_output=True,check=True)
        findings=introduced(json.loads((src.parent/"drc.json").read_text()),json.loads((folder/"drc.json").read_text()))
        b=p.LoadBoard(str(candidate));live.append(b)
        trace=[t for t in b.GetTracks() if t.GetNetname() in ("WIFI_RF","WIFI_ANT")]
    b.BuildConnectivity()
    verified = []
    for anchor, sinks in [(("U25","2"), [("R2001","1"),("R2005","1")]),
                          (("R2001","2"), [("J2001","1")]),
                          (("U4","69"), [("J2001","2"),("J2001","3"),("C2008","2"),("C2009","2")])]:
        pad = b.FindFootprintByReference(anchor[0]).FindPadByNumber(anchor[1])
        items = {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pad)}
        for ref, pin in sinks:
            assert b.FindFootprintByReference(ref).FindPadByNumber(pin).m_Uuid.AsString() in items
            verified.append([".".join(anchor), ref + "." + pin])
    ground=p.SHAPE_POLY_SET()
    for z in b.Zones():
        if z.GetNetname()=="GND" and z.IsOnLayer(p.In4_Cu) and z.HasFilledPolysForLayer(p.In4_Cu):ground.BooleanAdd(z.GetFilledPolysList(p.In4_Cu))
    assert ground.Area()>0
    results={}
    for name in ("WIFI_RF","WIFI_ANT"):
        segments=[t for t in trace if t.GetNetname()==name]
        assert segments,name
        projection=[]
        for margin in (0,100000,200000,300000,500000):
            envelope=p.SHAPE_POLY_SET()
            for t in segments:
                shape=p.SHAPE_POLY_SET();t.TransformShapeToPolygon(shape,p.B_Cu,margin,500,p.ERROR_OUTSIDE)
                envelope.BooleanAdd(shape)
            area=envelope.Area()
            envelope.BooleanSubtract(ground)
            projection.append(dict(lateral_margin_mm=margin/1e6,area_mm2=area/1e12,missing_ground_mm2=envelope.Area()/1e12))
        results[name]=dict(length_mm=sum(t.GetLength() for t in segments)/1e6,widths_mm=sorted({t.GetWidth()/1e6 for t in segments}),reference_plane="In4.Cu",projected_areas=projection)
    records[label]=dict(board=str(candidate.relative_to(root)),sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),rf=results,added_drc=findings,verified_pad_pairs=verified)
out=dict(parent_sha256=cp["sha256"],stacks=records,polygon_chord_tolerance_mm=.0005,scope="Saved RF trace copper projected onto the adjacent filled GND zone. Excludes pad and enclosure discontinuities and measured return loss.",assembly_ready=False)
(root/("rf-external-plane-projection" + suffix + ".json")).write_text(json.dumps(out,indent=2)+"\n")
for name,v in records.items():print(name,len(v["added_drc"]),[(n,[a["missing_ground_mm2"] for a in rec["projected_areas"]]) for n,rec in v["rf"].items()],flush=True)
os._exit(0)
