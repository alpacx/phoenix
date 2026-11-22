"""Compare filled-plane coverage, return vias and broadside signal exposure for CA coupons."""
import hashlib
import json
import math
import sys
from pathlib import Path
import pcbnew as p

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
stage=sys.argv[1];spec=json.loads((root/(stage+".json")).read_text());src=root/spec["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest()==spec["sha256"]
b=p.LoadBoard(str(src));b.BuildConnectivity()
ground={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference("U4").FindPadByNumber("69"))}
vias=[t for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in ground]
gnd=next(z.GetFilledPolysList(p.In4_Cu) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(p.In4_Cu))
nearby=[t for t in b.GetTracks() if isinstance(t,p.PCB_TRACK) and not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.In2_Cu]
rows=[]
def angular_separation(t,u):
    def angle(track):
        d=track.GetEnd()-track.GetStart()
        return math.atan2(d.y,d.x)
    return abs((angle(t)-angle(u)+math.pi/2)%math.pi-math.pi/2)
routes=spec.get("routes")
if routes is None and stage=="ddr-command-ca1-returns":
    predecessor=json.loads((root/"ddr-command-in3-cu-compact-broadside.json").read_text())
    assert predecessor["sha256"]==spec["parent_sha256"]
    routes=predecessor["routes"]
for route in routes:
    net=route["net"];segments=[t for t in b.GetTracks() if t.GetNetname()==net and t.GetLayer()==p.In3_Cu and not isinstance(t,p.PCB_VIA)]
    covered=total=0;exposed={};max_run=0
    cells=0
    for t in segments:
        a=tuple(t.GetStart());z=tuple(t.GetEnd());length=t.GetLength();n=max(1,math.ceil(length/20000))
        near=[u for u in nearby if angular_separation(t,u)<math.pi/12]
        runs={}
        for i in range(n):
            x,y=(round(s+(e-s)*(i+.5)/n) for s,e in zip(a,z));pt=p.VECTOR2I(x,y);step=length/n
            covered+=step*gnd.Contains(pt);total+=step;cells+=1
            hits={u.GetNetname() for u in near if u.GetEffectiveShape(p.In2_Cu).Collide(pt,200000)}
            runs={name:runs.get(name,0)+step for name in hits}
            for name,run in runs.items():
                exposed[name]=exposed.get(name,0)+step
                max_run=max(max_run,run)
    ret=[]
    for v in [t for t in b.GetTracks() if t.GetNetname()==net and isinstance(t,p.PCB_VIA)]:
        nearest=min(vias,key=lambda k:math.dist(tuple(v.GetPosition()),tuple(k.GetPosition())))
        ret.append({"position_nm":tuple(v.GetPosition()),"nearest_common_gnd_mm":round(math.dist(tuple(v.GetPosition()),tuple(nearest.GetPosition()))/1e6,4)})
    rows.append({"net":net,"samples":cells,"centerline_plane_coverage_fraction":round(covered/total,5),"via_returns":ret,"projected_near_parallel_mm":{k:round(v/1e6,3) for k,v in exposed.items()},"longest_segment_local_run_mm":round(max_run/1e6,3)})
out={"sha256":spec["sha256"],"rows":rows,"scope":"Sampling every 20 µm. Opposite signal layer In2 is separated by the stack's thin central dielectric. Within 0.20 mm of projected copper at up to 15 degrees; incidence is a geometric proxy, not a crosstalk or timing model. Plane antipads included."}
(root/(stage+"-reference.json")).write_text(json.dumps(out,indent=2)+"\n")
print(rows)
