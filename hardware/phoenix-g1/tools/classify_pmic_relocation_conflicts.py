"""Classify exact native fixed courtyards which exclude alternative RK809 positions."""
from collections import Counter
import json
from pathlib import Path
from tempfile import gettempdir
from shapely.geometry import box,Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
snapshot=json.loads((Path(gettempdir())/'phoenix-pmic-floorplan-native.json').read_text())
study=json.loads((root/'pmic-four-stage-floorplan.json').read_text())
assert snapshot['sha256']==study['source_sha256']
fs=snapshot['footprints'];origin=fs['U4'];ids=[];geoms=[]
omit={'U4','L405','C425','C435','C412'}
for i in range(1,5):omit.update([f'L40{i}',f'C42{i}',f'C43{i}'])
for ref,f in fs.items():
    if ref in omit or f['side']!='F.Cu':continue
    ids.append(ref);geoms.append(unary_union([Polygon(x) for x in f['court']]).buffer(.1,join_style=2))
for i,z in enumerate(snapshot['keepouts']):
    if z['footprints'] and 'F.Cu' in z['layers']:
        ids.append('keepout '+str(i));geoms.append(unary_union([Polygon(x) for x in z['poly']]).buffer(.08))
def category(name):
    if name.startswith(('H','J','keepout')):return 'mechanical interfaces and keepouts'
    if name.startswith(('U','Y','L')):return 'packages, clocks and power inductors'
    return 'passives, test pads and other'
index=STRtree(geoms);hits=Counter();exclusive=Counter();cat_counts=Counter();rows=[]
# U4 is a square; quarter-turns duplicate the same courtyard.
centers={tuple(row['center_mm']) for row in study['states']}
for x,y in centers:
    area=box(x-4.105,y-4.105,x+4.105,y+4.105);refs=sorted(ids[i] for i in index.query(area,predicate='intersects'))
    hits.update(refs)
    if len(refs)==1:exclusive.update(refs)
    cat_counts.update([tuple(sorted(set(map(category,refs))))])
    if 0<len(refs)<=2:rows.append(dict(xy_mm=[x,y],refs=refs))
result=dict(source_sha256=snapshot['sha256'],evaluated_unique_centres=len(centers),occurrences=hits.most_common(),only_obstacle=exclusive.most_common(),categories={' / '.join(k) or 'clear':v for k,v in cat_counts.items()},one_or_two_conflicts=sorted(rows,key=lambda r:((r['xy_mm'][0]-60)**2+(r['xy_mm'][1]-9)**2)))
(root/'pmic-relocation-obstacles.json').write_text(json.dumps(result,indent=2)+'\n')
print(len(centers),hits.most_common(6),exclusive.most_common(6))
