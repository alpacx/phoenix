#!/usr/bin/env python3
"""Conservative simultaneous CPU escape experiment; never a production router."""
import csv,json,math,shutil,heapq,os,random
from pathlib import Path
import pcbnew
from screen_rk3562_ddr_escape import distance_segment
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'migration-rk3562';P=BASE/'experiments/lpddr4-1gb';OUT=P/'cpu-simultaneous-coupon'
def mm(p):return (pcbnew.ToMM(p.x),pcbnew.ToMM(p.y))
def pt(p):return pcbnew.VECTOR2I(pcbnew.FromMM(p[0]),pcbnew.FromMM(p[1]))
def segdist(a,b,c,d):
    def cross(p,q,r):return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:return 0
    return min(distance_segment(a,c,d),distance_segment(b,c,d),distance_segment(c,a,b),distance_segment(d,a,b))
def main():
    diameter=.45
    OUT.mkdir(exist_ok=True);b=pcbnew.LoadBoard(str(P/'cpu-corner-coupon/cpu-corners.kicad_pcb'))
    pads={p.GetNumber():p for f in b.GetFootprints() for p in f.Pads()};coords={k:mm(p.GetPosition()) for k,p in pads.items()}
    tracks=[];vias=[];done=set()
    for t in b.GetTracks():
        done.add(t.GetNetname())
        if isinstance(t,pcbnew.PCB_VIA):vias.append(mm(t.GetPosition()))
        else:tracks.append((mm(t.GetStart()),mm(t.GetEnd())))
    offsets=sorted([(i*.05,j*.05) for i in range(-30,31) for j in range(-30,31) if .15<=math.hypot(i*.05,j*.05)<=1.5],key=lambda p:math.hypot(*p))
    candidates={};signals=[s for s in csv.DictReader((P/'signal-map.csv').open()) if 'ODT0_CA' not in s['signal'] and s['signal'] not in done]
    for s in signals:
        ball=s['soc_ball'];a=coords[ball];near=[v for k,v in coords.items() if k!=ball and math.dist(a,v)<2.1];opts=[]
        for dx,dy in offsets:
            v=(a[0]+dx,a[1]+dy)
            # Includes 0.25 mm hole-to-copper clearance, not only copper-to-copper.
            if any(math.dist(v,p)<.475-1e-8 for p in near):continue
            if any(distance_segment(p,a,v)<.125+.0762*1.5-1e-8 for p in near):continue
            opts.append(v)
        candidates[ball]=opts
    def bent_escape(r):
        ball=r['soc_ball'];a=coords[ball];near=[p for k,p in coords.items() if k!=ball and math.dist(a,p)<3.5]
        def xy(q):return (a[0]+q[0]*.05,a[1]+q[1]*.05)
        def edge_ok(c,d):
            return not (any(distance_segment(p,c,d)<.2393-1e-8 for p in near) or any(distance_segment(w,c,d)<.3881-1e-8 for w in vias) or any(segdist(c,d,e,f)<.1524-1e-8 for e,f in tracks))
        def via_ok(v):
            return not (any(math.dist(v,p)<.475-1e-8 for p in near) or any(math.dist(v,w)<(.1+.25+diameter/2)-1e-8 for w in vias) or any(distance_segment(v,e,f)<.3881-1e-8 for e,f in tracks))
        queue=[(0,(0,0))];cost={(0,0):0};prev={};end=None
        while queue:
            dist,q=heapq.heappop(queue)
            if dist>cost[q]+1e-9:continue
            c=xy(q)
            if dist>.15 and via_ok(c):end=q;break
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                z=(q[0]+dx,q[1]+dy)
                if max(abs(z[0]),abs(z[1]))>40:continue
                nd=dist+math.hypot(dx,dy)*.05
                if nd>=cost.get(z,1e9) or not edge_ok(c,xy(z)):continue
                cost[z]=nd;prev[z]=q;heapq.heappush(queue,(nd,z))
        if end is None:return
        path=[end]
        while path[-1]!=(0,0):path.append(prev[path[-1]])
        path=[xy(q) for q in reversed(path)]
        for c,d in zip(path,path[1:]):
            t=pcbnew.PCB_TRACK(b);t.SetStart(pt(c));t.SetEnd(pt(d));t.SetLayer(pcbnew.F_Cu);t.SetWidth(pcbnew.FromMM(.0762));t.SetNet(pads[ball].GetNet());b.Add(t);tracks.append((c,d))
        v=pcbnew.PCB_VIA(b);v.SetPosition(pt(path[-1]));v.SetWidth(pcbnew.FromMM(diameter));v.SetDrill(pcbnew.FromMM(.2));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(pads[ball].GetNet());b.Add(v);vias.append(path[-1]);r['via_mm']=path[-1];r['bent_path_mm']=path
    results=[]
    rng=random.Random(int(os.environ.get('PHOENIX_ESCAPE_SEED','11')))
    priority={s['soc_ball']:rng.random() for s in signals}
    for s in sorted(signals,key=lambda s:(s['soc_ball'] not in os.environ.get('PHOENIX_ESCAPE_FIRST','').split(','),len(candidates[s['soc_ball']])==0,priority[s['soc_ball']]) if int(os.environ.get('PHOENIX_ESCAPE_SEED','11')) else len(candidates[s['soc_ball']])):
        ball=s['soc_ball'];a=coords[ball];chosen=None
        for v in ([] if ball in os.environ.get('PHOENIX_ESCAPE_DEFER','').split(',') else candidates[ball]):
            if any(math.dist(v,w)<(.1+.25+diameter/2)-1e-8 or distance_segment(w,a,v)<.1+.25+.0762/2-1e-8 for w in vias):continue
            if any(distance_segment(v,c,d)<.1+.25+.0762/2-1e-8 or segdist(a,v,c,d)<.0762*2-1e-8 for c,d in tracks):continue
            chosen=v;break
        results.append({**s,'individual_candidates':len(candidates[ball]),'via_mm':chosen})
        if chosen is None:
            if os.environ.get('PHOENIX_ESCAPE_EAGER'):bent_escape(results[-1])
            continue
        t=pcbnew.PCB_TRACK(b);t.SetStart(pt(a));t.SetEnd(pt(chosen));t.SetLayer(pcbnew.F_Cu);t.SetWidth(pcbnew.FromMM(.0762));t.SetNet(pads[ball].GetNet());b.Add(t)
        v=pcbnew.PCB_VIA(b);v.SetPosition(pt(chosen));v.SetWidth(pcbnew.FromMM(diameter));v.SetDrill(pcbnew.FromMM(.2));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(pads[ball].GetNet());b.Add(v)
        tracks.append((a,chosen));vias.append(chosen)
    if not os.environ.get('PHOENIX_ESCAPE_EAGER'):
        deferred=os.environ.get('PHOENIX_ESCAPE_DEFER','').split(',')
        for r in sorted(results,key=lambda r:deferred.index(r['soc_ball'])+1 if r['soc_ball'] in deferred else 0):
            if r['via_mm'] is None:bent_escape(r)
    pcbnew.SaveBoard(str(OUT/'cpu-simultaneous.kicad_pcb'),b)
    shutil.copyfile(P/'cpu-corner-coupon/cpu-corners.kicad_pro',OUT/'cpu-simultaneous.kicad_pro');shutil.copyfile(P/'cpu-corner-coupon/fp-lib-table',OUT/'fp-lib-table')
    report={'status':'BOUNDED_SIMULTANEOUS_GEOMETRY_EXPERIMENT','seed':int(os.environ.get('PHOENIX_ESCAPE_SEED','11')),'priority_balls':os.environ.get('PHOENIX_ESCAPE_FIRST',''),'eager_bends':bool(os.environ.get('PHOENIX_ESCAPE_EAGER')),'deferred_balls':os.environ.get('PHOENIX_ESCAPE_DEFER',''),'new_via_diameter_mm':diameter,'escaped':len(vias),'required':65,'results':results,'unresolved':[r['soc_ball'] for r in results if r['via_mm'] is None],'limits':['Greedy straight candidates and bounded bent fallback after five fixed corner bends; failure does not prove impossibility','Provisional CPU lands','No planes, component neighbors, impedance or timing qualification','3 mil process not qualified'],'assembly_ready':False}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['escaped','required','unresolved']}))
if __name__=='__main__':main()
