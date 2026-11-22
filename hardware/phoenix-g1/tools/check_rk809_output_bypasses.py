"""Check all nine RK809 LDO bypasses against the schematic and the routed copper."""
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pcbnew

stage = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments/phy-power-parallel"
checkpoint = json.loads(Path(sys.argv[1]).read_text())
path = stage / checkpoint["board"]
assert hashlib.sha256(path.read_bytes()).hexdigest() == checkpoint["sha256"]
board = pcbnew.LoadBoard(str(path))
board.BuildConnectivity()
netlist = ET.parse(stage / "runs/schematic-mdio/netlist.xml")
nets = {(p.get("ref"), p.get("pin")): net.get("name")
        for net in netlist.findall(".//nets/net") for p in net.findall("node")}
parts = {c.get("ref"): c for c in netlist.findall(".//components/comp")}
pmic = board.FindFootprintByReference("U4")
ground_id = pmic.FindPadByNumber("69").m_Uuid.AsString()
def connected_items(pad):
    return {item.m_Uuid.AsString() for item in board.GetConnectivity().GetConnectedItems(pad)}


rows = []
# Pin assignment in Rockchip RK809-5 datasheet section 2.8.
for channel, number in enumerate((23, 21, 20, 28, 29, 31, 3, 5, 6), start=1):
    ref = f"C{459 + channel}"
    cap = board.FindFootprintByReference(ref)
    out = pmic.FindPadByNumber(str(number))
    pos = cap.FindPadByNumber("1")
    neg = cap.FindPadByNumber("2")
    assert nets[ref, "1"] == nets["U4", str(number)] == out.GetNetname() == pos.GetNetname()
    assert nets[ref, "2"] == neg.GetNetname() == "GND"
    assert parts[ref].findtext("value") == cap.GetValue()
    positive = connected_items(pos)
    output_group = connected_items(out)
    gnd = ground_id in connected_items(neg)
    has_bypass = out.m_Uuid.AsString() in positive and gnd
    loads = [p for p in board.FindFootprintByReference("U1").Pads() if p.GetNetname() == pos.GetNetname()]
    rows.append({"ldo": channel, "pin": number, "net": pos.GetNetname(), "capacitor": ref,
                 "nominal_part_value": cap.GetValue(), "output_and_capacitor_connected": out.m_Uuid.AsString() in positive,
                 "capacitor_ground_connected": gnd, "bypass_copper_complete": has_bypass,
                 "soc_pads_on_named_rail": sorted(p.GetNumber() for p in loads),
                 "soc_pads_joined_to_output": sorted(p.GetNumber() for p in loads if p.m_Uuid.AsString() in output_group)})
print(json.dumps({"board_sha256": checkpoint["sha256"], "ldo_count": len(rows),
                  "complete_local_bypasses": sum(row["bypass_copper_complete"] for row in rows), "rows": rows,
                  "basis": "RK809-5 pinout, schematic netlist, native KiCad connectivity on reloaded PCB",
                  "loop_stability_or_physical_operation_tested": False}, indent=2))
