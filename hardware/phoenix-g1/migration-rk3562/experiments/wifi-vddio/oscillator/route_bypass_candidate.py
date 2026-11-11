# Experimental local bypass; not in main rebuild.
import pcbnew as p,sys,math,json,hashlib,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from local_pcb_router import LocalRouter
ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);args=ap.parse_args();assert args.input.resolve()!=args.output.resolve();src=args.input;b=p.LoadBoard(str(src));b.BuildConnectivity()
fps={f.GetReference():f for f in b.GetFootprints()};c=fps['C2007'];assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in c.Pads())
c.Flip(c.GetPosition(),False)
def xy(q):return (p.ToMM(q.GetPosition().x),p.ToMM(q.GetPosition().y))
def point(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def box(o):
 q=o.GetBoundingBox(False,False) if isinstance(o,p.FOOTPRINT) else o.GetBoundingBox();return [p.ToMM(v) for v in (q.GetX(),q.GetY(),q.GetRight(),q.GetBottom())]
def overlap(a,z):return a[0]<z[2] and a[2]>z[0] and a[1]<z[3] and a[3]>z[1]
occupied=[box(f) for f in b.GetFootprints() if not f.IsFlipped() and f.GetReference()!='C2007']
for t in b.GetTracks():
 if t.IsOnLayer(p.F_Cu):
  z=box(t);occupied.append([z[0]-.2,z[1]-.2,z[2]+.2,z[3]+.2])
selected=None;free=0;failures={}
for x,y in sorted(((x/4,y/4) for x in range(188,249) for y in range(76,121)),key=lambda q:math.dist(q,(51.98,25.35))):
 for angle in (0,90,180,270):
  c.SetPosition(point((x,y)));c.SetOrientationDegrees(angle)
  if any(overlap(box(c),z) for z in occupied):continue
  free+=1
  pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};r=LocalRouter(b,(46,18,64,31),width=.2)
  paths=[]
  for a,z in [(pads['Y2001','1'],pads['C2007','1']),(pads['Y2001','4'],pads['C2007','1']),(pads['C2007','2'],pads['Y2001','2'])]:
   path=r.solve(r.blocked(p.F_Cu,a.GetNetname()),r.cell(xy(a)),r.cell(xy(z)))
   if not path:
    key=a.GetParentFootprint().GetReference()+'.'+a.GetNumber();failures[key]=failures.get(key,0)+1;break
   paths.append(([xy(a)]+path+[xy(z)],a.GetNetname()))
  if len(paths)==3:selected=(x,y,angle,paths);break
 if selected:break
print('Free',free,'failures',failures,flush=True)
assert selected,'No local placement with routes'
x,y,angle,paths=selected;records=[]
for path,name in paths:
 for a,z in zip(path,path[1:]):
  if math.dist(a,z)<1e-6:continue
  t=p.PCB_TRACK(b);t.SetStart(point(a));t.SetEnd(point(z));t.SetWidth(p.FromMM(.2));t.SetLayer(p.F_Cu);t.SetNetCode(b.FindNet(name).GetNetCode());b.Add(t)
 records.append({'net':name,'length_mm':sum(math.dist(a,z) for a,z in zip(path,path[1:]))})
p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();out=args.output;p.SaveBoard(str(out),b)
report={'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'pcb_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'capacitor':{'ref':'C2007','xy_mm':[x,y],'orientation':angle,'side':'front'},'paths':records,'status':'CANDIDATE; DRC AND CONTINUITY REQUIRED','upstream_pmic_connected':False,'production_ready':False};args.report.write_text(json.dumps(report,indent=2)+'\n');print(report)
