#!/usr/bin/env python3
"""Measure RGMII termination placement on the active checkpoint, not the archived floorplan."""
import hashlib,json,math
from pathlib import Path
import pcbnew as p
H=Path(__file__).resolve().parents[1];D=H/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text());source=D/cp['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(source));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()}
plan=json.loads((H/'review/highspeed-routing-plan.json').read_text());rows=[]
for path in plan['rgmii_paths']:
 ref=path['series']['component'];driver=path['source_ref'];net=path['net_segments'][0 if driver=='U1' else 1]
 def pin(name):
  pads=[q for q in fs[name].Pads() if q.GetNetname()==net]
  assert len(pads)==1,(name,net,len(pads))
  return pads[0]
 a,z=pin(driver),pin(ref)
 distance=p.ToMM(math.hypot(a.GetPosition().x-z.GetPosition().x,a.GetPosition().y-z.GetPosition().y))
 rows.append({'signal':path['signal'],'resistor':ref,'source':driver,'source_pin':a.GetNumber(),'source_net':net,
 'straight_line_pad_distance_mm':round(distance,4),
 'resistor_center_mm':[p.ToMM(fs[ref].GetPosition().x),p.ToMM(fs[ref].GetPosition().y)],
 'same_board_side':fs[ref].GetLayer()==fs[driver].GetLayer(),
 'connected_to_driver':z.m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(a)},
 'attached_copper_items':sum(len(b.GetConnectivity().GetConnectedTracks(q)) for q in fs[ref].Pads())})
report={'status':'CURRENT_RGMII_SOURCE_PLACEMENT_REVIEW','source_sha256':cp['sha256'],'rows':rows,
 'limits':['Source directions/net segments taken from the existing RGMII contract, pins resolved on the active RK3562 PCB.',
 'Distances are geometric lower bounds, not routed lengths, timing or signal-integrity results.',
 'No arbitrary pass threshold: source termination placement, BGA escape and matching remain to be designed.',
 'No footprint, net, resistor value or copper changed.'],'assembly_ready':False}
(D/'pcb/current-rgmii-placement.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
