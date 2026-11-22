"""Search full-width input taps from existing In2 rail to a front-side relocated link."""
import json, hashlib, math, os
from pathlib import Path
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=root/'runs/input-ground-local-002'
src=base/'phy-joint.kicad_pcb'
digest=hashlib.sha256(src.read_bytes()).hexdigest()
assert digest==json.loads((base/'report.json').read_text())['candidate_sha256']
b=p.LoadBoard(str(src))
b.BuildConnectivity()
r=b.FindFootprintByReference('R530')
target=b.FindFootprintByReference('C515').FindPadByNumber('1').GetPosition()
def pt(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def xy(v):return tuple(p.ToMM(i) for i in v)
def length(a,z):return math.dist(xy(a),xy(z))
rail='+3V3_IO'
load='+3V3_PHY'
objs=list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference()!='R530' for q in f.Pads()]
objs=[o for o in objs if o.GetBoundingBox().Inflate(p.FromMM(15)).Contains(target)]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
shapes={l:[(o.GetNetname(),o.GetEffectiveShape(l)) for o in objs if o.IsOnLayer(l)] for l in layers}
def free(shape,layer,net):
 return all(n==net or not shape.Collide(other,p.FromMM(.2)) for n,other in shapes[layer])
def clear(a,z,layer,net):
 t=p.PCB_TRACK(b);t.SetStart(a);t.SetEnd(z);t.SetLayer(layer);t.SetWidth(p.FromMM(1.05))
 return free(t.GetEffectiveShape(layer),layer,net)
connected={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(r.FindPadByNumber('1'))}
seeds={xy(v) for t in b.GetTracks() if t.m_Uuid.AsString() in connected and t.GetNetname()==rail and t.IsOnLayer(p.In2_Cu) for v in (t.GetStart(),t.GetEnd()) if length(v,target)<12}

landings=json.loads((root/'r530-inner-tap-wide.json').read_text())['inner_taps']
other_boxes=[f.GetCourtyard(f.GetLayer()).BBox() for f in b.GetFootprints() if f.GetReference()!='R530' and f.GetLayer()==p.F_Cu]
options=[]
for landing,seed in landings:
 v=pt(*landing)
 for angle in range(0,360,15):
  rad=math.radians(angle)
  for approach in (-60,-30,0,30,60):
   direction=rad+math.radians(approach)
   for gap in (.85,1.05,1.3,1.6,2,2.5):
    # KiCad positive footprint rotation turns toward negative board y.
    a=v+pt(gap*math.cos(direction),-gap*math.sin(direction))
    center=a+pt(.51*math.cos(rad),-.51*math.sin(rad))
    r.SetOrientationDegrees(angle);r.SetPosition(center)
    if any(r.GetCourtyard(p.F_Cu).BBox().Intersects(z) for z in other_boxes):continue
    if any(not free(q.GetEffectiveShape(p.F_Cu),p.F_Cu,q.GetNetname()) for q in r.Pads()):continue
    if clear(v,a,p.F_Cu,rail):
     options.append(dict(center=xy(center),angle=angle,input_endpoint=landing,seed=seed,length=length(v,a)))
options.sort(key=lambda q:q['length'])
(root/'r530-front-directed-sites.json').write_text(json.dumps(options,indent=2)+'\n')
print(len(options),options[:1],flush=True);os._exit(0)
