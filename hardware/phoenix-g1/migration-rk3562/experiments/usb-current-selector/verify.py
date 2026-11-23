"""Run with KiCad Python. Check the integrated schematic and the saved selector PCB."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import pcbnew

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "phy-power-parallel"
CLI = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"


def export_pins(project, output):
    subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadxml",
                    "-o", str(output), str(project / "phoenix-g1.kicad_sch")], check=True)
    root = ET.parse(output)
    return {(node.get("ref"), node.get("pin")): net.get("name")
            for net in root.findall(".//nets/net") for node in net.findall("node")}


def findings(report):
    return Counter((entry["type"], entry["severity"], tuple(sorted(item["uuid"] for item in entry["items"])))
                   for entry in report["violations"])


def verify():
    parent = json.loads((PARENT / "layout-pmic-image-c468.json").read_text())
    board_path = HERE / "phy-joint.kicad_pcb"
    checkpoint = json.loads((HERE / "verification.json").read_text())
    parent_board = PARENT / parent["board"]
    for path, expected in [(board_path, checkpoint["pcb_sha256"]), (parent_board, checkpoint["parent"])]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path
    board = pcbnew.LoadBoard(str(board_path))
    board.BuildConnectivity()

    def pad(key):
        ref, pin = key.split(".")
        return board.FindFootprintByReference(ref).FindPadByNumber(pin)

    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        integrated = HERE.parents[1] / "kicad/integrated"
        original = export_pins(integrated, temp / "original.xml")
        project = temp / "integrated"
        shutil.copytree(integrated, project)
        shutil.copy(HERE / "usb-power-control.kicad_sch", project)
        variant = export_pins(project, temp / "selector.xml")
        expected = dict(original)
        for key, net in {"U14.2": "USB_CURRENT_SEL_N", "R1104.1": "CC_OUT2_N",
                         "R1104.2": "USB_CURRENT_SEL_N", "R1105.1": "GND",
                         "R1105.2": "USB_CURRENT_SEL_N"}.items():
            expected[tuple(key.split("."))] = net
            assert pad(key).GetNetname() == net, key
        assert expected == variant
        for ref, optional in [("R1104", False), ("R1105", True)]:
            footprint = board.FindFootprintByReference(ref)
            assert footprint.IsDNP() == optional and footprint.GetValue() == "0R", ref

        subprocess.run([CLI, "pcb", "drc", "--format", "json", "-o", str(temp / "drc.json"),
                        str(board_path)], check=True)
        current = json.loads((temp / "drc.json").read_text())
        baseline = json.loads(parent_board.with_name("drc.json").read_text())
        assert findings(current) == findings(baseline)
        assert len(current["unconnected_items"]) == len(baseline["unconnected_items"])

    islands = {}

    def connected(first, second):
        if first not in islands:
            islands[first] = {item.m_Uuid.AsString() for item in board.GetConnectivity().GetConnectedItems(pad(first))}
        return pad(second).m_Uuid.AsString() in islands[first]

    for pair in parent["verified_pairs"]:
        first, second = ["R1104.1" if pin == "U14.2" else pin for pin in pair]
        assert connected(first, second), pair
    for first, second in [("U14.2", "R1104.2"), ("U14.2", "R1105.2"), ("U6.26", "R1104.1"),
                          ("U14.3", "R1105.1")]:
        assert connected(first, second), (first, second)
    print(f"{len(original)} original pin assignments compared; {len(parent['verified_pairs'])} retained pairs verified.")
    for first, second in [("U15.7", "R1201.1"), ("R1201.2", "TP1.1"), ("U15.1", "C1202.1"), ("U15.5", "TP3.1")]:
        assert connected(first, second), (first, second)


if __name__ == "__main__":
    verify()
