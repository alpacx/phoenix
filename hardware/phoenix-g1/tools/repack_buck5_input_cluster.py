"""Repack C425/C434/C481 with explicit paired input vias and separate ground connections."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pcb_power_leg import route_leg
import pcbnew as p
from pcb_bounds import inflated_box
from drc_regression import introduced
from audit_mount_component_reservations import screen

runs=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel/runs'
mobile='--move-buck4-vias' in sys.argv
source=runs/'pmic-five-stage-secondary-0';dest=runs/('pmic-five-stage-repack-mobile-0' if mobile else 'pmic-five-stage-repack-0');dest.mkdir(exist_ok=True)
fn='phy-joint.kicad_pcb';prior=json.loads((source/'output-legs.json').read_text());analysis=json.loads((source/'rear-input-before-feedback.json').read_text())
assert prior['board_sha256']==analysis['parent_sha256']==hashlib.sha256((source/fn).read_bytes()).hexdigest()
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source/name,dest/name)
b=p.LoadBoard(str(source/fn));b.BuildConnectivity();v=lambda xy:p.VECTOR2I(*xy)
def pad(ref,num):return b.FindFootprintByReference(ref).FindPadByNumber(num)
def uv(o):return o.m_Uuid.AsString()
def ids(board):return {uv(t) for t in board.GetTracks()}
start=p.LoadBoard(str(runs/'pmic-five-stage-sense-0'/fn));feedback=p.LoadBoard(str(runs/'pmic-five-stage-feedback-0'/fn))
unpick={uv(t) for t in feedback.GetTracks() if t.GetNetname()=='+1V8_SYS' and uv(t) not in ids(start)}
assert unpick
remove=unpick|{'490585d8-b8ee-482d-8fcf-eef4b7e2ec95','49a50d01-079a-4607-95c7-50da592500de','4f82c973-bd2e-4f21-b66d-021a90ab2468','dc4123ab-539b-4176-81d4-58ed0c0e54fb'}
parts={key:b.FindFootprintByReference(key) for key in ('C425','C434','C481')}
for key,nos in [('C425',['1']),('C481',['1','2'])]:
    for n in nos:
        q=pad(key,n);members=b.GetConnectivity().GetConnectedItems(q)
        assert not any(isinstance(o,p.PAD) and uv(o)!=uv(q) for o in members)
        remove.update(uv(o) for o in members if isinstance(o,p.PCB_TRACK))
rails={r['role']:r for r in prior['rows'] if r['stage']==4}
old_segments=set()
for target,ix in [('LC output',1),('C43 ground',0)]:
    for sides in rails[target]['branches_nm']:
        for u,w in zip(sides[ix],sides[ix][1:]):
            if u!=w:old_segments.add(frozenset((tuple(u),tuple(w))))
for t in b.GetTracks():
    if t.GetLayer()==p.B_Cu and not isinstance(t,p.PCB_VIA) and frozenset((tuple(t.GetStart()),tuple(t.GetEnd()))) in old_segments:remove.add(uv(t))
if mobile:
    centers={tuple(x) for x in rails['LC output']['via_centres_nm']}
    for t in b.GetTracks():
        if isinstance(t,p.PCB_VIA) and tuple(t.GetPosition()) in centers:remove.add(uv(t))
    front_segments={frozenset((tuple(a),tuple(z))) for sides in rails['LC output']['branches_nm'] for a,z in zip(sides[0],sides[0][1:]) if a!=z}
    for t in b.GetTracks():
        if t.GetLayer()==p.F_Cu and not isinstance(t,p.PCB_VIA) and t.GetNetname()=='VDD_NPU' and frozenset((tuple(t.GetStart()),tuple(t.GetEnd()))) in front_segments:remove.add(uv(t))
removed=[o for o in b.GetTracks() if uv(o) in remove]
assert len(removed)==len(remove)
for o in removed:b.Remove(o)
b.BuildConnectivity()
template=next(r for r in prior['rows'] if r['stage']==5 and r['role']=='PMIC to input bypass')
source_paths={tuple(r['pt_nm']):r['route_nm'] for r in template['source_map']}
pos=lambda q:tuple(q.GetPosition())
def wire(a,z,net,width,side=p.B_Cu):
    t=p.PCB_TRACK(b);t.SetNetCode(net);t.SetLayer(side);t.SetWidth(width);t.SetStart(v(a));t.SetEnd(v(z));return t
def via(at,net):
    o=p.PCB_VIA(b);o.SetViaType(p.VIATYPE_THROUGH);o.SetLayerPair(p.F_Cu,p.B_Cu);o.SetDrill(200000);o.SetWidth(450000);o.SetNetCode(net);o.SetPosition(v(at));return o
reference=v((67000000,9000000))
held=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference() not in parts for q in f.Pads()] if inflated_box(o,9500000).Contains(reference)]
geoms=[(o.GetNetCode(),o.GetEffectiveShape(p.B_Cu),o.GetBoundingBox()) for o in held if o.IsOnLayer(p.B_Cu)]
holes=[(o.GetNetCode(),o.GetEffectiveHoleShape(),o.GetPosition()) for o in held if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
physical=[o.GetEffectiveHoleShape() for o in held if isinstance(o,p.PAD) and o.GetDrillSize().x]
courts=[f.GetCourtyard(p.B_Cu) for f in b.GetFootprints() if f.GetReference() not in parts and f.GetLayer()==p.B_Cu and inflated_box(f,9500000).Contains(reference)]
zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.IsOnLayer(p.B_Cu) and z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
gndset={uv(t) for t in b.GetConnectivity().GetConnectedItems(pad('U4','69'))}
grounds={pos(o) for o in held if uv(o) in gndset and (isinstance(o,p.PCB_VIA) and o.GetDrillValue()>=200000 or isinstance(o,p.PAD) and o.GetDrillSize().x>=200000)}
def clean(o,other):
    s=o.GetEffectiveShape(p.B_Cu);bb=inflated_box(o,400000);net=o.GetNetCode()
    return not any(c!=net and bb.Intersects(box) and s.Collide(g,202000) for c,g,box in geoms) and not any(c!=net and bb.Contains(at) and s.Collide(h,250000) for c,h,at in holes) and not any(net!=t.GetNetCode() and s.Collide(t.GetEffectiveShape(p.B_Cu),202000) for t in other) and not any(s.Collide(k,0) for k in zones)
def clear_body(part,neighbors,other):
    c=part.GetCourtyard(p.B_Cu)
    return not any(c.Collide(g,100000) for g in courts) and not any(c.Collide(q.GetCourtyard(p.B_Cu),100000) for q in neighbors) and not any(c.Collide(h,50000) for h in physical) and all(clean(q,other) for q in part.Pads())
def branch(q,z,width,other,limit,straight=False):
    a=pos(q);dx,dy=z[0]-a[0],z[1]-a[1];d=min(abs(dx),abs(dy));xx=int(math.copysign(d,dx));yy=int(math.copysign(d,dy))
    if a==z:return []
    for pts in ((a,z),(a,(a[0]+xx,a[1]+yy),z),(a,(z[0]-xx,z[1]-yy),z)) if straight else ((a,(a[0]+xx,a[1]+yy),z),(a,(z[0]-xx,z[1]-yy),z)):
        parts=[wire(u,w,q.GetNetCode(),width) for u,w in zip(pts,pts[1:]) if u!=w]
        if sum(t.GetLength() for t in parts)<=limit and all(clean(t,other) for t in parts):return parts
    return None
def grounding(q,other,two=True):
    tree=[]
    for x in sorted(grounds,key=lambda at:math.dist(pos(q),at)):
        if math.dist(pos(q),x)>2500000:break
        path=branch(q,x,500000 if two else 300000,other,2700000)
        if path is None:continue
        if not two:return path
        for prev,earlier in tree:
            if math.dist(prev,x)>=600000:return earlier+path
        tree.append((x,path))
    return None
def store(f,xy,angle):f.SetPosition(v(xy));f.SetOrientationDegrees(angle)
def courtpose(part,xrange,yrange,neighbors,other):
    for ang in (0,90,180,270):
        for x in xrange:
            for y in yrange:
                xy=(x*100000,y*100000);store(part,xy,ang)
                if clear_body(part,neighbors,other):yield xy,ang
def positive_lands_ok(q,centers):
    shape=q.GetEffectiveShape(p.B_Cu);code=q.GetNetCode()
    for at in centers:
        o=via(at,code)
        if o.GetEffectiveShape(p.B_Cu).Collide(shape,75000) and not all(q.HitTest(v((at[0]+round(275000*math.cos(k*math.tau/24)),at[1]+round(275000*math.sin(k*math.tau/24))))) for k in range(24)):return False
    return True
def inspect():
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dest/fn),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dest/'drc.json'),str(dest/fn)],capture_output=True,check=True)
    return introduced(json.loads((source/'drc.json').read_text()),json.loads((dest/'drc.json').read_text()))
counts=Counter();selected=None;drc_rejections=[]
for row in analysis['ranked']:
    if row['copper_conflicts'] or set(row['body_moves'])-parts.keys():continue
    store(parts['C425'],row['xy_nm'],row['angle']);q=pad('C425','1');g=pad('C425','2');sites=[tuple(pt) for pt in row['source_vias_nm']]
    if not clear_body(parts['C425'],[],[]) or not positive_lands_ok(q,sites):continue
    positive=[];front=[];vs=[]
    for pt in sites:
        w=branch(q,pt,500000,[g],4100000,True)
        if w is None:break
        positive.extend(w);vs.append(via(pt,q.GetNetCode()));path=source_paths[pt]
        front.extend(wire(u,w,q.GetNetCode(),500000,p.F_Cu) for u,w in zip(path,path[1:]) if u!=w)
    else:
        counts['c425_supply']+=1;return5=grounding(g,[q]+positive+vs)
        if return5 is None:continue
        counts['c425_complete']+=1;fifth=[q,g]+vs+positive+return5
        c4=parts['C434'];q4=pad('C434','1');g4=pad('C434','2');power4=list(map(tuple,rails['LC output']['via_centres_nm']));ground4=list(map(tuple,rails['C43 ground']['via_centres_nm']))
        if mobile:
            c8=parts['C481'];q8=pad('C481','1');g8=pad('C481','2')
            choices8=[]
            for xy8,ang8 in courtpose(c8,range(630,705,2),range(49,110,2),[parts['C425']],fifth):
                feed8=branch(q8,pos(q),300000,fifth+[g8],2700000)
                if feed8 is None:continue
                back8=grounding(g8,fifth+[q8]+feed8,False)
                if back8 is None:continue
                choices8.append((sum(t.GetLength() for t in feed8+back8),xy8,ang8,feed8,back8))
            counts['c481_complete']+=len(choices8)
            for _,xy8,ang8,feed8,back8 in sorted(choices8,key=lambda v:v[0]):
                store(c8,xy8,ang8)
                copper=front+vs+positive+return5+feed8+back8
                unique={}
                for t in copper:
                    k=(t.GetNetCode(),t.GetLayer(),t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth(),frozenset((tuple(t.GetStart()),tuple(t.GetEnd()))))
                    unique[k]=t
                for t in unique.values():b.Add(t)
                pre=ids(b)
                options4=[]
                for xy4,ang4 in courtpose(c4,range(641,724,2),range(63,123,2),[parts['C425'],c8],fifth+[q8,g8]+feed8+back8):
                    dist=math.dist(pos(q4),pos(pad('L404','2')))
                    if dist<=3300000:options4.append((dist,xy4,ang4))
                for _,xy4,ang4 in sorted(options4):
                    counts['c434_body']+=1;store(c4,xy4,ang4)
                    out4=route_leg(b,q4.GetNetname(),pos(pad('L404','2')),p.F_Cu,pos(q4),p.B_Cu,600000,3.6,True)
                    if not out4['connected']:continue
                    counts['c434_both_positive']+=1
                    ret4=route_leg(b,'GND',pos(g4),p.B_Cu,pos(g4),p.In1_Cu,500000,3.2,True)
                    if ret4['connected'] and not screen(b):
                        counts['three_complete']+=1;delta=inspect()
                        if not delta:
                            selected=dict(c425=[row['xy_nm'],row['angle']],c434=[xy4,ang4],c481=[xy8,ang8],paired_vias_nm=sites,removed_copper=sorted(remove),fourth_output=out4,fourth_return=ret4);break
                        drc_rejections.append(dict(c434=xy4,c481=xy8,delta=delta))
                    additions=[t for t in b.GetTracks() if uv(t) not in pre]
                    for t in additions:b.Remove(t)
                if selected:break
                for t in unique.values():b.Remove(t)
            if selected:break
            continue
        for xy4,ang4 in courtpose(c4,range(651,720),range(66,115),[parts['C425']],fifth):
            counts['c434_body']+=1
            if not positive_lands_ok(q4,power4) or not positive_lands_ok(g4,ground4):continue
            counts['c434_barrel_land']+=1
            w4=[branch(q4,z,600000,fifth+[g4],3100000) for z in power4]
            if None in w4:continue
            counts['c434_both_positive']+=1
            load4=w4[0]+w4[1];gr4=[branch(g4,z,500000,fifth+[q4]+load4,2600000) for z in ground4]
            if None in gr4:continue
            counts['c434_complete']+=1
            fourth=[q4,g4]+load4+gr4[0]+gr4[1];c8=parts['C481'];q8=pad('C481','1');g8=pad('C481','2')
            for xy8,ang8 in courtpose(c8,range(630,702,2),range(50,107,2),[parts['C425'],c4],fifth+fourth):
                feed8=branch(q8,pos(q),300000,fifth+fourth+[g8],2700000)
                if feed8 is None:continue
                back8=grounding(g8,fifth+fourth+[q8]+feed8,False)
                if back8 is None:continue
                counts['three_complete']+=1
                if screen(b):continue
                copper=vs+front+positive+return5+load4+gr4[0]+gr4[1]+feed8+back8;unique={};final=[]
                for t in copper:
                    key=(t.GetNetCode(),t.GetLayer(),t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth(),frozenset((tuple(t.GetStart()),tuple(t.GetEnd()))))
                    if key not in unique:unique[key]=t;final.append(t)
                for t in final:b.Add(t)
                delta=inspect()
                if not delta:
                    selected=dict(c425=[row['xy_nm'],row['angle']],c434=[xy4,ang4],c481=[xy8,ang8],paired_vias_nm=sites,removed_copper=sorted(remove));break
                drc_rejections.append(dict(c434=xy4,c481=xy8,delta=delta))
                for t in final:b.Remove(t)
            if selected:break
    if selected:break
details=dict(parent_sha256=prior['board_sha256'],counts=counts,selected=selected,drc_rejections=drc_rejections)
(dest/'cluster.json').write_text(json.dumps(details,indent=2)+'\n');print(counts,selected,len(drc_rejections),flush=True)
if selected:
    probe=p.LoadBoard(str(dest/fn));probe.BuildConnectivity()
    for left,right in [('U4.54','C425.1'),('U4.69','C425.2'),('L404.2','C434.1'),('U4.69','C434.2'),('C481.1','C425.1'),('C481.2','U4.69')]:
        ps=lambda s:probe.FindFootprintByReference(s.split('.')[0]).FindPadByNumber(s.split('.')[1])
        assert uv(ps(right)) in {uv(t) for t in probe.GetConnectivity().GetConnectedItems(ps(left))}
    prior['board_sha256']=hashlib.sha256((dest/fn).read_bytes()).hexdigest();prior['three_body_cluster']=details
    (dest/'output-legs.json').write_text(json.dumps(prior,indent=2)+'\n')
os._exit(0)
