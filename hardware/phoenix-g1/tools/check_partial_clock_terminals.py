"""Verify all four package clock connections on the reloaded split-terminal coupon."""
from pathlib import Path
import hashlib
import json
import sys

import pcbnew as p

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
mode=sys.argv[1]
src=root/"runs"/mode/"phy-joint.kicad_pcb"
board=p.LoadBoard(str(src))
board.BuildConnectivity()
rows=[]
for channel in "AB":
    for polarity in "PN":
        net="LPDDR4_CLK"+polarity+"_"+channel
        pads=[next(pad for pad in board.FindFootprintByReference(ref).Pads() if pad.GetNetname()==net) for ref in ("U1","U2")]
        connected={q.m_Uuid.AsString() for q in board.GetConnectivity().GetConnectedItems(pads[0])}
        rows.append({"net":net,"source":"U1."+pads[0].GetNumber(),"sink":"U2."+pads[1].GetNumber(),"connected":pads[1].m_Uuid.AsString() in connected})
report={"board_sha256":hashlib.sha256(src.read_bytes()).hexdigest(),"board":str(src.relative_to(root)),"rows":rows}
(root/(mode+"-pins.json")).write_text(json.dumps(report,indent=2)+"\n")
print([(row["net"],row["connected"]) for row in rows])
