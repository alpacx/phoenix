"""Screen capacitor-to-source links using full-width copper on opposite board faces."""
from pathlib import Path
import hashlib,json
import pcbnew as p
from pcb_power_leg import route_leg
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((r/'layout-npu-output-cap-c444.json').read_text());src=r/base['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
rows=[]
for a,z in [('C1602.1','C1020.1'),('C441.1','C431.1'),('C1616.1','L402.2')]:
    b=p.LoadBoard(str(src));q,x=[b.FindFootprintByReference(ref.split('.')[0]).FindPadByNumber(ref.split('.')[1]) for ref in (a,z)]
    assert q.GetNetCode()==x.GetNetCode()
    route=route_leg(b,q.GetNetname(),tuple(q.GetPosition()),q.GetParentFootprint().GetLayer(),tuple(x.GetPosition()),x.GetParentFootprint().GetLayer(),800000,12.0,shifted=True,allow_supply_bends=True,via_diameter=650000,via_drill=300000)
    source=route.pop('source_map',[])
    if a=='C441.1':
        (r/'logic-output-source-face-anchors.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],source=source),indent=2)+'\n')
    rows.append(dict(pads=[a,z],route=route))
    (r/'core-cross-face-bank-pairs.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],rows=rows),indent=2)+'\n')
    print(a,z,route,flush=True)
