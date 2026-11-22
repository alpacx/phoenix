"""Find an uninterrupted 0.2 mm front-layer route from host strobe to the installed pull-down."""
from pathlib import Path
import hashlib,json,subprocess,math
import pcbnew as p
from phy_corridor_path import geometry
tools=Path(__file__).resolve().parent;r=tools.parent/'migration-rk3562/experiments/phy-power-parallel';cp=json.loads((r/'layout-emmc-strobe-pulldown.json').read_text());file=r/cp['board'];assert hashlib.sha256(file.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(file));b.BuildConnectivity();src=b.FindFootprintByReference('U1').FindPadByNumber('L26');dst=b.FindFootprintByReference('R8005').FindPadByNumber('1');code=src.GetNetCode()
goal={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(dst)};targets=[tuple(dst.GetPosition())]
for t in b.GetTracks():
    if t.IsOnLayer(p.F_Cu) and t.m_Uuid.AsString() in goal:targets.extend([tuple(t.GetStart()),tuple(t.GetEnd())])
geo=geometry(b,p.F_Cu,code,oval_caps=True)
for f in b.GetFootprints():
 for q in f.Pads():
    if q.IsOnLayer(p.F_Cu) and q.GetNetCode()!=code and q.GetShape()==p.PAD_SHAPE_CIRCLE:
        bb=q.GetBoundingBox();rect=(bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom())
        if rect in geo[1]:
            geo[1].remove(rect);xy=tuple(q.GetPosition());geo[0].append((xy,xy,q.GetSize().x))
rows=[]
for reverse in (False,True):
    ends=sorted(set(targets));start=[tuple(src.GetPosition())]
    req=dict(geometry=geo,width=200000,sites=ends if reverse else start,target=start if reverse else ends,limit=24000000,frontier=True)
    pr=subprocess.run(['python3',str(tools/'screen_cpu_launch_corridor.py')],input=json.dumps(req),text=True,capture_output=True,check=True)
    rows.append(json.loads(pr.stdout))
from_data=[row.pop('front') for row in rows]
if all(from_data):
    from itertools import product
    near=min((math.dist(a,z),a,z) for a,z in product(*from_data))
else:near=None
(r/'emmc-host-strobe-front.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],fronts=rows,minimum_gap=near),indent=2)+'\n');print(near,[row['front_nodes'] for row in rows])
if near:
    from pcb_power_leg import make
    from pcb_bounds import inflated_box
    t=make(b,near[1],near[2],200000,code,p.F_Cu);bb=inflated_box(t,275000);sh=t.GetEffectiveShape(p.F_Cu)
    obstacles=[]
    for o in [*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())]:
        if o.GetNetCode()!=code and o.IsOnLayer(p.F_Cu) and bb.Intersects(o.GetBoundingBox()) and sh.Collide(o.GetEffectiveShape(p.F_Cu),202000):
            obstacles.append(dict(type=o.GetClass(),net=o.GetNetname(),name=(o.GetParentFootprint().GetReference()+'.'+o.GetNumber()) if isinstance(o,p.PAD) else o.m_Uuid.AsString()))
    report=dict(parent_sha256=cp['sha256'],fronts=rows,minimum_gap=near,obstacles=obstacles)
    (r/'emmc-host-strobe-front.json').write_text(json.dumps(report,indent=2)+'\n')
    print(obstacles)
