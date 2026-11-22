"""Find the closest intact copper corridors on either side of the L403-to-memory bottleneck."""
from pathlib import Path
from collections import Counter
import json
import sys
import numpy as np
from scipy.spatial import cKDTree

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((root/n).read_text())
emmc='--emmc-1v8' in sys.argv
a=read('sys-feed-r8006.1.json' if emmc else 'lpddr-vddq-rear-source-feed.json');z=read('sys-feed-r8006.1-load.json' if emmc else 'lpddr-vddq-load-frontier.json')
assert a['sha256']==z['sha256']
left=np.asarray(read('runs/sys-feed-r8006.1-frontier.json' if emmc else 'runs/lpddr-vddq-copper-frontier.json'))
right=np.asarray(read('runs/sys-feed-r8006.1-load-frontier.json' if emmc else 'runs/lpddr-vddq-load-frontier.json'))
rows=[]
for l,name in enumerate(['F.Cu','In3.Cu','In2.Cu','B.Cu']):
    src=left[left[:,0]==l,1:];dst=right[right[:,0]==l,1:]
    if not len(dst) or not len(src):continue
    distances,neighbours=cKDTree(dst).query(src)
    chosen=[]
    for index in np.argsort(distances,kind='stable'):
        dist=distances[index]
        if dist>(9000000 if emmc else 2500000):break
        start=src[index]
        if any(np.linalg.norm(start-np.array(r['source_nm']))<1200000 for r in chosen):continue
        chosen.append(dict(source_nm=start.tolist(),load_nm=dst[neighbours[index]].tolist(),gap_mm=dist/1e6))
        if len(chosen)>=16:break
    rows.append(dict(layer=name,overlapping_cells=int(np.count_nonzero(distances==0)),closest_gap_mm=float(np.min(distances)/1e6),representatives=chosen))
(root/('emmc-1v8-corridor-gaps.json' if emmc else 'vddq-corridor-gaps.json')).write_text(json.dumps(dict(parent_sha256=a['sha256'],grid_mm=.10,width_mm=.60,rows=rows,assembly_ready=False),indent=2)+'\n')
print([(q['layer'],q['overlapping_cells'],q['closest_gap_mm'],len(q['representatives'])) for q in rows])
