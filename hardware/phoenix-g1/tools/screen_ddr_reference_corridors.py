"""Screen outer-layer 45-degree LPDDR4 via-to-via routes against filled reference copper."""
from pathlib import Path
import argparse,hashlib,json,math,os
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--checkpoint', default='layout-opposite-bypass.json')
parser.add_argument('--output', default='ddr-reference-corridors.json')
args=parser.parse_args()
cp=json.loads((root/args.checkpoint).read_text())
src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
chips=[b.FindFootprintByReference(ref) for ref in ('U1','U2')]
obs=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
planes={l:next(z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname()=='GND' and z.IsOnLayer(l)) for l in (p.In1_Cu,p.In4_Cu)}
vias_by_id={k.m_Uuid.AsString():k for k in b.GetTracks() if isinstance(k,p.PCB_VIA)}
rows=[]
for name in sorted(n for n in cp['open_nets'] if n.startswith('LPDDR4_')):
    pins=[[q for q in chip.Pads() if q.GetNetname()==name] for chip in chips]
    if list(map(len,pins))!=[1,1]:continue
    ends=[]
    for (q,) in pins:
        group=b.GetConnectivity().GetConnectedItems(q)
        ends.append([vias_by_id[k.m_Uuid.AsString()] for k in group if k.m_Uuid.AsString() in vias_by_id])
    row=dict(net=name,escape_via_counts=list(map(len,ends)),paths=[])
    rows.append(row)
    if list(map(len,ends))!=[1,1]:continue
    a,z=[items[0].GetPosition() for items in ends]
    row['via_nm']=[tuple(a),tuple(z)]
    dx,dy=z-a;d=min(abs(dx),abs(dy));step=p.VECTOR2I(int(math.copysign(d,dx)),int(math.copysign(d,dy)))
    for layer,ref in ((p.F_Cu,p.In1_Cu),(p.B_Cu,p.In4_Cu)):
        for c in (a+step,z-step):
            segs=[]
            for start,end in ((a,c),(c,z)):
                if start==end:continue
                t=p.PCB_TRACK(b);t.SetStart(start);t.SetEnd(end);t.SetWidth(200000);t.SetLayer(layer);segs.append(t)
            blockers=set();uncovered=0;covered=0
            for t in segs:
                near=t.GetBoundingBox().Inflate(200000)
                shape=t.GetEffectiveShape(layer)
                for other in obs:
                    if other.GetNetname()==name or not other.IsOnLayer(layer) or not near.Intersects(other.GetBoundingBox()):continue
                    if shape.Collide(other.GetEffectiveShape(layer),200000):
                        blockers.add(other.GetNetname() or '<mechanical>')
                steps=max(1,math.ceil(t.GetLength()/100000))
                for i in range(steps+1):
                    point=p.VECTOR2I(*(round(x+(y-x)*i/steps) for x,y in zip(t.GetStart(),t.GetEnd())))
                    if min(math.dist(tuple(point),tuple(v)) for v in (a,z))<600000:continue
                    if planes[ref].HitTestFilledArea(ref,point):covered+=1
                    else:uncovered+=1
            row['paths'].append(dict(layer=b.GetLayerName(layer),corner_nm=tuple(c),length_mm=sum(t.GetLength() for t in segs)/1e6,obstacle_nets=sorted(blockers),reference_centerline_samples=covered+uncovered,reference_misses=uncovered))
report=dict(source_sha256=cp['sha256'],width_screen_mm=.2,spacing_screen_mm=.2,reference_step_mm=.1,excluded_endpoint_radius_mm=.6,nets=rows,impedance_qualified=False,timing_qualified=False)
(root/args.output).write_text(json.dumps(report,indent=2)+'\n')
print(len(rows),sum(r['escape_via_counts']==[1,1] for r in rows),sum(not p['obstacle_nets'] and not p['reference_misses'] for r in rows for p in r['paths']),flush=True)
os._exit(0)
