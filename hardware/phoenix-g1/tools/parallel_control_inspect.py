import pcbnew as p,json
from pathlib import Path
S=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel';b=p.LoadBoard(str(S/'baseline/source.kicad_pcb'));b.BuildConnectivity()
xy=lambda q:[p.ToMM(q.GetPosition().x),p.ToMM(q.GetPosition().y)];box=lambda q:[p.ToMM(v) for v in (q.GetX(),q.GetY(),q.GetWidth(),q.GetHeight())]
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
print('U4.61',xy(pads['U4','61']))
for n in range(57,65):
 q=pads['U4',str(n)];print(n,q.GetNetname(),xy(q),q.GetSize())
for t in b.GetTracks():
 if t.GetNetname()=='+1V8_SYS':
  coords=[p.ToMM(v) for v in (t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y)]
  if min(coords[0],coords[2])>45 and max(coords[1],coords[3])<16:print(t.m_Uuid.AsString(),b.GetLayerName(t.GetLayer()),coords,p.ToMM(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth()))
data={'footprints':[{'ref':f.GetReference(),'xy':xy(f),'layer':b.GetLayerName(f.GetLayer()),'box':box(f.GetCourtyard(f.GetLayer()).BBox()),'pads':[{'box':box(q.GetBoundingBox(f.GetLayer())),'net':q.GetNetname(),'num':q.GetNumber()} for q in f.Pads()]} for f in b.GetFootprints()], 'tracks':[{'net':t.GetNetname(),'xy':[p.ToMM(v) for v in (t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y)],'layer':b.GetLayerName(t.GetLayer()),'width':p.ToMM(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth()),'via':isinstance(t,p.PCB_VIA)} for t in b.GetTracks()]};(S/'geometry.json').write_text(json.dumps(data))
