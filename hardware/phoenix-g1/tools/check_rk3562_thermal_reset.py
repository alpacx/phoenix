"""Check the shutdown jumper and the routed reset distribution on a saved RK3562 board."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pcbnew

hardware = Path(__file__).resolve().parents[1]
stage = hardware / "migration-rk3562/experiments/phy-power-parallel"
checkpoint = json.loads(Path(sys.argv[1]).read_text())
layout = stage / checkpoint["board"]
assert hashlib.sha256(layout.read_bytes()).hexdigest() == checkpoint["sha256"]
board = pcbnew.LoadBoard(str(layout))
board.BuildConnectivity()
netlist = ET.parse(stage / "runs/schematic-mdio/netlist.xml")
parts = {c.get("ref"): c for c in netlist.findall(".//components/comp")}
with (hardware / "migration-rk3562/review/manufacturer-pins.csv").open() as pins_file:
    names = {row["ball"]: row["name"] for row in csv.DictReader(pins_file)}
assert "TSADC_SHUT_M0" in names["1R13"].split("/")
assert names["1P12"] == "nPOR"
assert "PWR_CTRL0" in names["AF23"].split("/")
assert parts["R1507"].findtext("value") == "0R"
expected = {
    "THERMAL_SHUTDOWN": {"U1.1R13", "R1507.1"},
    "RESET_N": {"R1507.2", "U1.1P12", "U4.67", "C411.1", "R412.2", "TP9.1", "U16.2", "R1103.1"},
    "PMIC_SLEEP": {"U1.AF23", "U4.49", "U10.A1"},
}
groups = {}
for net in netlist.findall(".//nets/net"):
    name = net.get("name")
    if name not in expected:
        continue
    actual = {node.get("ref") + "." + node.get("pin") for node in net.findall("node")}
    assert expected[name] == actual, (name, actual)
    pads = {}
    for label in sorted(actual):
        ref, number = label.split(".")
        pad = board.FindFootprintByReference(ref).FindPadByNumber(number)
        assert pad.GetNetname() == name
        pads[label] = pad
    groups[name] = []
    remaining = set(actual)
    while remaining:
        label = min(remaining)
        connected = {item.m_Uuid.AsString() for item in board.GetConnectivity().GetConnectedItems(pads[label])}
        group = {label} | {label for label in remaining if pads[label].m_Uuid.AsString() in connected}
        groups[name].append(sorted(group))
        remaining -= group
assert groups.keys() == expected.keys()
closed = all(len(groups[n]) == 1 for n in ("THERMAL_SHUTDOWN", "RESET_N"))
print(json.dumps({
    "board_sha256": checkpoint["sha256"], "family": "RK3562",
    "reference": "rk3562-oomwoo-reference.pdf, page 6, TSADC_SHUT_M0 and R1202",
    "documented_pad_functions_and_schematic_topology_match": True,
    "native_copper_pad_groups": groups, "full_shutdown_copper_path": closed,
    "hardware_trip_and_reset_measured": False,
}, indent=2))
