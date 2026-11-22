"""Export the integrated design with its reviewed MDIO correction and compare numbered pads."""
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pcbnew

experiments = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments"
stage = experiments / "phy-power-parallel"
seed = experiments / "emmc-system/system/kicad/integrated"
checkpoint = stage / "layout-rgmii-short-source-clock.json"
board_info = json.loads(checkpoint.read_text())
board_path = stage / board_info["board"]
assert hashlib.sha256(board_path.read_bytes()).hexdigest() == board_info["sha256"]
board = pcbnew.LoadBoard(str(board_path))
output = stage / "runs/schematic-mdio/integrated"
output.mkdir(parents=True, exist_ok=True)
for path in sorted(seed.glob("*.kicad_sch")):
    shutil.copyfile(path, output / path.name)
sheet = output / "ethernet-phy.kicad_sch"
before = sheet.read_text()
corrected = before
for old, new in (("1.8k", "1.5k"), ("C163481", "C114759"), ("RC0402FR-071K8L", "RC0402FR-071K5L")):
    assert before.count(old) == 1
    corrected = corrected.replace(old, new)
assert corrected == (stage / "runs/mdio-pullup" / sheet.name).read_text()
sheet.write_text(corrected)
# Select the resistor independently of the accessory branch load qualification.
source_record = json.loads((experiments.parents[1] / "sourcing/public/C25877.json").read_text())
assert source_record["componentModelEn"] == "0402WGF2101TCE"
addon = output / "expansion-power.kicad_sch"
text = addon.read_text()
start = text.index('(property "Reference" "R8101"')
end = text.index('(instances', start)
symbol_fields = text[start:end]
assert symbol_fields.count('"UNQUALIFIED"') == 1
assert symbol_fields.count('"2.1k 1% candidate"') == 1
symbol_fields = symbol_fields.replace('"UNQUALIFIED"', '"0402WGF2101TCE"').replace('"2.1k 1% candidate"', '"2.1k 1%"')
symbol_fields += '(property "JLCPCB" "C25877" (at 215.2 60.96 0) (effects (font (size 1 1)) hide)) '
addon.write_text(text[:start] + symbol_fields + text[end:])
# Align only this candidate export to the three parts fitted in the routed study.
phy_selection = {
    "C511": ("CL10A475KP8NNNC", "C1705"),
    "C515": ("CL10A475KO8NNNC", "C19666"),
    "L501": ("AFE252012S2R2MBT", "C22459322"),
}
support = output / "ethernet-support.kicad_sch"
text = support.read_text()
for ref, (mpn, jlc) in phy_selection.items():
    start = text.index(f'(property "Reference" "{ref}"')
    end = text.index('(instances', start)
    component = text[start:end]
    footprint = board.FindFootprintByReference(ref)
    for label, value in (("Value", footprint.GetValue()), ("Footprint", footprint.GetFPIDAsString()),
                         ("MPN", mpn), ("JLCPCB", jlc)):
        component, count = re.subn(r'\(property "' + label + r'" "[^"]*"', f'(property "{label}" "{value}"', component)
        assert count == 1
    assert 'CANDIDATE - NOT QUALIFIED' in component
    text = text[:start] + component + text[end:]
support.write_text(text)
# Bind all twelve units of the candidate SoC only after comparing the physical ball map.
soc = board.FindFootprintByReference("U1")
library, name = soc.GetFPIDAsString().split(":")
local_library = seed.parent / (library + ".pretty")
library_soc = pcbnew.FootprintLoad(str(local_library), name)
def ball_geometry(fp):
    return sorted((pad.GetNumber(), tuple(pad.GetFPRelativePosition()), tuple(pad.GetSize()),
                   pad.GetShape(), pad.GetAttribute(), tuple(pad.GetLayerSet().Seq())) for pad in fp.Pads())
assert library_soc and len(list(soc.Pads())) == 478 and ball_geometry(soc) == ball_geometry(library_soc)
soc_units = sorted(output.glob("rk3562-pins-*.kicad_sch"))
assert len(soc_units) == 12
for unit in soc_units:
    text = unit.read_text()
    start = text.index('(property "Reference" "U1"')
    end = text.index('(instances', start)
    instance = text[start:end]
    assert instance.count('(property "Footprint" ""') == 1
    instance = instance.replace('(property "Footprint" ""', f'(property "Footprint" "{library}:{name}"')
    unit.write_text(text[:start] + instance + text[end:])
xml = output.parent / "netlist.xml"
cli = shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
subprocess.run([cli, "sch", "export", "netlist", "--format", "kicadxml", "-o", str(xml),
                str(output / "phoenix-g1.kicad_sch")], check=True)
doc = ET.parse(xml)
parts = {c.get("ref"): c for c in doc.findall(".//components/comp")}
assert parts["U1"].findtext("footprint") == soc.GetFPIDAsString()
r8101_fields = {field.get("name"): field.text for field in parts["R8101"].findall("fields/field")}
assert parts["R8101"].findtext("value") == "2.1k 1%"
assert r8101_fields["MPN"] == "0402WGF2101TCE" and r8101_fields["JLCPCB"] == "C25877"
footprints = {f.GetReference(): f for f in board.GetFootprints()}
pins = {(n.get("ref"), n.get("pin")): net.get("name") for net in doc.findall(".//nets/net")
        for n in net.findall("node") if not net.get("name").startswith("unconnected-")}
pads = {}
differences = []
attributes = []
absent_fields = {}
resolved_libraries = {}
missing = []
def field_value(fp, name):
    try:
        return fp.GetFieldText(name)
    except KeyError:
        return ""


for ref, fp in sorted(footprints.items()):
    if ref not in parts:
        continue
    c = parts[ref]
    for pad in fp.Pads():
        key = ref, pad.GetNumber()
        actual = pad.GetNetname()
        pads.setdefault(key, []).append(actual)
        if actual.startswith("unconnected-"):
            actual = ""
        if actual != pins.get(key, ""):
            differences.append([*key, pins.get(key, ""), actual])
    fields = {f.get("name"): f.text for f in c.findall("fields/field")}
    mismatch = {}
    for name, a, b in (("value", c.findtext("value"), fp.GetValue()),
                        ("footprint", c.findtext("footprint"), fp.GetFPIDAsString()),
                        ("MPN", fields.get("MPN"), field_value(fp, "MPN")),
                        ("JLCPCB", fields.get("JLCPCB"), field_value(fp, "JLCPCB"))):
        if name in ("MPN", "JLCPCB") and a and not b:
            absent_fields.setdefault(name, []).append(ref)
            continue
        if (a or "") != (b or ""):
            mismatch[name] = [a, b]
    if "footprint" in mismatch:
        sch_id, pcb_id = mismatch["footprint"]
        if sch_id and ":" not in pcb_id and sch_id.endswith(":" + pcb_id):
            library_name, item_name = sch_id.split(":")
            local = pcbnew.FootprintLoad(str(seed.parent / (library_name + ".pretty")), item_name)
            assert local
            scratch = pcbnew.BOARD()
            scratch.Add(local)
            if fp.IsFlipped():
                local.Flip(local.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
            assert ball_geometry(fp) == ball_geometry(local), ref
            resolved_libraries[ref] = {"library_id": sch_id, "matching_pads": len(list(fp.Pads()))}
    if mismatch:
        attributes.append({"ref": ref, "differences": mismatch})
for key, net in sorted(pins.items()):
    if key not in pads:
        missing.append([*key, net])
report = dict(board_sha256=board_info["sha256"], schematic="runs/schematic-mdio/integrated/phoenix-g1.kicad_sch",
              schematic_parts=len(parts), pcb_footprints=len(footprints), distinct_board_pad_numbers_compared=len(pads),
              schematic_only=sorted(parts.keys()-footprints.keys()), board_only=sorted(footprints.keys()-parts.keys()),
              mismatched_existing_pad_nets=differences, connected_schematic_pins_without_pads=missing,
              attributes=attributes, matched_library_pad_geometry=resolved_libraries, schematic_fields_absent_from_pcb=absent_fields, pcb_layout_qualified=False)
(stage / "routed-schematic-parity.json").write_text(json.dumps(report, indent=2)+"\n")
print(len(differences), len(missing), len(attributes))
