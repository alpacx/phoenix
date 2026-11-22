"""Record the actual PCB routing and sampled local GND reference for SI screening."""
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import pcbnew as p

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
checkpoint=json.loads((root/'layout-pmic-pwron-filter.json').read_text());source=root/checkpoint['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==checkpoint['sha256']
board=p.LoadBoard(str(source))
usb=re.compile(r'^(USB_D[PM]|(?:USB|SOC_USB|MUX)_(?:RX|TX)[12]?_[PN]|ADDON_USB_D[PM])$')
mdi=re.compile(r'^ETH_MDI[0-3]_[PN]$')
def category(net):
    if mdi.fullmatch(net):return 'ethernet_mdi'
    if usb.fullmatch(net):return 'usb_data'
    if not net.startswith('LPDDR4_'):return None
    if net.endswith(('RESETN','240R')):return 'lpddr4_aux'
    if re.match(r'^LPDDR4_(DQS|CLK)',net):return 'lpddr4_differential'
    return 'lpddr4_single_ended'
layers={p.F_Cu:p.In1_Cu,p.B_Cu:p.In4_Cu,p.In2_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu}
polys={l:[z.GetFilledPolysList(l) for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname()=='GND' and z.HasFilledPolysForLayer(l)] for l in layers.values()}
groups=defaultdict(lambda:dict(count=0,length_mm=0,reference_sample_points=0,points_over_ground=0,nets=set()))
for t in board.GetTracks():
    signal=category(t.GetNetname())
    if not signal or isinstance(t,p.PCB_VIA):continue
    l=t.GetLayer();reference=layers[l];key=(signal,board.GetLayerName(l),t.GetWidth())
    row=groups[key];row['count']+=1;row['length_mm']+=t.GetLength()/1e6;row['nets'].add(t.GetNetname())
    a,z=t.GetStart(),t.GetEnd();slices=max(1,math.ceil(t.GetLength()/50000))
    for i in range(slices):
        at=p.VECTOR2I(round(a.x+(z.x-a.x)*(i+.5)/slices),round(a.y+(z.y-a.y)*(i+.5)/slices))
        row['reference_sample_points']+=1
        if any(poly.Contains(at) for poly in polys[reference]):row['points_over_ground']+=1
rows=[]
for (family,layer,width),r in sorted(groups.items()):
    r.update(family=family,layer=layer,width_mm=width/1e6,reference_layer=board.GetLayerName(layers[board.GetLayerID(layer)]))
    r['nets']=sorted(r['nets']);rows.append(r)
multi={}
for n,parts in checkpoint['open_nets'].items():
    family=category(n)
    if family:multi[n]=len(parts)
r=dict(source_sha256=checkpoint['sha256'],track_rows=rows,unconnected_by_net=multi,
       usb_data_segments=sum(v['count'] for v in rows if v['family']=='usb_data'),
       ethernet_mdi_segments=sum(v['count'] for v in rows if v['family']=='ethernet_mdi'),
       sampling='Midpoint of subdivisions up to 0.05 mm along each existing trace. Ground under centerline only; no inference on continuous RF return or target impedance.')
(root/'highspeed-copper-inventory.json').write_text(json.dumps(r,indent=2)+'\n')
print([(v['family'],v['layer'],v['width_mm'],round(v['length_mm'],2),v['points_over_ground'],v['reference_sample_points']) for v in rows],flush=True);os._exit(0)
