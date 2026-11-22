"""Rank reversible rear-cap displacements that can actually receive paired vias from VCC9."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import os
import sys
import pcbnew as p
from pcb_bounds import inflated_box

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel/runs'
folder=root/'pmic-five-stage-secondary-0';src=folder/'phy-joint.kicad_pcb';report=json.loads((folder/'output-legs.json').read_text())
assert hashlib.sha256(src.read_bytes()).hexdigest()==report['board_sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
cap=b.FindFootprintByReference('C425');power=cap.FindPadByNumber('1');ground=cap.FindPadByNumber('2');side=p.B_Cu;code=power.GetNetCode()
owner=lambda o:o.GetParentFootprint().GetReference() if isinstance(o,p.PAD) else o.m_Uuid.AsString()
v=lambda pt:p.VECTOR2I(*pt)
origin=v((65000000,10575000));near=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference()!='C425' for q in f.Pads()] if inflated_box(o,7500000).Contains(origin)]
ls=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
reserve='--reserve-supply' in sys.argv
if reserve:
    antecedent=p.LoadBoard(str(root/'pmic-five-stage-sense-0/phy-joint.kicad_pcb'))
    base_ids={t.m_Uuid.AsString() for t in antecedent.GetTracks()}
    stage=p.LoadBoard(str(root/'pmic-five-stage-feedback-0/phy-joint.kicad_pcb'))
    sense_ids={t.m_Uuid.AsString() for t in stage.GetTracks() if t.GetNetname()=='+1V8_SYS' and t.m_Uuid.AsString() not in base_ids}
    near=[o for o in near if o.m_Uuid.AsString() not in sense_ids]
geometry={k:[(o.GetNetCode(),owner(o),o.GetEffectiveShape(k),o.GetBoundingBox()) for o in near if o.IsOnLayer(k)] for k in ls}
drills=[(o.GetNetCode(),owner(o),o.GetEffectiveHoleShape(),o.GetPosition()) for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
courts=[(f.GetReference(),f.GetCourtyard(side)) for f in b.GetFootprints() if f.GetLayer()==side and f.GetReference()!='C425' and inflated_box(f,7500000).Contains(origin)]
areas=list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()]
vias_keep=[z.Outline() for z in areas if z.GetIsRuleArea() and z.GetDoNotAllowVias()];tr_keep={k:[z.Outline() for z in areas if z.GetIsRuleArea() and z.IsOnLayer(k) and z.GetDoNotAllowTracks()] for k in ls}
def trace(a,z,w,net,layer):
    t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetNetCode(net);t.SetWidth(w);t.SetStart(v(a));t.SetEnd(v(z));return t
def impacts(obj,layer,ignore=frozenset()):
    shape=obj.GetEffectiveShape(layer);box=inflated_box(obj,400000);net=obj.GetNetCode()
    hits={name for c,name,g,r in geometry[layer] if c!=net and name not in ignore and box.Intersects(r) and shape.Collide(g,202000)}
    hits.update(name for c,name,h,pt in drills if c!=net and name not in ignore and box.Contains(pt) and shape.Collide(h,250000))
    if any(shape.Collide(z,0) for z in tr_keep[layer]):hits.add('track-keepout')
    return hits
def via(at):
    o=p.PCB_VIA(b);o.SetViaType(p.VIATYPE_THROUGH);o.SetLayerPair(p.F_Cu,p.B_Cu);o.SetDrill(200000);o.SetWidth(450000);o.SetPosition(v(at));o.SetNetCode(code);return o
# These four traces attach C425 at its present position. Evaluate the replacement
# separately while preserving both existing original EP barrels.
oldg={'490585d8-b8ee-482d-8fcf-eef4b7e2ec95','49a50d01-079a-4607-95c7-50da592500de','4f82c973-bd2e-4f21-b66d-021a90ab2468','dc4123ab-539b-4176-81d4-58ed0c0e54fb'}
assert oldg <= {o.m_Uuid.AsString() for o in near if isinstance(o,p.PCB_TRACK) and o.GetNetname()=='GND'}
supply=next(r for r in report['rows'] if r['stage']==5 and r['role']=='PMIC to input bypass')
pairs=[];sites={};cause=Counter();blocked_sites={}
for entry in supply['source_map']:
    pt=tuple(entry['pt_nm']);path=entry['route_nm']
    front=set().union(*(impacts(trace(a,z,500000,code,p.F_Cu),p.F_Cu) for a,z in zip(path,path[1:]))); hits=set(front)
    o=via(pt);sh=o.GetEffectiveShape(side);box=inflated_box(o,450000);h=o.GetEffectiveHoleShape()
    if any(sh.Collide(z,0) for z in vias_keep):hits.add('via-keepout')
    hits.update(n for c,n,g,q in drills if box.Contains(q) and (h.Collide(g,252000) or c!=code and sh.Collide(g,250000)))
    hits.update(n for l in ls for c,n,g,bb in geometry[l] if c!=code and box.Intersects(bb) and (sh.Collide(g,202000) or h.Collide(g,250000)))
    if hits:
        blocked_sites[pt]=sorted(hits);cause.update(hits);continue
    sites[pt]=(sum(math.dist(a,z) for a,z in zip(path,path[1:])),sh,o)
for i,a in enumerate(sites):
    for z in list(sites)[:i]:
        if 600000<=math.dist(a,z)<=1050000:pairs.append((a,z))
movables={'C412','R410','R411','C481','C434','C425','C445'}
# Copper used by already closed branches is counted as a real rerouting cost.
counts=Counter();options={};net_lookup={owner(o):o.GetNetname() for o in near}
for angle in (0,90,180,270):
    cap.SetOrientationDegrees(angle)
    for x in range(605,684,2):
        for y in range(72,142,2):
            xy=(x*100000,y*100000);cap.SetPosition(v(xy));c=cap.GetCourtyard(side)
            blocked=frozenset(n for n,shape in courts if c.Collide(shape,100000))
            if blocked-movables or len(blocked)>2:continue
            counts['fixed_clear']+=1
            if any(c.Collide(h,50000) for _,n,h,_ in drills if n.startswith('U4')):continue
            pins=impacts(power,side,oldg)|impacts(ground,side,oldg)
            # Connections to the old C425 lands are superseded simultaneously.
            permitted=blocked|oldg
            conflicts=(pins-permitted)
            if len(conflicts)>4:continue
            center=tuple(power.GetPosition());allowed={}
            g=ground.GetEffectiveShape(side);land=power.GetEffectiveShape(side)
            for pt,(distance,sh,o) in sites.items():
                if distance+math.dist(center,pt)>4100000 or sh.Collide(g,202000):continue
                if sh.Collide(land,75000) and not all(power.HitTest(v((pt[0]+round(275000*math.cos(i*math.tau/24)),pt[1]+round(275000*math.sin(i*math.tau/24))))) for i in range(24)):continue
                seg=trace(center,pt,500000,code,side)
                if seg.GetEffectiveShape(side).Collide(g,202000):continue
                allowed[pt]=impacts(seg,side,permitted)|conflicts
            for a,z in pairs:
                if a not in allowed or z not in allowed:continue
                extra=allowed[a]|allowed[z]
                if len(extra)>4:continue
                ids=tuple(sorted(extra));key=(tuple(sorted(blocked)),ids, angle, xy[0]//400000,xy[1]//400000)
                score=sum(math.dist(pt,center)+sites[pt][0] for pt in (a,z))+math.dist(xy,tuple(origin))*.1
                if key not in options or score<options[key][0]:options[key]=(score,dict(xy_nm=xy,angle=angle,source_vias_nm=[a,z],body_moves=sorted(blocked),copper_conflicts=[(k,net_lookup.get(k)) for k in ids],maximum_branch_mm=max(math.dist(pt,center)+sites[pt][0] for pt in (a,z))/1e6))
rows=sorted((val[1] for val in options.values()),key=lambda r:(len(r['copper_conflicts'])+len(r['body_moves']),len(r['copper_conflicts']),r['maximum_branch_mm']))
res=dict(parent_sha256=report['board_sha256'],legal_source_sites=len(sites),legal_source_pairs=len(pairs),counts=counts,alternatives=len(rows),ranked=rows[:140],blocked_sites={str(k):v for k,v in blocked_sites.items()},source_obstructions=[(k,net_lookup.get(k),c) for k,c in cause.most_common()])
(folder/('rear-input-before-feedback.json' if reserve else 'rear-input-conflicts.json')).write_text(json.dumps(res,indent=2)+'\n')
print(len(sites),len(pairs),counts,len(rows),rows[:2],flush=True);os._exit(0)
