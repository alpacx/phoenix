#!/usr/bin/env python3
"""Illustrative KiCad render copy; simplified bodies, not assembly validation."""
import pcbnew as p,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[3];base=root/'hardware/phoenix-g1/migration-rk3562/experiments/stacked-expansion';out=root/'results/hardware-render-stacked';models=out/'models';models.mkdir(parents=True,exist_ok=True)
c=json.loads((base/'audit.json').read_text());c['sha256']=c['pcb_sha256'];src=base/'pcb/candidate.kicad_pcb';assert hashlib.sha256(src.read_bytes()).hexdigest()==c['sha256'];b=p.LoadBoard(str(src));report=[]
for f in b.GetFootprints():
 if len(f.Models()):continue
 ref=f.GetReference();g=p.FOOTPRINT(f)
 if g.IsFlipped():g.Flip(g.GetPosition(),False)
 g.SetOrientationDegrees(0);g.SetPosition(p.VECTOR2I(0,0))
 boxes=[x.GetBoundingBox() for x in g.GraphicalItems() if isinstance(x,p.PCB_SHAPE) and x.GetLayer()==p.F_Fab]
 if not boxes:boxes=[g.GetBoundingBox(False,False)]
 x0=min(p.ToMM(x.GetX()) for x in boxes);y0=min(p.ToMM(x.GetY()) for x in boxes);x1=max(p.ToMM(x.GetRight()) for x in boxes);y1=max(p.ToMM(x.GetBottom()) for x in boxes)
 w=max(.4,x1-x0);d=max(.4,y1-y0);h=.5;color='.19 .20 .22'
 if ref.startswith('C'):color='.54 .43 .28';h=.55
 elif ref.startswith('R'):h=.35
 elif ref.startswith('L'):h=1.4
 elif ref.startswith('U'):h=1
 elif ref.startswith('J'):h=2.2;color='.65 .67 .70'
 if ref=='U1':w=d=13.9;h=1.1
 if ref=='U2':w=10;d=15;h=1
 if ref=='U25':w=d=12;h=1.8;color='.63 .65 .66'
 if ref=='J3':w=9.52;d=2.97;h=1.14;color='.18 .19 .20'
 if ref=='J2':h=13.5;color='.59 .61 .64'
 if ref=='J1':h=3.2;color='.68 .70 .73'
 path=models/(ref+'.wrl');cx=(x0+x1)/2;cy=-(y0+y1)/2
 path.write_text('#VRML V2.0 utf8\nTransform { translation %f %f %f children [ Shape { appearance Appearance { material Material { diffuseColor %s shininess 0.25 } } geometry Box { size %f %f %f } } ] }\n'%(cx/2.54,cy/2.54,(h/2+.05)/2.54,color,w/2.54,d/2.54,h/2.54))
 m=p.FP_3DMODEL();m.m_Filename=str(path);f.Add3DModel(m);report.append({'reference':ref,'approximate_size_mm':[w,d,h]})
p.SaveBoard(str(out/'phoenix-visualization.kicad_pcb'),b)
(out/'render-scope.json').write_text(json.dumps({'source_sha256':c['sha256'],'source_outline_mm':[90,40],'simplified_models':report,'missing':['display','five-way control final placement','eMMC integration','heatsink/enclosure'],'production_ready':False},indent=2))
print('Approximate models:',len(report))
