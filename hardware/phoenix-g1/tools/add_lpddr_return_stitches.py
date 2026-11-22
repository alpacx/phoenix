"""Add a GND reference transfer near each end of the routed LPDDR4 reset on the verified board."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
ordinary='--ordinary-data-returns' in sys.argv
command='--ca1-returns' in sys.argv
cke='--vdd1-cke' in sys.argv
radio='--radio-wake' in sys.argv
edge='--dqs-edge' in sys.argv
cp=json.loads((root/('bga-ordinary-barrels.json' if ordinary else 'ddr-command-in3-cu-compact-broadside.json' if command else 'vdd1-c2303-return.json' if cke else 'layout-radio-host-wake.json' if radio else 'layout-lpddr-dq0-reference.json' if edge else 'layout-pmic-pwron-filter.json')).read_text());cp=cp['candidate'] if cke else cp;src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();target='LPDDR4_A1_A' if command else 'LPDDR4_CKE0_A' if cke else 'WIFI_HOST_WAKE' if radio else 'LPDDR4_RESETN'
paired='--pair' in sys.argv or edge
folder=root/('runs/bga-ordinary-returns' if ordinary else 'runs/ddr-command-ca1-returns' if command else 'runs/vdd1-c2303-cke-return' if cke else 'runs/radio-wake-returns' if radio else 'runs/lpddr-dqs-edge' if edge else 'runs/lpddr-clock-return' if paired else 'runs/lpddr-reset-return');folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_dru','phy-joint.kicad_pro','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
baseline=json.loads((src.parent/'drc.json').read_text())
out=folder/src.name
vl=lambda xy:p.VECTOR2I(*xy)
uid=lambda o:o.m_Uuid.AsString()
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
gcode=b.FindNet('GND').GetNetCode()
def barrel(pt):
    v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(gcode);v.SetWidth(450000);v.SetDrill(200000);v.SetPosition(vl(pt));return v
def zone_at(board,layer,pt):
    return any(z.GetNetname()=='GND' and not z.GetIsRuleArea() and z.HasFilledPolysForLayer(layer) and z.GetFilledPolysList(layer).Contains(vl(pt)) for z in board.Zones())
def ground_barrels(board):
    joints=[t for t in board.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and t.IsOnLayer(p.In1_Cu) and t.IsOnLayer(p.In4_Cu)]
    joints.extend(q for f in board.GetFootprints() for q in f.Pads() if q.GetNetname()=='GND' and q.GetDrillSize().x and q.IsOnLayer(p.In1_Cu) and q.IsOnLayer(p.In4_Cu))
    return [tuple(o.GetPosition()) for o in joints if all(zone_at(board,layer,tuple(o.GetPosition())) for layer in [p.In1_Cu,p.In4_Cu])]
def check():
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    return introduced(baseline,json.loads((folder/'drc.json').read_text()))
zones=[z for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
allpads=[q for f in b.GetFootprints() for q in f.Pads()]
alltracks=list(b.GetTracks());signal_vias=sorted((t for t in alltracks if isinstance(t,p.PCB_VIA) and t.GetNetname()==target),key=lambda t:t.GetPosition().x)
assert len(signal_vias)==(8 if radio else 2)
tasks=[(q,None) for q in signal_vias]
if ordinary:
    moved={row["uuid"] for row in cp["moved"]}
    tasks=[(v,None) for v in alltracks if uid(v) in moved]
if cke:
    tasks=[q for q in tasks if uid(q[0])=='6dd809ab-eff2-41de-9c53-84164f8e5082']
    assert len(tasks)==1
if radio:
    reference={p.F_Cu:p.In1_Cu,p.In2_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu,p.B_Cu:p.In4_Cu}
    def crosses(via):
        pt=tuple(via.GetPosition())
        return len({reference[t.GetLayer()] for t in alltracks if not isinstance(t,p.PCB_VIA) and t.GetNetname()==target and pt in (tuple(t.GetStart()),tuple(t.GetEnd()))})>1
    tasks=[(via,None) for via in signal_vias if crosses(via)]
if paired:
    tasks=[]
    for family in ('DQS0','DQS1','CLK'):
        for channel in ('A','B'):
            group=[]
            for polarity in ('P','N'):
                name=f'LPDDR4_{family}{polarity}_{channel}'
                vs=[t for t in alltracks if isinstance(t,p.PCB_VIA) and t.GetNetname()==name]
                assert len(vs)==2
                group.append(sorted(vs,key=lambda t:t.GetPosition().x))
            tasks.extend(zip(*group))
if edge:
    tasks=[pair for pair in tasks if pair[0].GetNetname() in ('LPDDR4_DQS1P_B','LPDDR4_DQS0P_B')]
report=[]
for s,mate in tasks:
    signals=[tuple(i.GetPosition()) for i in (s,mate) if i is not None]
    centre=tuple(round(sum(pt[k] for pt in signals)/len(signals)) for k in (0,1))
    old=ground_barrels(b);before=[min(math.dist(pt,at) for at in old) for pt in signals];dist0=max(before)
    if edge and max(before)<3500000 or radio and max(before)<1500000:continue
    nearby=[o for o in list(b.GetTracks())+allpads if inflated_box(o,4400000 if edge else 3400000).Contains(vl(centre))]
    shapes=[(o.GetEffectiveShape(l),o.GetBoundingBox()) for o in nearby if o.GetNetCode()!=gcode for l in layers if o.IsOnLayer(l)]
    holes=[(o.GetEffectiveHoleShape(),o.GetPosition(),o.GetNetCode()) for o in nearby if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    lands=[q.GetEffectiveShape(q.GetParentFootprint().GetLayer()) for q in nearby if isinstance(q,p.PAD)]
    candidates=[];counts=Counter()
    radius=62 if edge else 44
    for dx in range(-radius,radius+1):
        for dy in range(-radius,radius+1):
            length=math.hypot(dx,dy)*50000
            if length>(3100000 if edge else 2200000 if paired else 1400000):continue
            at=(centre[0]+dx*50000,centre[1]+dy*50000)
            distances=[math.dist(pt,at) for pt in signals]
            if min(distances)<550000 or max(distances)>(3100000 if edge else 2250000 if paired else 1400000) or max(distances)-min(distances)>250000 or any(new>old-(700000 if edge else 400000) for old,new in zip(before,distances)):continue
            length=max(distances)
            o=barrel(at);sh=o.GetEffectiveShape(p.F_Cu);drill=o.GetEffectiveHoleShape();bb=inflated_box(o,400000)
            if any(bb.Contains(pos) and (drill.Collide(h,252000) or nc!=gcode and sh.Collide(h,250000)) for h,pos,nc in holes):continue
            if any(sh.Collide(land,100000) for land in lands):continue
            if any(bb.Intersects(box) and (sh.Collide(g,202000) or drill.Collide(g,252000)) for g,box in shapes):continue
            if any(z.Outline().Collide(sh,0) for z in zones):continue
            counts['copper_and_drill']+=1
            # Continuous GND disc on both sides of the dielectric stack; requires
            # solid copper beyond the via annulus, not just a coincident point.
            rim=[at]+[(at[0]+round(280000*math.cos(k*math.tau/16)),at[1]+round(280000*math.sin(k*math.tau/16))) for k in range(16)]
            if not all(zone_at(b,l,pt) for l in (p.In1_Cu,p.In4_Cu) for pt in rim):continue
            counts['solid_planes']+=1;candidates.append((length,at))
    attempts=[];picked=None
    for length,at in sorted(candidates):
        via=barrel(at);b.Add(via);delta=check()
        if not delta and not screen(b):
            saved=p.LoadBoard(str(out));saved.BuildConnectivity()
            q=next(t for t in saved.GetTracks() if uid(t)==uid(via));master=saved.FindFootprintByReference('U4').FindPadByNumber('69')
            ids={uid(t) for t in saved.GetConnectivity().GetConnectedItems(q)}
            if uid(master) in ids and all(zone_at(saved,l,at) for l in (p.In1_Cu,p.In4_Cu)):
                picked=dict(via_uuid=uid(via),center_nm=at,distance_mm=length/1e6);break
        attempts.append(dict(at=at,delta=delta))
        b.Remove(via)
    report.append(dict(signal_via=uid(s),signal_center_nm=signals,signals=[i.GetNetname() for i in (s,mate) if i is not None],previous_distances_mm=[x/1e6 for x in before],previous_nearest_ground_mm=dist0/1e6,candidates=counts,accepted=picked,rejected=attempts))
delta=check();probe=p.LoadBoard(str(out));probe.BuildConnectivity()
assert not delta and not screen(probe)
proof=verify_preservation(p.LoadBoard(str(src)),probe)
chosen=[r for r in report if r['accepted']]
assert proof['added_tracks_vias']==len(chosen)
record=dict(parent_sha256=cp['sha256'],sha256=hashlib.sha256(out.read_bytes()).hexdigest(),board=str(out.relative_to(root)),terminal_results=report,preservation=proof,new_drc=delta,verified_pairs=cp.get('verified_pairs',[]),assembly_ready=False)
(root/('bga-ordinary-returns.json' if ordinary else 'ddr-command-ca1-returns.json' if command else 'vdd1-c2303-cke-return.json' if cke else 'radio-wake-return-stitches.json' if radio else 'lpddr-dqs-edge-stitches.json' if edge else 'lpddr-clock-return-stitches.json' if paired else 'lpddr-reset-return-stitches.json')).write_text(json.dumps(record,indent=2)+'\n')
print([(r['previous_nearest_ground_mm'],r['candidates'],r['accepted']) for r in report],flush=True);os._exit(0)
