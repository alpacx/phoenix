"""Sweep RF control vertices between fixed lands against a finite image-plane corridor."""
import hashlib
import heapq
import itertools
import json
import math
from pathlib import Path

import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make

root = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments/phy-power-parallel"
entry = json.loads((root / "rf-external-usb-direction.json").read_text())
path = root / entry["board"]
assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
board = p.LoadBoard(str(path))
ground = p.SHAPE_POLY_SET()
for z in board.Zones():
    if z.GetNetname() == "GND" and z.HasFilledPolysForLayer(p.In4_Cu):
        ground.BooleanAdd(z.GetFilledPolysList(p.In4_Cu))
roi = p.SHAPE_POLY_SET()
roi.NewOutline()
for xy in ((65000000,14000000),(76000000,14000000),(76000000,22000000),(65000000,22000000)):
    roi.Append(*xy)
ground.BooleanIntersection(roi)
objects = list(board.GetTracks()) + [q for f in board.GetFootprints() for q in f.Pads()]
sources = [("WIFI_ANT", (71200000,17600000), (74000000,20200000)),
           ("WIFI_RF", (67467500,16400000), (70707188,16324688))]
out = {}
for name, start, end in sources:
    width = 338000 if name == "WIFI_ANT" else 335000
    obstacles = []
    for o in objects:
        if not inflated_box(o,400000).Intersects(roi.BBox()):
            continue
        if o.IsOnLayer(p.B_Cu) and o.GetNetname() != name:
            obstacles.append((o.GetEffectiveShape(p.B_Cu),202000))
        if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x:
            obstacles.append((o.GetEffectiveHoleShape(),252000))
    wire = make(board,start,end,width,board.GetNetcodeFromNetname(name),p.B_Cu)
    corridors = p.SHAPE_POLY_SET(ground)
    corridors.Deflate(width//2 + 201000, p.CORNER_STRATEGY_ROUND_ALL_CORNERS, 500)
    def clear(a,b):
        if a == b: return corridors.Contains(p.VECTOR2I(*a))
        wire.SetStart(p.VECTOR2I(*a));wire.SetEnd(p.VECTOR2I(*b))
        sh = wire.GetEffectiveShape(p.B_Cu)
        if any(sh.Collide(other,c) for other,c in obstacles):
            return False
        n = max(1,math.ceil(math.dist(a,b)/20000))
        return all(corridors.Contains(p.VECTOR2I(*(round(i+(j-i)*k/n) for i,j in zip(a,b)))) for k in range(n+1))
    grid = [(x*100000,y*100000) for x in range(min(start[0],end[0])//100000-5,max(start[0],end[0])//100000+6)
                                  for y in range(min(start[1],end[1])//100000-12,max(start[1],end[1])//100000+13)]
    left = [pt for pt in grid if clear(start,pt)]
    right = [pt for pt in grid if clear(pt,end)]
    paths = sorted(((math.dist(start,a)+math.dist(a,b)+math.dist(b,end),a,b) for a,b in itertools.product(left,right)),key=lambda x:x[0])
    best = next(([start,a,b,end] for _,a,b in paths if clear(a,b)),None)
    if not best and left and right:
        gridset = set(grid)
        rightset = set(right)
        distances = {a: math.dist(start,a) for a in left}
        parents = {a:start for a in left}
        frontier = [(cost+math.dist(a,end),cost,a) for a,cost in distances.items()]
        heapq.heapify(frontier)
        tested = {}
        while frontier:
            _,cost,a = heapq.heappop(frontier)
            if cost != distances[a]:
                continue
            if a in rightset:
                rev = [end, a]
                while rev[-1] != start:
                    rev.append(parents[rev[-1]])
                long_path = list(reversed(rev))
                best = [long_path[0]]
                while best[-1] != end:
                    best.append(next(pt for pt in reversed(long_path[long_path.index(best[-1])+1:]) if clear(best[-1],pt)))
                break
            for dx,dy in itertools.product((-100000,0,100000),repeat=2):
                n = (a[0]+dx,a[1]+dy)
                alt = cost + math.hypot(dx,dy)
                if n not in gridset or alt >= distances.get(n,math.inf):
                    continue
                key = tuple(sorted((a,n)))
                if key not in tested:
                    tested[key] = clear(a,n)
                if tested[key]:
                    parents[n] = a
                    distances[n] = alt
                    heapq.heappush(frontier,(alt+math.dist(n,end),alt,n))
    out[name] = dict(start_nm=start,end_nm=end,start_reachable=len(left),end_reachable=len(right),
                     grid_mm=.1,path_nm=best)
    print(name,len(left),len(right),best,flush=True)
(root/"rf-external-plane-detours.json").write_text(json.dumps(dict(source_sha256=entry["sha256"],sample_step_mm=.02,clearance_margin_mm=.2,paths=out),indent=2)+"\n")
