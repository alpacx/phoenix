#!/usr/bin/env python3
"""Report straight-line source-to-series-pad distance, never routed length."""
import json, math
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[1]
board=p.LoadBoard(str(ROOT/'kicad/floorplan/phoenix-g1-floorplan.kicad_pcb'))
fp={f.GetReference():f for f in board.GetFootprints()}
plan=json.loads((ROOT/'review/highspeed-routing-plan.json').read_text());rows=[]
for path in plan['rgmii_paths']:
 source=path['source_ref'];ref=path['series']['component'];net=path['net_segments'][0 if source=='U1' else 1]
 def pad(r):
  found=[q for q in fp[r].Pads() if q.GetNetname()==net]
  assert len(found)==1,(r,net,len(found))
  return found[0]
 a,b=pad(source),pad(ref);aa,bb=a.GetPosition(),b.GetPosition()
 rows.append({'signal':path['signal'],'resistor':ref,'source':source,'source_pin':a.GetNumber(),'source_net':net,'straight_line_pad_distance_mm':round(p.ToMM(math.hypot(aa.x-bb.x,aa.y-bb.y)),4),'same_board_side':fp[source].IsFlipped()==fp[ref].IsFlipped()})
report={'status':'PLACEMENT SCREEN ONLY - NO ROUTE LENGTH OR TIMING CHECK','rows':rows,'max_straight_line_mm':max(v['straight_line_pad_distance_mm'] for v in rows),'limits':['Straight-line distance is only a lower bound on required routing length.','No arbitrary pass distance used: topology and IBIS review still required.','Source pad may require BGA escape and layer transitions.','This does not validate package, termination value or operating mode.']}
(ROOT/'review/rgmii-placement.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(rows,indent=2))
