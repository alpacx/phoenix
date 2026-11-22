"""Estimate planar delays for routed CA groups and bound the still open clock span."""
import hashlib
import json
import math
import sys
from pathlib import Path
import pcbnew as p

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
c27 = "--bga-c27" in sys.argv
c27base = "--bga-c27-base" in sys.argv
preserved = "--clock-b-preserved" in sys.argv
checkpoint = "bga-c27-referenced-barrel" if c27 else "layout-bga-referenced-barrel" if c27base else "ddr-clock-b-preserved-recovered" if preserved else "ddr-ca-group-shielded"
coupon=json.loads((root/(checkpoint+".json")).read_text());src=root/coupon["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest()==coupon["sha256"]
board=p.LoadBoard(str(src));board.BuildConnectivity()
stacks=json.loads((root/"usb-ddr-stack-simulation.json").read_text())["stacks"]
stacks.update(json.loads((root/"jlc-close-reference-stack-simulation.json").read_text())["stacks"])
records=[]
speed_mm_per_ps=.299792458
for n in (([f"DQ{n}_B" for n in range(8,16)]+["DQS1P_B","DQS1N_B"]) if c27 or c27base else ("CLKP_B","CLKN_B") if preserved else ("A0_A","A1_A","CLKP_A","CLKN_A","A0_B","CLKP_B","CLKN_B")):
    name="LPDDR4_"+n
    pins=[next(q for q in board.FindFootprintByReference(k).Pads() if q.GetNetname()==name) for k in ("U1","U2")]
    terminals=[{t.m_Uuid.AsString() for t in board.GetConnectivity().GetConnectedItems(pin)} for pin in pins]
    linked=pins[1].m_Uuid.AsString() in terminals[0]
    traces=[t for t in board.GetTracks() if t.GetNetname()==name and not isinstance(t,p.PCB_VIA)]
    vias=[t for t in board.GetTracks() if t.GetNetname()==name and isinstance(t,p.PCB_VIA)]
    assert all(t.m_Uuid.AsString() in terminals[0] | terminals[1] for t in traces+vias)
    linears={}
    for t in traces:
        key=(t.GetLayerName(),t.GetWidth()/1e6)
        linears[key]=linears.get(key,0)+t.GetLength()/1e6
    gap=0
    if not linked:
        anchors=[[tuple(v.GetPosition()) for v in vias if v.m_Uuid.AsString() in group] for group in terminals]
        gap=min((math.dist(a,z)/1e6 for a in anchors[0] for z in anchors[1]),default=None)
    models={}
    for stack,spec in stacks.items():
        delay=0;sections=[]
        for (layer,width),length in linears.items():
            rows=[r for r in spec["outside" if layer in ("F.Cu","B.Cu") else "inner"]
                  if r["mode"]=="single" and not r.get("opposite_layer_aligned_grounded_track",False)]
            row=min(rows,key=lambda r:abs(r["width_mm"]-width))
            delay+=length*math.sqrt(row["effective_er"])/speed_mm_per_ps
            sections.append([layer,width,round(length,3),row["width_mm"],round(row["ohms"],1)])
        models[stack]={"estimated_present_planar_delay_ps":round(delay,2),"sections_layer_width_length_model_width_ohms":sections}
    records.append({"net":name,"linked_pins":linked,"copper_trace_sum_mm":round(sum(linears.values()),3),
                    "unrouted_via_to_via_straight_distance_mm":round(gap,3) if gap is not None else None,"barrels":len(vias),"models":models})
report={"board_sha256":coupon["sha256"],"records":records,"timing_closed":False,
        "interpretation":"Planar copper-length inventory of the connected terminal groups. Uniform-line estimate uses nearest simulated width and ignores via delay, terminal capacitance, reference discontinuities, package delays and PVT. An unrouted clock's straight distance is a geometric lower bound. No setup/hold result is inferred. Source-synchronous package-plus-PCB timing budgets must come from RK3562 and the chosen DRAM."}
(root/("bga-c27-byte-budget.json" if c27 else "bga-c27-base-byte-budget.json" if c27base else "ddr-clock-b-preserved-budget.json" if preserved else "ddr-command-clock-budget.json")).write_text(json.dumps(report,indent=2)+"\n")
print([(r["net"],r["linked_pins"],r["copper_trace_sum_mm"],r["unrouted_via_to_via_straight_distance_mm"]) for r in records])
