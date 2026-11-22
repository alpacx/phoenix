"""Form the two conductor centrelines of a mitred clock corridor."""
import json
import sys
from shapely.geometry import LineString
d=json.load(sys.stdin)
center=LineString(d["points_nm"])
paths=[]
for d in (-225000,225000):
    offset=center.offset_curve(d,join_style="mitre")
    assert offset.geom_type=="LineString"
    paths.append([[round(x),round(y)] for x,y in offset.coords])
print(json.dumps(paths))
