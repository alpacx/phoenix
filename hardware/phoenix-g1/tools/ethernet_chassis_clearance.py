"""Check short J2 chassis bonds against projected circuit copper and existing plane fills."""
import hashlib
import json
import os
from pathlib import Path
import pcbnew as p
from pcb_bounds import inflated_box

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-coincident-cleanup.json').read_text());source=root/meta['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==meta['sha256']
b=p.LoadBoard(str(source));jack=b.FindFootprintByReference('J2')
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
objects=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
candidates=[]
for first,last in [('P10','SHIELD0'),('SHIELD0','SHIELD1')]:
    a,z=[jack.FindPadByNumber(n) for n in (first,last)]
    assert a.GetNetname()==z.GetNetname()=='CHASSIS'
    t=p.PCB_TRACK(b);t.SetNetCode(a.GetNetCode());t.SetLayer(p.B_Cu);t.SetWidth(1000000);t.SetStart(a.GetPosition());t.SetEnd(z.GetPosition())
    sh=t.GetEffectiveShape(p.B_Cu);bounds=inflated_box(t,2100000)
    nearby={};overlap=[]
    for l in layers:
        close=[o for o in objects if o.GetNetCode()!=a.GetNetCode() and o.IsOnLayer(l) and bounds.Intersects(o.GetBoundingBox()) and sh.Collide(o.GetEffectiveShape(l),2000000)]
        nearby[b.GetLayerName(l)]=sorted({o.GetNetname() or 'unassigned pin / mounting hole' for o in close})
        for zone in b.Zones():
            if not zone.IsOnLayer(l) or zone.GetIsRuleArea():continue
            if zone.GetNetCode()!=a.GetNetCode() and zone.HasFilledPolysForLayer(l) and zone.GetFilledPolysList(l).Collide(sh,0):
                overlap.append([b.GetLayerName(l),zone.GetNetname()])
    candidates.append(dict(terminals=[first,last],width_mm=1,length_mm=t.GetLength()/1e6,projected_copper_within_2mm=nearby,overlapping_filled_zones=overlap))
report=dict(board_sha256=meta['sha256'],sources=['reference/HR911130A.pdf page 1, P10 / 1000 pF 2 kV / four 75 ohm terminations','native KiCad loaded filled zones'],candidates=candidates,geometry_acceptance='2 mm is an exploratory lateral keepout, not a board insulation rating.',adopted=False)
(root/'ethernet-chassis-clearance.json').write_text(json.dumps(report,indent=2)+'\n')
print([(v['terminals'],v['overlapping_filled_zones']) for v in candidates],flush=True)
os._exit(0)
