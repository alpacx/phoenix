#!/usr/bin/env python3
"""Bounded straight-dogbone search on provisional CPU land geometry; not routing proof."""
import csv,json,math,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'migration-rk3562';P=BASE/'experiments/lpddr4-1gb'
def distance_segment(p,a,b):
    dx=b[0]-a[0];dy=b[1]-a[1];t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
def main():
    pads={r['ball']:(r['x_mm'],r['y_mm']) for r in json.loads((BASE/'review/package-candidate.json').read_text())['pads']}
    signals=[r for r in csv.DictReader((P/'signal-map.csv').open()) if 'ODT0_CA' not in r['signal']]
    offsets=sorted([(i*.05,j*.05) for i in range(-30,31) for j in range(-30,31) if .15<=math.hypot(i*.05,j*.05)<=1.5],key=lambda p:math.hypot(*p))
    cases=[]
    for width,clear in [(.1,.1),(.0762,.0762)]:
        results=[]
        for s in signals:
            a=pads[s['soc_ball']];near=[v for k,v in pads.items() if k!=s['soc_ball'] and math.dist(a,v)<2.1];found=None
            for dx,dy in offsets:
                v=(a[0]+dx,a[1]+dy)
                if any(math.dist(v,p)<.125+.225+clear-1e-8 for p in near):continue
                if any(distance_segment(p,a,v)<.125+width/2+clear-1e-8 for p in near):continue
                found={'offset_mm':[round(dx,4),round(dy,4)],'length_mm':round(math.hypot(dx,dy),4)};break
            results.append({**s,'straight_escape':found})
        cases.append({'width_mm':width,'clearance_mm':clear,'via_land_drill_mm':[.45,.2],'individual_candidates':sum(r['straight_escape'] is not None for r in results),'no_candidate_in_search':[r['soc_ball'] for r in results if r['straight_escape'] is None],'results':results})
    out={'status':'BOUNDED_SINGLE_PIN_GEOMETRY_SCREEN_ONLY','land_mm':.25,'land_qualified':False,'search_radius_mm':1.5,'grid_mm':.05,'cases':cases,'limitations':['Straight segments only; lack of a candidate does not establish impossibility','Independent pins: candidate via and trace collisions with each other not checked','No neighboring components, power fanout or planes','3mil clearance requires exact fabrication process confirmation','Not an impedance or simultaneous routing result']}
    (P/'system/review/cpu-escape-screen.json').write_text(json.dumps(out,indent=2)+'\n')
    print([(c['width_mm'],c['individual_candidates'],c['no_candidate_in_search']) for c in cases])
if __name__=='__main__':main()
