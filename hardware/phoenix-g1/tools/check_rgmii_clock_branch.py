"""Audit the candidate SoC TX clock branch against the adjacent ground plane and switching nodes."""
from pathlib import Path
import json,math,hashlib
import pcbnew as p
from pcb_power_leg import make
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';c=json.loads((r/'layout-npu-c434-paired-load.json').read_text());src=r/c['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==c['sha256']
b=p.LoadBoard(str(src));doc=json.loads((r/'interface-copper-edge-candidates.json').read_text());assert doc['parent_sha256']==c['sha256'];row,=[q for q in doc['rows'] if q['net']=='ETH_TXCLK' and q['found']];route=row['found']['path_nm'];ref=[z.GetFilledPolysList(p.In1_Cu) for z in b.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(p.In1_Cu)]
other=[o.GetEffectiveShape(p.F_Cu) for o in [*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())] if o.IsOnLayer(p.F_Cu) and o.GetNetname().startswith(('PMIC_SW','CPU_SW','PHY_SW','WIFI_SW'))]
left=[];right=[];mid=[];sw=[];count=0
for a,z in zip(route,route[1:]):
 dx=z[0]-a[0];dy=z[1]-a[1];length=math.hypot(dx,dy);n=max(1,math.ceil(length/25000));t=make(b,a,z,200000,b.FindNet('ETH_TXCLK').GetNetCode(),p.F_Cu)
 if any(t.GetEffectiveShape(p.F_Cu).Collide(sh,1000000) for sh in other):sw.append([a,z])
 for i in range(n+1):
    count+=1
    for off,missing in [(-110000,left),(0,mid),(110000,right)]:
        xy=(round(a[0]+i*dx/n-off*dy/length),round(a[1]+i*dy/n+off*dx/length))
        if not any(poly.Contains(p.VECTOR2I(*xy)) for poly in ref):missing.append(xy)
(r/'rgmii-clock-fixed-branch-reference.json').write_text(json.dumps(dict(parent_sha256=c['sha256'],groups=row['found']['groups'],length_mm=row['found']['length_mm'],sites_per_band=count,missing_samples=dict(left=len(left),middle=len(mid),right=len(right)),first_missing=[v[:3] for v in (left,mid,right)],near_switch_segments=len(sw),measured_timing=False),indent=2)+'\n');print(count,len(left),len(mid),len(right),len(sw))
