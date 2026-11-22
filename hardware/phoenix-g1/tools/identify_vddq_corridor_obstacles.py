"""Measure native copper, drill and keepout blockers for the closest disconnected VDDQ frontiers."""
import hashlib
import json
import sys
from pathlib import Path
import pcbnew as p
from pcb_power_leg import make
from pcb_bounds import inflated_box

stage=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((stage/n).read_text())
emmc='--emmc-1v8' in sys.argv
cp=read('layout-memory-n12-neighbors.json' if emmc else 'layout-lpddr-vdd1-source.json');gaps=read('emmc-1v8-corridor-gaps.json' if emmc else 'vddq-corridor-gaps.json')
src=stage/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']==gaps['parent_sha256']
b=p.LoadBoard(str(src));code=b.FindNet('+1V8_SYS' if emmc else '+1V1_LPDDR4').GetNetCode()
objs=[*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())]
zones=[z for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
trials=[]
for row in gaps['rows']:
    layer=b.GetLayerID(row['layer'])
    for pair in row['representatives']:
        t=make(b,pair['source_nm'],pair['load_nm'],600000,code,layer)
        bb=inflated_box(t,400000);sh=t.GetEffectiveShape(layer)
        hits=[]
        for o in objs:
            if o.GetNetCode()==code or not bb.Intersects(o.GetBoundingBox()):continue
            collision=o.IsOnLayer(layer) and sh.Collide(o.GetEffectiveShape(layer),202000)
            drilled=isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x
            if not (collision or drilled and sh.Collide(o.GetEffectiveHoleShape(),252000)):continue
            hits.append(dict(net=o.GetNetname(),type=o.GetClass(),id=o.m_Uuid.AsString(),
                             pad=o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else None))
        trials.append(dict(layer=row['layer'],**pair,hits=hits,rule_areas=[z.GetZoneName() for z in zones if z.IsOnLayer(layer) and sh.Collide(z.Outline(),0)]))
trials.sort(key=lambda x:(len(x['hits'])+len(x['rule_areas']),x['gap_mm']))
(stage/('emmc-1v8-corridor-obstacles.json' if emmc else 'vddq-corridor-obstacles.json')).write_text(json.dumps(dict(parent_sha256=cp['sha256'],trials=trials,assembly_ready=False),indent=2)+'\n')
print([(x['layer'],x['gap_mm'],[(i['net'],i['type']) for i in x['hits']]) for x in trials[:5]])
