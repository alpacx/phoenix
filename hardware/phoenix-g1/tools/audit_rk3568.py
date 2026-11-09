#!/usr/bin/env python3
"""Extract manufacturer pin data and audit imported CAD, without inferring nets.

Run with Python containing sexpdata. Reference worksheet remains authoritative;
this check does not validate electrical connectivity or land-pattern dimensions.
"""
import csv
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET
import sexpdata

ROOT = Path(__file__).resolve().parents[1]
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

def fields(node, key):
    return [x for x in node if isinstance(x, list) and x and str(x[0]) == key]

def walk(node, key):
    if isinstance(node, list):
        if node and str(node[0]) == key:
            yield node
        for child in node:
            yield from walk(child, key)

def main():
    records = []
    with zipfile.ZipFile(ROOT / "reference/RK3568_PinOut_V1.1_20210202.xlsx") as archive:
        strings = ["".join(e.itertext()) for e in ET.fromstring(
            archive.read("xl/sharedStrings.xml")).findall("m:si", NS)]
        xml = ET.fromstring(archive.read("xl/worksheets/sheet6.xml"))
        group = ""
        domain = ""
        for row in xml.findall(".//m:row", NS):
            cells = {}
            for c in row:
                v = c.findtext("m:v", default="", namespaces=NS)
                cells[re.sub(r"\d", "", c.attrib["r"])] = strings[int(v)] if c.attrib.get("t") == "s" else v
            if cells.get("A", "").startswith("Part "):
                group = cells.get("B", "")
                domain = ""
            if not re.fullmatch(r"[A-Z]{1,2}\d{1,2}", cells.get("A", "")):
                continue
            if cells.get("C"):
                domain = cells["C"]
            records.append({"ball": cells["A"], "name": cells.get("B", ""),
                "group": group, "power_domain": domain, "type": cells.get("E", ""),
                "functions": " | ".join(cells.get(c, "") for c in "MNOPQR" if cells.get(c)),
                "reference_net": cells.get("S", ""),
                "voltage_cell": cells.get("D", ""),
                "source_row": row.attrib["r"]})
    with (ROOT / "review/rk3568-manufacturer-pins.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
    lib = sexpdata.loads((ROOT / "kicad/Phoenix_Candidates.kicad_sym").read_text())
    sym = next(x for x in fields(lib, "symbol") if x[1] == "RK3568")
    pins = [{"ball": str(fields(p, "number")[0][1]), "name": str(fields(p, "name")[0][1])}
            for p in walk(sym, "pin")]
    fp = sexpdata.loads((ROOT / "kicad/Phoenix_Candidates.pretty/BGA-636_L19.0-W19.0-P0.65-BL.kicad_mod").read_text())
    pads = [str(p[1]) for p in fields(fp, "pad") if p[1]]
    official = {p["ball"]: p for p in records}
    imported = {p["ball"]: p for p in pins}
    # Normalization intentionally limited. Mux names must be reviewed by a person.
    mismatches = [{"ball": b, "manufacturer": official[b]["name"], "imported": imported[b]["name"]}
                  for b in sorted(official.keys() & imported.keys())
                  if official[b]["name"] != imported[b]["name"]]
    result = {
        "status": "PIN INVENTORY ONLY; NOT an ERC, DRC or design approval",
        "source": "Rockchip RK3568 PinOut V1.1 20210202 worksheet 05.PinOut List",
        "manufacturer_count": len(records), "symbol_pin_count": len(pins), "footprint_pad_count": len(pads),
        "missing_symbol_balls": sorted(official.keys() - imported.keys()),
        "extra_symbol_balls": sorted(imported.keys() - official.keys()),
        "missing_footprint_balls": sorted(official.keys() - set(pads)),
        "extra_footprint_balls": sorted(set(pads) - official.keys()),
        "duplicate_symbol_balls": [b for b, n in Counter(p["ball"] for p in pins).items() if n > 1],
        "duplicate_footprint_balls": [b for b, n in Counter(pads).items() if n > 1],
        "name_differences_for_review": mismatches,
        "limitations": ["Power domain merged cells are filled downward only inside a part group.",
            "reference_net is Rockchip's reference design, NOT a Phoenix net assignment.",
            "Footprint coordinates, pad diameter, orientation and mask are NOT validated here."]}
    (ROOT / "review/rk3568-pin-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "name_differences_for_review"}, indent=2))
    print(f"Name differences requiring review: {len(mismatches)}")

if __name__ == "__main__":
    main()
