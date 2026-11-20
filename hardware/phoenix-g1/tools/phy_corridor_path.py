"""Grid search with full-width copper at endpoints and on every edge."""
import heapq
import math
import pcbnew as p

def geometry(board, layer, net, oval_caps=False):
    obstacles=[]
    for t in board.GetTracks():
        if t.GetNetCode()==net or not t.IsOnLayer(layer):continue
        diameter=t.GetWidth(layer) if isinstance(t,p.PCB_VIA) else t.GetWidth()
        obstacles.append([tuple(t.GetStart()),tuple(t.GetEnd()),diameter])
    pads=[]
    for f in board.GetFootprints():
        for q in f.Pads():
            if q.GetNetCode()==net or not q.IsOnLayer(layer):continue
            box=q.GetBoundingBox()
            if oval_caps and q.GetShape()==p.PAD_SHAPE_OVAL and q.GetOrientationDegrees()%90==0:
                x,y=q.GetPosition()
                w,h=box.GetWidth(),box.GetHeight()
                dx=max(0,(w-h)//2);dy=max(0,(h-w)//2)
                obstacles.append([(x-dx,y-dy),(x+dx,y+dy),min(w,h)])
            else:
                pads.append((box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom()))
    return obstacles,pads

def route(board, layer, net, start, end):
    import subprocess,json
    from pathlib import Path
    a,z=[tuple(p.FromMM(x) for x in pos) for pos in (start,end)]
    run=subprocess.run(["/usr/bin/env","python3",str(Path(__file__).with_name("phy_corridor_grid.py"))],input=json.dumps([a,z,*geometry(board,layer,net)]),text=True,capture_output=True,check=True)
    return json.loads(run.stdout)
