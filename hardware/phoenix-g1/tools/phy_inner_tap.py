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
landings=[]
for i in range(-24,25):
 for j in range(-24,25):
  pos=target+pt(i*.25,j*.25)
  via=p.PCB_VIA(b);via.SetPosition(pos);via.SetWidth(p.FromMM(.6));via.SetDrill(p.FromMM(.3));via.SetLayerPair(p.F_Cu,p.B_Cu)
  if any(isinstance(o,p.PAD) and o.GetBoundingBox().Inflate(p.FromMM(.35)).Contains(pos) for o in objs):continue
  if not all(free(via.GetEffectiveShape(layer),layer,rail) for layer in layers):continue
  for seed in sorted(seeds,key=lambda s:length(pt(*s),pos)):
   if clear(pt(*seed),pos,p.In2_Cu,rail):
    landings.append((xy(pos),seed));break
routes=[]
for i in range(-20,21):
 for j in range(-20,21):
  center=target+pt(i*.25,j*.25)
  for angle in range(0,360,45):
   rad=math.radians(angle);off=pt(.51*math.cos(rad),.51*math.sin(rad));a=center-off;z=center+off
   if length(z,target)<.8 or not clear(z,target,p.F_Cu,load):continue
   for via,seed in landings:
    if length(a,pt(*via))<.8 or not clear(a,pt(*via),p.F_Cu,rail):continue
    routes.append(dict(center=xy(center),angle=angle,via=via,seed=seed))
report=dict(source_sha256=digest,rail_endpoints=len(seeds),inner_taps=landings,geometric_routes=routes,width_mm=1.05,assembly_ready=False)
(root/'r530-inner-tap-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print(len(seeds),len(landings),len(routes),flush=True);os._exit(0)
