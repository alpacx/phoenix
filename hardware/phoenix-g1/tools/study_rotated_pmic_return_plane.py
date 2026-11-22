"""Test a solid local return pour, excluding the projections of inductors and hot copper."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pcbnew as pcb

from drc_regression import introduced
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'rotated-buck-return-pairs.json').read_text())
src=root/meta['board']
digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
assert digest(src)==meta['sha256']
original=pcb.LoadBoard(str(src));board=pcb.LoadBoard(str(src))
def rectangle(bounds):
    x,y,z,w=bounds
    shape=pcb.SHAPE_POLY_SET();idx=shape.NewOutline()
    for a,b in ((x,y),(z,y),(z,w),(x,w)):shape.Append(a,b,idx)
    return shape
def group(b):
    b.BuildConnectivity();g=b.FindFootprintByReference('U4').FindPadByNumber('69')
    return {obj.m_Uuid.AsString() for obj in b.GetConnectivity().GetConnectedItems(g)}
def pad(board,ref):
    return board.FindFootprintByReference(ref).FindPadByNumber('2')

outline=rectangle((52000000,500000,67200000,14600000))
switch_nets=set()
excluded=[]
for n in range(1,6):
    fp=board.FindFootprintByReference('L40'+str(n))
    switch_nets.add(fp.FindPadByNumber('1').GetNetname())
    box=fp.GetCourtyard(pcb.F_Cu).BBox()
    box.Inflate(200000)
    cut=(box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom())
    outline.BooleanSubtract(rectangle(cut));excluded.append(cut)
for t in board.GetTracks():
    if t.GetNetname() not in switch_nets:continue
    # This bounds every projected segment conservatively, also for diagonal tracks.
    box=t.GetBoundingBox();box.Inflate(200000)
    cut=(box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom())
    outline.BooleanSubtract(rectangle(cut));excluded.append(cut)
zone=pcb.ZONE(board);zone.SetLayer(pcb.B_Cu);zone.SetNetCode(board.FindNet('GND').GetNetCode())
zone.SetZoneName('RK809 local return study');zone.SetLocalClearance(250000)
zone.SetMinThickness(600000);zone.SetPadConnection(pcb.ZONE_CONNECTION_FULL)
zone.SetIslandRemovalMode(pcb.ISLAND_REMOVAL_MODE_ALWAYS);zone.Outline().Append(outline)
board.Add(zone)
folder=root/'runs/rotated-buck-return-zone';folder.mkdir(exist_ok=True)
for cfg in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/cfg,folder/cfg)
out=folder/src.name
pcb.ZONE_FILLER(board).Fill(board.Zones());pcb.SaveBoard(str(out),board)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
saved=pcb.LoadBoard(str(out));guard=verify_preservation(original,saved)
old_ground,new_ground=group(original),group(saved)
refs=[f'C{k}' for k in (421,422,431,432,470)]
new_caps=[r for r in refs if pad(original,r).m_Uuid.AsString() not in old_ground and pad(saved,r).m_Uuid.AsString() in new_ground]
z=next(z for z in saved.Zones() if z.GetZoneName()=='RK809 local return study')
polys=z.GetFilledPolysList(pcb.B_Cu)
copper=[]
def ring(chain):
    return [tuple(chain.CPoint(i)) for i in range(chain.PointCount())]
for i in range(polys.OutlineCount()):
    copper.append(dict(exterior=ring(polys.COutline(i)),holes=[ring(polys.CHole(i,j)) for j in range(polys.HoleCount(i))]))
anchors=[dict(at_nm=tuple(t.GetPosition()),drill_mm=t.GetDrillValue()/1e6,diameter_mm=t.GetWidth(pcb.B_Cu)/1e6,uuid=t.m_Uuid.AsString()) for t in original.GetTracks() if isinstance(t,pcb.PCB_VIA) and t.m_Uuid.AsString() in old_ground and t.GetViaType()==pcb.VIATYPE_THROUGH and t.GetDrillValue()>=200000 and 50000000<t.GetPosition().x<69000000 and t.GetPosition().y<17000000]
legs={r:dict(at_nm=tuple(pad(saved,r).GetPosition()),pad_size_nm=tuple(pad(saved,r).GetBoundingBox().GetSize())) for r in refs}
report=dict(parent_sha256=meta['sha256'],board=str(out.relative_to(root)),sha256=digest(out),new_drc=delta,preservation=guard,new_caps=new_caps,exclusion_boxes_nm=excluded,polygons=copper,anchors=anchors,lands=legs,accepted=False,assembly_ready=False)
(root/'rotated-buck-return-zone.json').write_text(json.dumps(report,indent=2)+'\n')
print(len(copper),len(new_caps),new_caps,len(delta),flush=True);os._exit(0)
