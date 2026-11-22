"""Compare the RK3562 SoC core bypass population with the page-4 reference and its placement zones."""
from pathlib import Path
import hashlib
import json
import re

import pcbnew as p
root=Path(__file__).resolve().parents[1]
stage=root/"migration-rk3562/experiments/phy-power-parallel"
cp=json.loads((stage/"layout-bga-referenced-barrel.json").read_text())
pcb=stage/cp["board"]
assert hashlib.sha256(pcb.read_bytes()).hexdigest()==cp["sha256"]
board=p.LoadBoard(str(pcb))
bom={c["ref"]:c for c in json.loads((root/"migration-rk3562/review/bom-inventory.json").read_text())["components"]}
cpu=board.FindFootprintByReference("U1").GetCourtyard(p.F_Cu)
sheets={"VDD_CPU":[.1,1,1,1,22,22],"VDD_GPU":[.1,1,1,1,22,22],"VDD_NPU":[.1,1,1,1,22,22],"VDD_LOGIC":[.1,1,1,1,22,22,1,22]}
inventory={}
for net,reference in sheets.items():
    caps=[]
    for fp in board.GetFootprints():
        ref=fp.GetReference()
        if bom.get(ref,{}).get("sheet")!="/soc-core-bypass/":continue
        if {q.GetNetname() for q in fp.Pads()}!={net,"GND"}:continue
        value=re.match(r"(\d+(?:\.\d+)?)\s*([nu])",fp.GetValue())
        area=fp.GetCourtyard(fp.GetLayer()).Area()/1e12
        caps.append({"ref":ref,"selected_mpn":bom[ref]["selected_mpn"],"package":fp.GetFPIDAsString(),"cap_uf":float(value[1])*(.001 if value[2]=="n" else 1),"courtyard_area_mm2":area,"center_in_soc_courtyard_xy":cpu.Contains(fp.GetPosition()),"side":fp.GetLayerName()})
    inventory[net]={"parts":sorted(caps,key=lambda c:c["ref"]),"design_total_uf":round(sum(q["cap_uf"] for q in caps),3),"reference_total_uf":sum(reference),"reference_values_uf":reference,"design_total_courtyard_mm2":round(sum(q["courtyard_area_mm2"] for q in caps),3)}
report={"board_sha256":cp["sha256"],"reference":"reference/rk3562-oomwoo-reference.pdf, sheet 4. VDD_LOGIC_MEM is tied to VDD_LOGIC in this reference; values include both branches.","rails":inventory,"limitations":"Only the SoC bypass sheet. Excludes regulator-side capacitors and all other sheets. Nominal capacitor sums and two-dimensional envelope only. No change in population or schematic authorized by this comparison alone."}
(stage/"soc-core-capacitor-comparison.json").write_text(json.dumps(report,indent=2)+"\n")
print([(n,x["design_total_uf"],x["reference_total_uf"],x["design_total_courtyard_mm2"]) for n,x in inventory.items()])
