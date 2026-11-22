"""Localize missing centerline GND beneath real LPDDR copper relative to drilled clearances."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import os
import sys
import pcbnew as p
from pcb_bounds import inflated_box

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
after_display='--after-display' in sys.argv
recheck='--after-dq0' in sys.argv or after_display
cp=json.loads((root/('layout-lcd-select-trunk.json' if after_display else 'layout-lpddr-dq0-reference.json' if recheck else 'layout-lpddr-clock-return.json')).read_text());src=root/cp['board']
ab4=next((k for k in ('before-ab4','after-ab4','after-bank','after-cap-return') if '--'+k in sys.argv),None)
if ab4:
    cp=json.loads((root/('layout-ground-land-offsets.json' if ab4=='before-ab4' else 'memory-bank-cap-and-return.json' if ab4=='after-cap-return' else 'memory-ab4-bank-bent.json' if ab4=='after-bank' else 'memory-ab4-bypass-placement.json')).read_text())
    if ab4 in ('after-ab4','after-bank','after-cap-return'):cp=cp['candidate']
    src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));layers={p.F_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu}
zones={l:[z for z in b.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(l)] for l in layers.values()}
allholes=[t for t in b.GetTracks() if isinstance(t,p.PCB_VIA)]+[q for f in b.GetFootprints() for q in f.Pads() if q.GetDrillSize().x]
totals=Counter();events=[]
for t in b.GetTracks():
    if isinstance(t,p.PCB_VIA) or not t.GetNetname().startswith('LPDDR4_') or t.GetLayer() not in layers:continue
    l=layers[t.GetLayer()];a,z=t.GetStart(),t.GetEnd();n=max(1,math.ceil(t.GetLength()/25000))
    nearby=[h for h in allholes if h.IsOnLayer(l) and h.GetNetname()!='GND' and inflated_box(t,750000).Contains(h.GetPosition())]
    prior=None;slices=[]
    for i in range(n):
        at=p.VECTOR2I(round(a.x+(z.x-a.x)*(i+.5)/n),round(a.y+(z.y-a.y)*(i+.5)/n))
        if any(zone.GetFilledPolysList(l).Contains(at) for zone in zones[l]):label='over_ground';nets=[]
        else:
            local=[]
            for o in nearby:
                # Use this width only for geometric attribution: actual copper presence is
                # sampled above from KiCad's filled polygon with all project rules applied.
                if o.GetEffectiveShape(l).Collide(at,202000):local.append((o.GetNetname(),o.m_Uuid.AsString()))
            nets=sorted(set(local))
            if any(k==t.GetNetname() for k,_ in nets):label='within_own_via_clearance'
            elif nets:label='within_other_net_clearance'
            else:label='outside_modeled_annuli'
        totals[label]+=t.GetLength()/n/1e6
        key=(label,tuple(nets))
        if prior!=key:slices.append(dict(kind=label,neighbors=nets,first_nm=tuple(at),last_nm=tuple(at),mm=0));prior=key
        slices[-1]['last_nm']=tuple(at);slices[-1]['mm']+=t.GetLength()/n/1e6
    not_own=sum(r['mm'] for r in slices if r['kind'] in ('within_other_net_clearance','outside_modeled_annuli'))
    if not_own:events.append(dict(uuid=t.m_Uuid.AsString(),net=t.GetNetname(),layer=t.GetLayerName(),width_mm=t.GetWidth()/1e6,length_mm=t.GetLength()/1e6,not_own_mm=not_own,slices=slices))
events.sort(key=lambda e:-e['not_own_mm'])
(root/(('lpddr-return-'+ab4+'.json') if ab4 else 'lpddr-return-after-display.json' if after_display else 'lpddr-return-void-map-recovered.json' if recheck else 'lpddr-return-void-map.json')).write_text(json.dumps(dict(source_sha256=cp['sha256'],sample_pitch_mm=.025,estimated_length_mm=totals,foreign_or_unattributed=events),indent=2)+'\n')
print(totals,[(r['net'],round(r['not_own_mm'],3)) for r in events[:12]],flush=True);os._exit(0)
