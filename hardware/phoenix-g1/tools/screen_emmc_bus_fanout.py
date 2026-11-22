"""Check best-case simultaneous package fanout with fixed eMMC lands and the existing process."""
import csv,hashlib,heapq,json,math,sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import label

root=Path(__file__).resolve().parents[1]
stage=root/'migration-rk3562/experiments/phy-power-parallel'
entry=json.loads((stage/'layout-emmc-data-power.json').read_text())
source=stage/entry['board'];assert hashlib.sha256(source.read_bytes()).hexdigest()==entry['sha256']
balls=list(csv.DictReader((root/'migration-rk3562/experiments/emmc-8gb/ball-disposition.csv').open()))
assert len(balls)==153 and len({q['ball'] for q in balls})==153
positions={q['ball']:(float(q['x_mm']),float(q['y_mm'])) for q in balls}
signals={q['ball']:q['function'] for q in balls if q['function'].startswith('DAT') or q['function'] in ('CLK','CMD','STRB','RSTN')}
fine='--jlc-local-3mil' in sys.argv
step=.010 if fine else .025;size=round(10/step)+1;g=np.arange(size)*step-5;x,y=np.meshgrid(g,g,indexing='ij');sample=np.stack([x,y],axis=2);xy=sample.reshape(-1,2)
pads=np.array(list(positions.values()))
clearance=.0782 if fine else .202;pad_radius=.125;track_radius=.0381 if fine else .100;via_radius=.225;drill_radius=.1;hole_clearance=.252;guard=step/math.sqrt(2)
dirs=((0,1),(0,-1),(1,0),(-1,0),(1,1),(-1,-1),(1,-1),(-1,1))
def calculate(ball,tracks,barrels):
    point=np.array(positions[ball]);other=pads[np.any(pads!=point,axis=1)]
    dist=cKDTree(other).query(xy)[0].reshape((size,size))
    origin_dist=np.linalg.norm(sample-point,axis=2)
    open_track=dist>pad_radius+track_radius+clearance+guard
    open_via=(dist>pad_radius+max(via_radius+clearance,drill_radius+hole_clearance)+guard)&(origin_dist>pad_radius+via_radius+.052+guard)
    if tracks:
        td=cKDTree(np.array(tracks)).query(xy)[0].reshape((size,size))
        open_track &= td>2*track_radius+clearance+guard
        open_via &= td>track_radius+max(via_radius+clearance,drill_radius+hole_clearance)+guard
    if barrels:
        bd=cKDTree(np.array(barrels)).query(xy)[0].reshape((size,size))
        open_track &= bd>track_radius+max(via_radius+clearance,drill_radius+hole_clearance)+guard
        open_via &= bd>max(2*via_radius+clearance,via_radius+drill_radius+hole_clearance,2*drill_radius+hole_clearance)+guard
    # Four-connected flood on clearance-expanded geometry prevents corner jumps.
    components,count=label(open_track)
    origin=tuple(np.rint((point+5)/step).astype(int))
    if not components[origin]:return dict(sites=0,reachable=0),[]
    reached=components==components[origin];sites=np.argwhere(open_via&reached)
    if not len(sites):return dict(sites=0,reachable=int(np.count_nonzero(reached))),[]
    queue=[(0,origin)];cost={origin:0};prev={}
    while queue:
        length,pt=heapq.heappop(queue)
        if cost[pt]!=length:continue
        if open_via[pt]:
            trace=[pt]
            while trace[-1] in prev:trace.append(prev[trace[-1]])
            coords=[tuple(sample[tuple(s)]) for s in reversed(trace)]
            return dict(sites=len(sites),reachable=int(np.count_nonzero(reached)),selected_via_mm=coords[-1],land_to_via_mm=length,path_mm=coords),coords
        for dx,dy in dirs:
            end=(pt[0]+dx,pt[1]+dy)
            if not 0<=end[0]<size or not 0<=end[1]<size or not reached[end]:continue
            if dx and dy and (not reached[pt[0]+dx,pt[1]] or not reached[pt[0],pt[1]+dy]):continue
            distance=length+step*math.hypot(dx,dy)
            if distance>=cost.get(end,math.inf):continue
            prev[end]=pt;cost[end]=distance;heapq.heappush(queue,(distance,end))
    raise AssertionError('Connected site unexpectedly unreachable')
individual={ball:calculate(ball,[],[])[0] for ball in signals};allowed=sorted((ball for ball in signals if individual[ball]['sites']),key=lambda ball:individual[ball]['sites'])
simultaneous={};tracks=[];barrels=[]
for ball in allowed:
    result,path=calculate(ball,tracks,barrels);simultaneous[ball]=result
    if path:tracks.extend(path);barrels.append(path[-1])
area=dict(fixed_balls=len(balls),fixed_RFU=sum(q['function']=='RFU' for q in balls),pad_diameter_mm=.25,pitch_mm=.50,signal_width_mm=2*track_radius,drill_mm=.20,via_land_mm=.45,clearance_mm=clearance,drill_to_copper_mm=hole_clearance,conservative_raster_allowance_mm=guard,raster_mm=step)
report=dict(parent_sha256=entry['sha256'],scope='Isolated land-array geometry in package coordinates; excludes physical board obstacles, plane returns, remaining rails, manufacturing tolerances and timing.',geometry=area,signals=signals,individual=individual,simultaneous=simultaneous,existing_board_socket_D0_verified=True,assembly_ready=False)
(stage/('emmc-bus-local-3mil-study.json' if fine else 'emmc-bus-package-feasibility.json')).write_text(json.dumps(report,indent=2)+'\n')
print('Standalone fails',[(ball,signals[ball]) for ball in signals if not individual[ball]['sites']]);print('Simultaneous',[(ball,signals[ball]) for ball,row in simultaneous.items() if row['sites']])
