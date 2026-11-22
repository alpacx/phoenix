"""Measure same-layer parallel adjacency for the candidate BGA escape before reserving its lane."""
from pathlib import Path
import hashlib
import json
import subprocess
import pcbnew as p

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
read=lambda n:json.loads((root/(n+".json")).read_text())
base=read("layout-bga-referenced-barrel");cand=read("bga-c27-referenced-barrel")
def checked(d):
    f=root/d["board"];assert hashlib.sha256(f.read_bytes()).hexdigest()==d["sha256"]
    return p.LoadBoard(str(f))
a=checked(base);b=checked(cand)
ids={t.m_Uuid.AsString() for t in a.GetTracks()}
def rec(t):
    return [tuple(t.GetStart()),tuple(t.GetEnd()),t.GetWidth()/1e6,t.GetNetname()]
fresh=[rec(t) for t in b.GetTracks() if t.m_Uuid.AsString() not in ids and not isinstance(t,p.PCB_VIA)]
other=[rec(t) for t in b.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu and t.GetNetname()!="LPDDR4_DQ9_B"]
calc="""
from shapely.geometry import LineString
import sys,json,math
fresh,other=json.load(sys.stdin);hits=[]
for a,z,w,n in fresh:
    length=math.dist(a,z)
    for u,v,ww,nn in other:
        if u==v:continue
        angle=abs((math.atan2(z[1]-a[1],z[0]-a[0])-math.atan2(v[1]-u[1],v[0]-u[0])+math.pi/2)%math.pi-math.pi/2)
        if angle>math.pi/12:continue
        current=LineString([a,z]);adjacent=LineString([u,v])
        gap=current.distance(adjacent)/1e6-(w+ww)/2
        if gap>.6:continue
        proximity=current.intersection(adjacent.buffer((.6+(w+ww)/2)*1e6,cap_style='flat')).length/1e6
        if proximity>0:hits.append(dict(net=nn,edge_gap_mm=gap,run_within_0p6mm=proximity))
print(json.dumps(hits))
"""
rows=json.loads(subprocess.run(["python3","-c",calc],input=json.dumps([fresh,other]),text=True,capture_output=True,check=True).stdout)
out={"board_sha256":cand["sha256"],"runs":sorted(rows,key=lambda row:-row["run_within_0p6mm"]),"assumptions":"Planar centerline distance minus radii, angular difference <=15 degrees. Segment-pair proximity; not a coupled-field solver or flight-delay acceptance."}
(root/"bga-c27-neighboring-runs.json").write_text(json.dumps(out,indent=2)+"\n")
print(out["runs"][:5])
