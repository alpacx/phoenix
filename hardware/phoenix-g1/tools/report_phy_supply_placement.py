#!/usr/bin/env python3
"""Measure PHY bypass proximity, not electrical adequacy or routed loop length."""
import hashlib,json,math
from pathlib import Path
import pcbnew as p
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text());src=D/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
fs={f.GetReference():f for f in b.GetFootprints()}
def xy(q):return [p.ToMM(q.GetPosition().x),p.ToMM(q.GetPosition().y)]
rows=[]
assignments={'C512':'3','C513':'8','C514':'21','C522':'38','C516':'11','C517':'28','C518':'40','C519':'29'}
for n in list(range(511,520))+[522]:
 ref=f'C{n}';q=next(q for q in fs[ref].Pads() if q.GetNumber()=='1')
 targets=[v for v in fs['U5'].Pads() if v.GetNetname()==q.GetNetname()]
 assert targets,(ref,q.GetNetname())
 v=min(targets,key=lambda v:math.dist(xy(q),xy(v)))
 ids={v.m_Uuid.AsString() for v in b.GetConnectivity().GetConnectedItems(q)}
 assigned=next((v for v in targets if v.GetNumber()==assignments.get(ref)),None)
 assignment=None if assigned is None else dict(pin=assigned.GetNumber(),
  straight_line_mm=round(math.dist(xy(q),xy(assigned)),4),
  connected=assigned.m_Uuid.AsString() in ids,
  status='PROJECT_LAYOUT_ASSIGNMENT_NOT_ELECTRICAL_QUALIFICATION')
 rows.append(dict(candidate_assignment=assignment,reference=ref,net=q.GetNetname(),position_mm=xy(q),
  closest_phy_pin=v.GetNumber(),straight_line_mm=round(math.dist(xy(q),xy(v)),4),
  connected_to_closest_phy_pin=v.m_Uuid.AsString() in ids))
out=dict(status='PLACEMENT_REVIEW_REQUIRED',sha256=cp['sha256'],capacitors=rows,
 limitations=['Straight-line distances are lower bounds, not routed supply/return loops.',
 'Ground continuity does not validate decoupling effectiveness.',
 'Review all capacitor assignments and placement with PHY reference layout before routing rails.',
 'No electrical simulation, current qualification or physical testing.'],assembly_ready=False)
(D/'pcb/phy-supply-placement.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
