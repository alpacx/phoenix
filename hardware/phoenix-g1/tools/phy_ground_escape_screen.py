#!/usr/bin/env python3
"""Conservative clearance screen for C2007 ground return; DRC still mandatory."""
import pcbnew as p,json,math,os,sys
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
m=json.loads((D/'runs/input-ground-local-001/input.json').read_text());b=p.LoadBoard(m['source']);removed=set(m['removed']);clock=len(sys.argv)>1 and sys.argv[1]=='clock'
if clock:
 for t in b.GetTracks():
  if t.GetNetname()=='GND' and ((isinstance(t,p.PCB_VIA) and abs(p.ToMM(t.GetPosition().x)-54.5)<.001 and abs(p.ToMM(t.GetPosition().y)-26.45)<.001) or (not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu and all(abs(p.ToMM(v)-54.5)<.001 for v in [t.GetStart().x,t.GetEnd().x]) and min(p.ToMM(t.GetStart().y),p.ToMM(t.GetEnd().y))>=25.35 and max(p.ToMM(t.GetStart().y),p.ToMM(t.GetEnd().y))<=26.45)):removed.add(t.m_Uuid.AsString())
xy=lambda v:tuple(p.ToMM(x) for x in v)
def dist(a,c,d):
 vx,vy=d[0]-c[0],d[1]-c[1];l=vx*vx+vy*vy;t=max(0,min(1,((a[0]-c[0])*vx+(a[1]-c[1])*vy)/l)) if l else 0
 return math.hypot(a[0]-c[0]-t*vx,a[1]-c[1]-t*vy)
def boxdist(a,bb):return math.hypot(max(bb[0]-a[0],0,a[0]-bb[2]),max(bb[1]-a[1],0,a[1]-bb[3]))
tracks=[];pads=[]
for t in b.GetTracks():
 if t.m_Uuid.AsString() not in removed:tracks.append((xy(t.GetStart()),xy(t.GetEnd()),p.ToMM(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth())/2,t.GetNetname(),t.IsOnLayer(p.F_Cu),isinstance(t,p.PCB_VIA)))
for f in b.GetFootprints():
 for q in f.Pads():
  z=q.GetBoundingBox();pads.append(([p.ToMM(v) for v in (z.GetX(),z.GetY(),z.GetRight(),z.GetBottom())],q.GetNetname(),q.IsOnLayer(p.F_Cu),f.GetReference()))
start=(54.52,25.35) if clock else (52.48,28);candidates=[]
for ix in range(530,571) if clock else range(510,551):
 for iy in range(235,267) if clock else range(265,301):
  end=(ix/10,iy/10)
  if any(dist(end,a,z)<rad+.225+.2 for a,z,rad,n,front,via in tracks if n!='GND'):continue
  if any(boxdist(end,bb)<.225+.05 for bb,n,front,ref in pads):continue
  if any(boxdist(end,bb)<.225+.2 for bb,n,front,ref in pads if n!='GND'):continue
  if any(math.dist(end,a)<.45 for a,z,rad,n,front,via in tracks if via):continue
  # sample at 0.025mm and add sampling allowance
  steps=max(1,math.ceil(math.dist(start,end)/.025));points=[(start[0]+(end[0]-start[0])*i/steps,start[1]+(end[1]-start[1])*i/steps) for i in range(steps+1)]
  if any(dist(q,a,z)<rad+.1+.2125 for a,z,rad,n,front,via in tracks if n!='GND' and front for q in points):continue
  if any(boxdist(q,bb)<.3125 for bb,n,front,ref in pads if n!='GND' and front for q in points):continue
  candidates.append({'xy':end,'length':math.dist(start,end)})
candidates.sort(key=lambda r:r['length']);(D/('clock-ground-escape-screen.json' if clock else 'ground-escape-screen.json')).write_text(json.dumps({'source_sha256':m['source_sha256'],'candidates':candidates,'method':'conservative pad bounding boxes and sampled segment clearance; zones/DRC not certified'},indent=2)+'\n');print(json.dumps(candidates[:12]),flush=True);os._exit(0)
