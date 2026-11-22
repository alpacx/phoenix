"""Compare the filled planes underneath unchanged high-speed traces near new through barrels."""
from pathlib import Path
import hashlib
import json
import math
import sys

import pcbnew as p
from pcb_bounds import inflated_box

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
net_prefixes=('LPDDR4_','USB_','MUX_','SOC_USB_','ADDON_USB_','EMMC_','SOC_EMMC_','ETH_','PHY_','WIFI_')
references={p.F_Cu:p.In1_Cu,p.In2_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu,p.B_Cu:p.In4_Cu}
def load(name):
    data=json.loads((root/(name+'.json')).read_text());entry=data.get('candidate',data)
    path=root/entry['board'];assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
    return p.LoadBoard(str(path)),entry['sha256']
def zones(board,l):
    ground=p.SHAPE_POLY_SET()
    for z in board.Zones():
        if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(l):
            ground.BooleanAdd(z.GetFilledPolysList(l))
    return ground
radio='--radio-wake' in sys.argv
shielded='--ca0-shielded' in sys.argv
ca0='--ca0-group' in sys.argv or shielded
ca1='--ca1' in sys.argv
emmc_data='--emmc-data' in sys.argv
n12='--n12' in sys.argv
zq='--zq' in sys.argv
vdd1_trunk='--vdd1-trunk' in sys.argv
vdd1_return='--vdd1-return' in sys.argv
moved='--cap-return' in sys.argv or vdd1_return
inner='--inner' in sys.argv
base,base_sha=load('layout-command-ca1' if ca0 else 'layout-emmc-data-power' if ca1 else 'layout-memory-n12-neighbors' if emmc_data else 'layout-memory-zq-supply' if n12 else 'layout-memory-trunk-widths' if zq else 'layout-lpddr-vdd1-bank' if vdd1_return or vdd1_trunk else 'layout-gpu-cap-bank' if radio else 'layout-memory-bank-rear-taps' if moved else 'layout-memory-ab4-bypass' if inner else 'layout-ground-land-offsets')
after,sha=load('ddr-ca-group-shielded' if shielded else 'ddr-ca-group-corridor' if ca0 else 'ddr-command-ca1-returns' if ca1 else 'emmc-d0-data-pullup' if emmc_data else 'vddq-n12-source' if n12 else 'layout-memory-zq-supply' if zq else 'vdd1-external-pair-trunk' if vdd1_trunk else 'vdd1-c2303-return' if vdd1_return else 'layout-radio-host-wake' if radio else 'memory-bank-cap-and-return' if moved else 'memory-ab4-bank-bent' if inner else 'layout-memory-ab4-bypass')
old={t.m_Uuid.AsString() for t in base.GetTracks()}
new=[t for t in after.GetTracks() if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() not in old]
if emmc_data:
    prev={t.m_Uuid.AsString():tuple(t.GetPosition()) for t in base.GetTracks() if isinstance(t,p.PCB_VIA)}
    new.extend(t for t in after.GetTracks() if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in prev and tuple(t.GetPosition())!=prev[t.m_Uuid.AsString()])
if vdd1_trunk:
    previous={t.m_Uuid.AsString():t.GetDrillValue() for t in base.GetTracks() if isinstance(t,p.PCB_VIA)}
    new.extend(t for t in after.GetTracks() if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in previous and t.GetDrillValue()!=previous[t.m_Uuid.AsString()])
if moved:
    old_vias={t.m_Uuid.AsString():t for t in base.GetTracks() if isinstance(t,p.PCB_VIA)}
    new=[t for t in after.GetTracks() if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in old_vias and tuple(t.GetPosition())!=tuple(old_vias[t.m_Uuid.AsString()].GetPosition())]
    assert len(new)==1 and new[0].GetNetname()=='GND'
planes={l:(zones(base,l),zones(after,l)) for l in (p.In1_Cu,p.In4_Cu)}
records=[]
for t in after.GetTracks():
    if t.m_Uuid.AsString() not in old or isinstance(t,p.PCB_VIA) or not t.GetNetname().startswith(net_prefixes):continue
    lay=t.GetLayer()
    if lay not in references or not any(inflated_box(t,1500000).Contains(v.GetPosition()) for v in new):continue
    rows=[]
    for lateral in (0,100000,200000):
        areas=[]
        for plane in planes[references[lay]]:
            poly=p.SHAPE_POLY_SET();t.TransformShapeToPolygon(poly,lay,lateral,500,p.ERROR_OUTSIDE)
            poly.BooleanSubtract(plane);areas.append(poly.Area()/1e12)
        rows.append(dict(lateral_mm=lateral/1e6,before_mm2=areas[0],after_mm2=areas[1],increase_mm2=areas[1]-areas[0]))
    records.append(dict(uuid=t.m_Uuid.AsString(),net=t.GetNetname(),layer=t.GetLayerName(),projection=rows))
out=dict(base_sha256=base_sha,sha256=sha,new_barrels=len(new),records=records,
         scope='Local adjacent-GND plane shadow near newly drilled holes; electrical coupling, unused ball escape and impedance require separate qualification.')
if moved:
    def grounded_vias(board):
        board.BuildConnectivity()
        connected={q.m_Uuid.AsString() for q in board.GetConnectivity().GetConnectedItems(board.FindFootprintByReference('U4').FindPadByNumber('69'))}
        return [t for t in board.GetTracks() if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in connected and t.GetViaType()==p.VIATYPE_THROUGH]
    origin=tuple(new[0].GetPosition())
    supplies=(grounded_vias(base),grounded_vias(after))
    neighbours=[]
    for t in after.GetTracks():
        if not isinstance(t,p.PCB_VIA) or not t.GetNetname().startswith(net_prefixes) or math.dist(origin,tuple(t.GetPosition()))>3000000:continue
        distances=[min(math.dist(tuple(t.GetPosition()),tuple(g.GetPosition())) for g in cluster)/1e6 for cluster in supplies]
        neighbours.append(dict(net=t.GetNetname(),via=t.m_Uuid.AsString(),nearest_before_mm=distances[0],nearest_after_mm=distances[1]))
    out['nearby_signal_vias']=neighbours
(root/('ddr-ca0-shielded-impact.json' if shielded else 'ddr-ca0-plane-impact.json' if ca0 else 'ddr-ca1-plane-impact.json' if ca1 else 'emmc-data-plane-impact.json' if emmc_data else 'memory-n12-plane-impact.json' if n12 else 'memory-zq-plane-impact.json' if zq else 'vdd1-source-barrel-projections.json' if vdd1_trunk else 'vdd1-c2303-return-projection.json' if vdd1_return else 'radio-wake-barrel-projections.json' if radio else 'memory-bank-cap-return-projection.json' if moved else 'memory-bank-inner-reference-comparison.json' if inner else 'memory-ab4-reference-comparison.json')).write_text(json.dumps(out,indent=2)+'\n')
print(len(new),len(records),[(r['net'],max(k['increase_mm2'] for k in r['projection'])) for r in records if max(k['increase_mm2'] for k in r['projection'])>1e-6],flush=True)
