"""Check moved barrel geometry, fast reference-plane impact, and prior pad joins on reloaded KiCad files."""
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from pcb_bounds import inflated_box

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
load=lambda n:json.loads((root/(n+".json")).read_text())
referenced="--referenced-only" in sys.argv
cpu="--cpu-bypass" in sys.argv
c27="--c27" in sys.argv
base=load("layout-bga-referenced-barrel" if c27 or cpu else "layout-command-ca1");candidate=load("soc-c1601-local-placement")["candidate"] if cpu else load("bga-c27-referenced-barrel" if c27 else "bga-referenced-barrel" if referenced else "bga-ordinary-barrels")
def checked(d):
    file=root/d["board"]
    assert hashlib.sha256(file.read_bytes()).hexdigest()==d["sha256"]
    b=p.LoadBoard(str(file));b.BuildConnectivity()
    return b
before=checked(base);after=checked(candidate)
moved=candidate.get("moved",[])
changed={x["uuid"] for x in moved}
proof=verify_preservation(before,after,replaced_copper=changed)
old={t.m_Uuid.AsString():t for t in before.GetTracks()}
new={t.m_Uuid.AsString():t for t in after.GetTracks()}
refs={p.F_Cu:p.In1_Cu,p.In2_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu,p.B_Cu:p.In4_Cu}
def planes(board):
    return {l:next(z.GetFilledPolysList(l) for z in board.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(l)) for l in set(refs.values())}
ob=planes(before);nb=planes(after);local=[]
at=[t.GetPosition() for k in changed for t in (new[k],old[k])]
if cpu:at.extend(t.GetPosition() for k,t in new.items() if k not in old and isinstance(t,p.PCB_VIA))
for uid,t in old.items():
    if isinstance(t,p.PCB_VIA) or t.GetLayer() not in refs:continue
    if not t.GetNetname().startswith(("LPDDR4_","USB_","EMMC_","SOC_EMMC_","ETH_","PHY_","SOC_USB_","MUX_","WIFI_")):continue
    if not any(inflated_box(t,1900000).Contains(pos) for pos in at):continue
    l=refs[t.GetLayer()]
    area=p.SHAPE_POLY_SET();t.TransformShapeToPolygon(area,t.GetLayer(),200000,500,p.ERROR_OUTSIDE)
    area.BooleanIntersection(ob[l])
    area.BooleanSubtract(nb[l])
    local.append({"uuid":uid,"net":t.GetNetname(),"area_loss_mm2":area.Area()/1e12})
issues=[]
for row in moved:
    pad=after.FindFootprintByReference('U1').FindPadByNumber(row['pad'].split('.')[1])
    via=new[row["uuid"]]
    assert row["uuid"] in {o.m_Uuid.AsString() for o in after.GetConnectivity().GetConnectedItems(pad)}
    for f in after.GetFootprints():
        for q in f.Pads():
            if not q.IsOnLayer(p.F_Cu):continue
            if via.GetEffectiveShape(p.F_Cu).Collide(q.GetEffectiveShape(p.F_Cu),100000):issues.append((row["pad"],f.GetReference(),q.GetNumber()))
gnd_pad=after.FindFootprintByReference("U10").FindPadByNumber("B4")
gnd_ids={o.m_Uuid.AsString() for o in after.GetConnectivity().GetConnectedItems(gnd_pad)}
gnd_vias=[v for k,v in new.items() if isinstance(v,p.PCB_VIA) and k in gnd_ids]
old_master=before.FindFootprintByReference("U10").FindPadByNumber("B4")
old_gnd_ids={o.m_Uuid.AsString() for o in before.GetConnectivity().GetConnectedItems(old_master)}
old_gnd_vias=[v for k,v in old.items() if isinstance(v,p.PCB_VIA) and k in old_gnd_ids]
return_distance=[]
for item in moved:
    uid=item["uuid"]
    net=new[uid].GetNetname()
    nearest=lambda v,grounds:min(math.dist(tuple(v.GetPosition()), tuple(g.GetPosition())) for g in grounds)/1e6
    extra=[v for k,v in new.items() if k not in old and v.GetNetname()==net and v.GetLayer()==p.F_Cu]
    total=0;missing=0
    for t in extra:
        a,z=tuple(t.GetStart()),tuple(t.GetEnd())
        count=math.ceil(t.GetLength()/25000)
        for j in range(count):
            xy=p.VECTOR2I(*(round(u+(v-u)*(j+.5)/count) for u,v in zip(a,z)))
            total+=1
            if not nb[p.In1_Cu].Contains(xy):missing+=1
    return_distance.append({"net":net,"old_nearest_gnd_mm":nearest(old[uid],old_gnd_vias),"new_nearest_gnd_mm":nearest(new[uid],gnd_vias),"extension_mm":sum(t.GetLength() for t in extra)/1e6,"centerline_samples_without_plane":missing,"centerline_samples":total})
pairs=base["verified_pairs"]
def pad(name):
    ref,num=name.split(".");return after.FindFootprintByReference(ref).FindPadByNumber(num)
cache={}
for a,z in pairs:
    if a not in cache:cache[a]={o.m_Uuid.AsString() for o in after.GetConnectivity().GetConnectedItems(pad(a))}
    assert pad(z).m_Uuid.AsString() in cache[a]
drc=json.loads(((root/candidate["board"]).parent/"drc.json").read_text())
report=dict(board_sha256=candidate["sha256"],preservation=proof,prior_pairs_verified=len(pairs),nearby_existing_fast_segments=len(local),return_distance=return_distance,
    projected_area_losses=[t for t in local if t["area_loss_mm2"]>1e-7],via_land_margin_conflicts=issues,
    drc_counts=dict(Counter(v["type"] for v in drc["violations"])),minimum_joins=len(drc["unconnected_items"]))
(root/("cpu-bypass-referenced-preservation.json" if cpu else "bga-c27-barrel-preservation.json" if c27 else "bga-referenced-barrel-preservation.json" if referenced else "bga-ordinary-barrel-preservation.json")).write_text(json.dumps(report,indent=2)+"\n")
print(len(pairs),len(local),len(report["projected_area_losses"]),issues,report["minimum_joins"])
if cpu:
    added_pairs=[("C1601.1","U1."+ball) for ball in ("1G8","1H6","1H7","1H8","1J6","1J7")]
    added_pairs.append(("C1601.2","U10.B4"))
    for a,z in added_pairs:
        assert pad(z).m_Uuid.AsString() in {o.m_Uuid.AsString() for o in after.GetConnectivity().GetConnectedItems(pad(a))}
    assert not candidate["new_drc"] and not report["projected_area_losses"]
    assert not issues and not changed
    groups=base["open_nets"].copy()
    new_groups=[]
    netpads={n:pad(n) for group in groups["VDD_CPU"] for n in group}
    pending=set(netpads)
    while pending:
        n=min(pending)
        ids={o.m_Uuid.AsString() for o in after.GetConnectivity().GetConnectedItems(netpads[n])}
        group=sorted(q for q in pending if q==n or netpads[q].m_Uuid.AsString() in ids)
        pending.difference_update(group)
        new_groups.append(group)
    groups["VDD_CPU"]=new_groups
    assert sum(len(g)-1 for g in groups.values())==report["minimum_joins"]
    checkpoint=dict(board=candidate["board"],sha256=candidate["sha256"],parent_sha256=base["sha256"],
        verified_pairs=sorted({tuple(sorted(pair)) for pair in [*pairs,*added_pairs]}),preservation=proof,
        open_nets=groups,remaining_minimum_joins=report["minimum_joins"],new_drc=[],drc_counts=report["drc_counts"],
        assembly_ready=False,scope="HF bypass only. Converter output and processor power bank remain separate.")
    (root/"layout-cpu-local-hf-bypass.json").write_text(json.dumps(checkpoint,indent=2)+"\n")
