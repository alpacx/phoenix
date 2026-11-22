"""Widen straight memory supply sections where same-layer clearance and adjacent signal projections permit."""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation

stage=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((stage/(n+'.json')).read_text())
source=read('layout-lpddr-vddq-source')
src=stage/source['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==source['sha256']
board=p.LoadBoard(str(src));original=p.LoadBoard(str(src))
uid=lambda o:o.m_Uuid.AsString()
nets=[('vddq-rail-first','+1V1_LPDDR4'),('vdd1-external-pair-trunk','+1V8_SYS')]
indices={uid(t):t for t in board.GetTracks()}
original_ground=[z for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
edges=[o.GetEffectiveShape(p.Edge_Cuts) for o in [*board.GetDrawings(),*(g for f in board.GetFootprints() for g in f.GraphicalItems())] if o.GetLayer()==p.Edge_Cuts]
all_items=[*board.GetTracks(),*(q for f in board.GetFootprints() for q in f.Pads())]
hi=('LPDDR4_','EMMC_','SOC_EMMC_','USB_','SOC_USB_','MUX_','ETH_','PHY_','WIFI_','ADDON_USB_')
changed=[];detail=[];stats=[]
for name,net in nets:
    route,=read(name)['records'];added=[indices[i] for i in route['added']]
    trunk=[];i=0
    while i<len(added):
        if isinstance(added[i],p.PCB_VIA):i+=4
        else:trunk.append(added[i]);i+=1
    metrics={'original_ohm':0.,'revised_ohm':0.}
    for old in trunk:
        layer=old.GetLayer();code=old.GetNetCode()
        assert old.GetWidth()==600000 and old.GetNetname()==net
        length=old.GetLength()
        thickness=35 if layer in (p.F_Cu,p.B_Cu) else 18
        metrics['original_ohm']+=1.724e-8*(length*1e-9)/(.0006*thickness*1e-6)
        a,z=tuple(old.GetStart()),tuple(old.GetEnd())
        segments=max(1,math.ceil(length/350000))
        points=[tuple(round(x+(y-x)*n/segments) for x,y in zip(a,z)) for n in range(segments+1)]
        box=inflated_box(old,1200000)
        nearby=[o for o in all_items if box.Intersects(o.GetBoundingBox()) and o.GetNetCode()!=code]
        layer_shapes=[o.GetEffectiveShape(layer) for o in nearby if o.IsOnLayer(layer)]
        holes=[o.GetEffectiveHoleShape() for o in nearby if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
        other={p.In2_Cu:p.In3_Cu,p.In3_Cu:p.In2_Cu}.get(layer)
        adjacent=[o.GetEffectiveShape(other) for o in nearby if other is not None and o.IsOnLayer(other) and o.GetNetname().startswith(hi)]
        keep=[zone.Outline() for zone in original_ground if zone.IsOnLayer(layer)]
        runs=[]
        for x,y in zip(points,points[1:]):
            for width in (1400000,1200000,1000000,800000,600000):
                if width==600000:break
                test=make(board,x,y,width,code,layer)
                shape=test.GetEffectiveShape(layer)
                if any(shape.Collide(s,202000) for s in layer_shapes):continue
                if any(shape.Collide(h,252000) for h in holes):continue
                if any(shape.Collide(s,252000) for s in edges):continue
                if any(shape.Collide(s,0) for s in keep):continue
                if any(shape.Collide(s,350000) for s in adjacent):continue
                break
            if runs and runs[-1][2]==width:runs[-1][1]=y
            else:runs.append([x,y,width])
        if all(w==600000 for _,_,w in runs):
            metrics['revised_ohm']+=1.724e-8*(length*1e-9)/(.0006*thickness*1e-6)
            continue
        changed.append(uid(old));board.Remove(old)
        # Update the obstacle inventory so the second rail also respects widened sections of the first.
        all_items.remove(old)
        new_ids=[]
        for x,y,w in runs:
            t=make(board,x,y,w,code,layer);board.Add(t);all_items.append(t);new_ids.append(uid(t))
            metrics['revised_ohm']+=1.724e-8*(t.GetLength()*1e-9)/(w*1e-9*thickness*1e-6)
        detail.append(dict(net=net,layer=old.GetLayerName(),original=uid(old),sections=runs,new_ids=new_ids))
    stats.append(dict(net=net,**metrics))
folder=stage/'runs/wide-memory-routes';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
out=folder/src.name
p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(out),board)
dr=folder/'drc.json'
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],check=True,capture_output=True)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()))
saved=p.LoadBoard(str(out));guard=verify_preservation(original,saved,replaced_copper=set(changed))
record=dict(parent_sha256=source['sha256'],board=str(out.relative_to(stage)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),replaced=changed,sections=detail,dc_estimate_18um_inner_35um_outer_20C=stats,net_clearance_mm=.202,opposite_high_speed_clearance_mm=.35,new_drc=delta,mounts=screen(saved),preservation=guard,assembly_ready=False)
(stage/'memory-trunk-widths.json').write_text(json.dumps(record,indent=2)+'\n')
print(len(changed),stats,delta[:3])
