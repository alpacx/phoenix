"""Inventory all nominal RK860 output bypasses, including load-side SoC decoupling."""
import hashlib
import json
from pathlib import Path
import re

import pcbnew as p

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
checkpoint=json.loads((root/"layout-cpu-local-hf-bypass.json").read_text())
pcb=root/checkpoint["board"]
assert hashlib.sha256(pcb.read_bytes()).hexdigest()==checkpoint["sha256"]
board=p.LoadBoard(str(pcb))
board.BuildConnectivity()
def connected(ref,pin):
    pad=board.FindFootprintByReference(ref).FindPadByNumber(pin)
    return {item.m_Uuid.AsString() for item in board.GetConnectivity().GetConnectedItems(pad)}
upstream=connected("L1001","2")
processor=connected("U1","1H6")
return_plane=connected("U10","B4")
caps=[]
for f in board.GetFootprints():
    if not f.GetReference().startswith("C"):continue
    pins={q.GetNetname():q for q in f.Pads()}
    if set(pins)!={"VDD_CPU","GND"}:continue
    value=re.match(r"(\d+(?:\.\d+)?)\s*([un])",f.GetValue(),re.I)
    assert value, f.GetValue()
    caps.append(dict(ref=f.GetReference(),uf=float(value[1])*(.001 if value[2]=="n" else 1),
        reaches_processor=pins["VDD_CPU"].m_Uuid.AsString() in processor,
        reaches_output=pins["VDD_CPU"].m_Uuid.AsString() in upstream,
        reaches_ground=pins["GND"].m_Uuid.AsString() in return_plane))
total=round(sum(c["uf"] for c in caps),3)
attached=sum(c["uf"] for c in caps if c["reaches_ground"] and c["reaches_output"])
report={"board_sha256":checkpoint["sha256"],"caps":sorted(caps,key=lambda c:c["ref"]),
        "processor_grounded_capacitance_uf":sum(c["uf"] for c in caps if c["reaches_ground"] and c["reaches_processor"]),
        "processor_connected_to_output":bool(processor & upstream),
        "design_total_uf":total,"connected_both_terminals_uf":attached,
        "local_datasheet":"reference/RK860-0-C19188628.pdf, Rev 1.2 pp. 5–6",
        "recommended_cout_uf":[44,88],"full_population_fraction_at_88uf":88/total,
        "qualification":"Nominal inventory. The frequency-dependent load at the regulator depends on capacitance versus bias, temperature and tolerance, ESR, ESL, rail distribution and the RK860 loop. C1020 is in the feedback network and excluded. Measure a load transient and qualify the effective load; the local capacitor count alone does not bound the final load."}
(root/"cpu-external-buck-cap-budget.json").write_text(json.dumps(report,indent=2)+"\n")
print(total,attached,[(c["ref"],c["reaches_output"],c["reaches_ground"]) for c in caps])
