"""Retain the reachable full-size via sites from the NPU output-capacitor node."""
from pathlib import Path
import hashlib,json,sys
import pcbnew as p
from pcb_power_leg import route_leg
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
gpu='--gpu' in sys.argv
base=json.loads((r/('layout-npu-c434-paired-load.json' if gpu else 'layout-logic-c431-paired-load.json')).read_text());src=r/base['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src))
q=b.FindFootprintByReference('L402' if gpu else 'C444').FindPadByNumber('2' if gpu else '1');z=b.FindFootprintByReference('R422' if gpu else 'L404').FindPadByNumber('1' if gpu else '2')
if gpu:
    # Project from the nearby load side, with a six-millimetre eastward scan toward the power bank.
    goal=(q.GetPosition().x+6000000,q.GetPosition().y)
else:goal=tuple(z.GetPosition())
result=route_leg(b,q.GetNetname(),tuple(q.GetPosition()),p.F_Cu,goal,p.B_Cu,800000,12.0,shifted=True,allow_supply_bends=True,via_diameter=650000,via_drill=300000,collect_supply_sites=True)
(r/('gpu-output-source-face-anchors.json' if gpu else 'npu-output-source-face-anchors.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],legal=result['legal_sites'],source=result['source_map']),indent=2)+'\n')
print(result['legal_sites'],len(result['source_map']))
