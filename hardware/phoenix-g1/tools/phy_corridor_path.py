"""Grid search with full-width copper at endpoints and on every edge."""
import heapq
import math
import pcbnew as p

def geometry(board, layer, net, oval_caps=False, df40_pitch=False):
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
            # The caller inflates all shapes by 0.202 mm. The existing DF40
            # clearance is 0.170 mm; keep the same 2 µm guard here.
            df40_inset=30000 if df40_pitch and f.GetReference()=='J3' else 0
            if oval_caps and q.GetShape()==p.PAD_SHAPE_OVAL and q.GetOrientationDegrees()%90==0:
                x,y=q.GetPosition()
                w,h=box.GetWidth(),box.GetHeight()
                dx=max(0,(w-h)//2);dy=max(0,(h-w)//2)
                obstacles.append([(x-dx,y-dy),(x+dx,y+dy),min(w,h)-2*df40_inset])
            else:
                pads.append((box.GetLeft()+df40_inset,box.GetTop()+df40_inset,box.GetRight()-df40_inset,box.GetBottom()-df40_inset))
    return obstacles,pads

def route(board, layer, net, start, end):
    import subprocess,json
    from pathlib import Path
    a,z=[tuple(p.FromMM(x) for x in pos) for pos in (start,end)]
    run=subprocess.run(["/usr/bin/env","python3",str(Path(__file__).with_name("phy_corridor_grid.py"))],input=json.dumps([a,z,*geometry(board,layer,net)]),text=True,capture_output=True,check=True)
    return json.loads(run.stdout)
