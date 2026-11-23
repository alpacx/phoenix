"""Check the prototype leaf sheet and its effect on the integrated RK3562 netlist."""
import json
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAD = HERE.parents[1] / "kicad"
CLI = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"


def pins(sheet, output):
    subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadxml",
                    "-o", str(output), str(sheet)], check=True)
    return {(item.get("ref"), item.get("pin")): net.get("name").lstrip("/")
            for net in ET.parse(output).findall(".//nets/net") for item in net.findall("node")}


def check_change(before, after):
    assert before.keys() == after.keys()
    assert {p for p in before if before[p] != after[p]} == {("U14", "2")}
    assert before["U14", "2"] == "CC_OUT2_N" and after["U14", "2"] == "GND"


with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    leaf = "usb-power-control.kicad_sch"
    check_change(pins(CAD / leaf, temp / "leaf-original.xml"),
                 pins(HERE / leaf, temp / "leaf-variant.xml"))
    project = temp / "integrated"
    shutil.copytree(CAD / "integrated", project)
    top = project / "phoenix-g1.kicad_sch"
    baseline = pins(top, temp / "before.xml")
    sheet = project / leaf
    original = sheet.read_text()
    old = '(global_label "CC_OUT2_N"'
    assert original.count(old) == 1
    sheet.write_text(original.replace(old, '(global_label "GND"'))
    variant = pins(top, temp / "after.xml")
    check_change(baseline, variant)
    assert variant["U6", "26"] == "CC_OUT2_N"
    assert variant["U14", "1"] == variant["U6", "25"] == "CC_OUT1_N"
    assert variant["U14", "4"] == variant["U19", "1"] == "USB_CURRENT_OK"
    assert variant["U19", "2"] == "AON_READY"
    assert variant["U19", "4"] == variant["U15", "2"] == "USB_MAIN_ENABLE"
    states = []
    for profile, out1, out2 in [("default", 1, 1), ("1.5 A", 0, 1), ("3 A", 0, 0)]:
        for ready in (False, True):
            states.append(dict(profile=profile, aon_ready=ready,
                               baseline_main=ready and not (out1 or out2),
                               prototype_main=ready and not out1))
    (HERE / "verification.json").write_text(json.dumps({
        "integrated_pin_assignments_compared": len(variant),
        "changed_pin": "U14.2: CC_OUT2_N -> GND",
        "scope": "KiCad logical connectivity and Boolean evaluation; static valid UFP states only",
        "states": states}, indent=2) + "\n")
