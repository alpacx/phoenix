#!/usr/bin/env python3
"""Search bent local escapes for five constrained CPU DDR pins; independent-pin only."""
import json,math,heapq
from pathlib import Path
from screen_rk3562_ddr_escape import distance_segment
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'migration-rk3562';P=BASE/'experiments/lpddr4-1gb'
def main():
    pads={r['ball']:(r['x_mm'],r['y_mm']) for r in json.loads((BASE/'review/package-candidate.json').read_text())['pads']}
    report=[]
    for width,clear in [(.1,.1),(.0762,.0762)]:
        for ball in ['B2','B26','B3','B25','C2']:
            origin=pads[ball];near=[v for k,v in pads.items() if k!=ball and math.dist(origin,v)<2.2];queue=[(0,(0,0))];cost={(0,0):0};prev={};end=None
            def world(q):return (origin[0]+q[0]*.05,origin[1]+q[1]*.05)
            while queue:
                dist,q=heapq.heappop(queue)
                if dist>cost[q]+1e-9:continue
                a=world(q)
                if math.dist(a,origin)>=.35 and all(math.dist(a,p)>=.125+.225+clear-1e-8 for p in near):end=q;break
                for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                    n=(q[0]+dx,q[1]+dy)
                    if max(abs(n[0]),abs(n[1]))>30:continue
                    w=world(n);nd=dist+math.hypot(dx,dy)*.05
                    if nd>=cost.get(n,float('inf'))-1e-9:continue
                    if any(distance_segment(p,a,w)<.125+width/2+clear-1e-8 for p in near):continue
                    cost[n]=nd;prev[n]=q;heapq.heappush(queue,(nd,n))
            path=[]
            if end is not None:
                q=end
                while q!=(0,0):path.append(world(q));q=prev[q]
                path.append(origin);path.reverse()
            report.append({'ball':ball,'width_mm':width,'clearance_mm':clear,'found':end is not None,'length_mm':round(cost[end],4) if end is not None else None,'path_mm':path,'visited_states':len(cost)})
    (P/'system/review/cpu-escape-bends.json').write_text(json.dumps({'status':'INDEPENDENT_LOCAL_PATHS_NOT_SIMULTANEOUS_ROUTING','search_halfspan_mm':1.5,'grid_mm':.05,'via_mm':[.45,.2],'results':report,'holds':['Provisional CPU land pattern','3mil fabrication process confirmation','Mutual via/trace collisions','Full six-layer routing and SI']},indent=2)+'\n')
    print([{k:v for k,v in r.items() if k not in ['path_mm']} for r in report])
if __name__=='__main__':main()
