"""Pack four complete buck component sets around RK809 and reserve the VDC corridor."""
from functools import lru_cache
from itertools import product
from pathlib import Path
from tempfile import gettempdir
import json
import math
from collections import Counter
import sys
import numpy as np
from shapely import contains_xy
from shapely.geometry import Point,Polygon,box as polygon_box
from shapely.strtree import STRtree
from shapely.ops import unary_union
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
native=json.loads((Path(gettempdir())/'phoenix-pmic-floorplan-native.json').read_text());fs=native['footprints']
active=json.loads((root/'layout-pmic-pwron-filter.json').read_text());assert active['sha256']==native['sha256']
# Every dimension and pin location originates in the actual footprint on disk.
five='--joint-buck5' in sys.argv
sets=[(f'L40{i}',f'C42{i}',f'C43{i}') for i in range(1,6 if five else 5)]
rotate='--rotate-pmic' in sys.argv
reuse5='--rigid-buck5' in sys.argv
rigid=('U4','L405','C425','C435') if reuse5 else ('U4',) if rotate else ('U4','C412') if five else ('U4','L405','C425','C435','C412')
cpu='--cpu-clearance' in sys.argv
moves=set(rigid).union(*sets)
repack='--local-bypass-bank' in sys.argv
bypass_refs=('C480','C481','C482','C483','C484','C485','R410','R411','C410') if repack else ('C482','C485')
if rotate:bypass_refs+=('C412',)
if cpu:moves.update((*bypass_refs,'L1001'))
side={'F.Cu':0,'B.Cu':1};step=.10
xg=np.arange(0,90,step)+step/2;yg=np.arange(0,40,step)+step/2
fixed={s:np.zeros((len(yg),len(xg)),dtype=np.uint16) for s in range(2)}
immutable_shapes={0:[],1:[]}
for ref,f in fs.items():
    if ref in moves:continue
    shapes=[Polygon(p).buffer(.1,join_style=2) for p in f['court'] if len(p)>=3]
    if not shapes:continue
    poly=unary_union(shapes);immutable_shapes[side[f['side']]].append(poly);a,b,c,d=poly.bounds
    xx=np.flatnonzero((xg>=a-.08)&(xg<=c+.08));yy=np.flatnonzero((yg>=b-.08)&(yg<=d+.08))
    if len(xx) and len(yy):fixed[side[f['side']]][np.ix_(yy,xx)]|=contains_xy(poly.buffer(.071),xg[xx][None,:],yg[yy][:,None]).astype('uint16')
for ref,f in fs.items():
    if ref=='U4':continue
    opposite=1-side[f['side']]
    for q in f['pads']:
        if min(q['drill'])<=0:continue
        hole=Point(*q['xy']).buffer(max(q['drill'])/2+.05)
        immutable_shapes[opposite].append(hole)
        fixed[opposite]|=contains_xy(hole.buffer(.071),xg[None,:],yg[:,None]).astype('uint16')
for z in native['keepouts']:
    if z['name'].endswith(' mechanical reservation'):
        a,b,c,d=z['bbox'];circle=Point((a+c)/2,(b+d)/2).buffer(max(c-a,d-b)/2+.025)
        for layer in (0,1):
            immutable_shapes[layer].append(circle)
            fixed[layer]|=contains_xy(circle.buffer(.071),xg[None,:],yg[:,None]).astype('uint16')
    if not z['footprints']:continue
    for outline in z['poly']:
        if len(outline)<3:continue
        poly=Polygon(outline).buffer(.08)
        for s in z['layers']:
            immutable_shapes[side[s]].append(poly)
            fixed[side[s]]|=contains_xy(poly,xg[None,:],yg[:,None]).astype('uint16')
tree={s:STRtree(shapes) for s,shapes in immutable_shapes.items()}
prefix={s:np.pad(a.cumsum(0).cumsum(1),((1,0),(1,0))).astype(np.int64) for s,a in fixed.items()}
def overlap(a,b):
    return a[0]==b[0] and a[1]<b[3]+.10 and b[1]<a[3]+.10 and a[2]<b[4]+.10 and b[2]<a[4]+.10
@lru_cache(None)
def legal(box):
    layer,a,b,c,d=box
    if a<.2 or b<.2 or c>89.8 or d>39.8:return False
    i,j=int(math.floor(a/step)),int(math.floor(b/step));k,l=int(math.ceil(c/step)),int(math.ceil(d/step));s=prefix[layer]
    return s[l,k]-s[j,k]-s[l,i]+s[j,i]==0 or not len(tree[layer].query(polygon_box(a,b,c,d),predicate="intersects"))
def rot(p,q):
    x,y=p
    return [(x,y),(-y,x),(-x,-y),(y,-x)][q%4]
def plus(a,b):return (a[0]+b[0],a[1]+b[1])
def minus(a,b):return (a[0]-b[0],a[1]-b[1])
def draw(ref,center,turn,layer):
    f=fs[ref];a,b,c,d=f['bounds'];w,h=c-a,d-b
    if turn%2:w,h=h,w
    x,y=center
    return (layer,round(x-w/2,3),round(y-h/2,3),round(x+w/2,3),round(y+h/2,3))
def pad(f,n):
    return next(p['xy'] for p in fs[f]['pads'] if p['pin']==n)
def placed_pad(ref,n,center,turn):return plus(center,rot(minus(pad(ref,n),fs[ref]['xy']),turn))
reasons=Counter()
def fail(msg):
    reasons[msg]+=1;return [],{}
def configs(chassis,turn,shift_cpu=(0,0)):
    origin=fs['U4']['xy']
    transform=lambda x:plus(chassis,rot(minus(x,origin),turn))
    occupied=[];poses={}
    if cpu:
        f=fs['L1001'];center=plus(f['xy'],shift_cpu);r=draw('L1001',center,0,0)
        if not legal(r):return fail('CPU inductor clearance')
        occupied.append(r);poses['L1001']=(center,0,0)
    for ref in rigid:
        f=fs[ref];xy=transform(f['xy']);s=side[f['side']];r=draw(ref,xy,turn,s)
        if not legal(r) or (cpu and overlap(r,occupied[0])):return fail('rigid '+ref)
        occupied.append(r);poses[ref]=(xy,turn,s)
    for pin in fs['U4']['pads']:
        if min(pin['drill'])>0:
            x,y=transform(pin['xy']);r=max(pin['drill'])/2+.05
            occupied.append((1,x-r,y-r,x+r,y+r))
    # Keep out the quiet VDC side immediately beyond pin 61. Moving BUCK5 would be a separate topology.
    xp,yp=transform(pad('U4','61'));nx,ny=rot((0,-1),turn)
    vdc=(0,min(xp,xp+nx*1.2)-.15,min(yp,yp+ny*1.2)-.15,max(xp,xp+nx*1.2)+.15,max(yp,yp+ny*1.2)+.15)
    groups=[]
    for idx,(L,I,O) in enumerate(sets):
        sk=('12','9','25','65','53')[idx];ik=('11','10','24','66','54')[idx]
        sw=transform(pad('U4',sk));vin=transform(pad('U4',ik))
        nx,ny=rot(((-1,0),(-1,0),(0,1),(0,-1),(0,-1))[idx],turn);tx,ty=-ny,nx
        def local(p,r,t):return (p[0]+nx*r+tx*t,p[1]+ny*r+ty*t)
        def options(ref,target,radials,tangents,faces):
            result=[]
            for r,t,angle,layer in product(radials,tangents,range(4),faces):
                xy=local(target,r,t);box=draw(ref,xy,angle,layer)
                if not legal(box) or any(overlap(box,q) for q in occupied+[vdc]):continue
                point=placed_pad(ref,'1',xy,angle);distance=math.dist(point,target)
                result.append((distance,ref,xy,angle,layer,box))
            return sorted(result,key=lambda o:o[0])
        if idx==2:
            ls=options(L,sw,[x/10 for x in range(18,43,2)],[x/10 for x in range(-38,39,2)],(0,))
        elif idx in (0,1):
            ls=options(L,sw,(2.0,2.3,2.6,2.9,3.2,3.5,3.8,4.1),[v/10 for v in range(-38,39,3)],(0,))
        else:
            ls=options(L,sw,(2.3,2.9,3.5,4.1),(-3.2,-2.4,-1.6,-.8,0,.8,1.6,2.4,3.2),(0,))
        ins=options(I,vin,(-2.4,-1.8,-1.2,-.6,0,.6,1.2,1.8,2.4,3.0),(-3,-2,-1,0,1,2,3),(1,0))
        if not ls or not ins:return fail('stage '+str(idx+1)+' components '+str((bool(ls),bool(ins))))
        g=[]
        if idx in (0,1):
            # Adjacent SW1/SW2 should fan away from each other rather than occupy the same corridor.
            rank=lambda o:o[0]+max(0,((o[2][0]-sw[0])*tx+(o[2][1]-sw[1])*ty)*(1 if idx==0 else -1))*2
            ls=sorted(ls,key=rank)
        for length,l,xy,angle,layer,box in ls[:65]:
            if length>(math.dist(pad('U4','53'),pad('L405','1')) if idx==4 else 3.3):continue
            lout=placed_pad(L,'2',xy,angle)
            outs=options(O,lout,(-2.4,-1.8,-1.2,-.6,0,.6,1.2,1.8,2.4,2.7,3,3.15,3.3,3.6),(-2.4,-1.6,-.8,0,.8,1.6,2.4),(0,1))
            for o in [x for x in outs if x[0]<=2.5 and not overlap(x[-1],box)][:30]:
                for i in [x for x in ins if x[0]<=3 and not overlap(x[-1],box) and not overlap(x[-1],o[-1])][:50]:
                    score=length+o[0]+i[0]+.8*(o[4]==1)
                    if idx in (0,1):score+=max(0,((xy[0]-sw[0])*tx+(xy[1]-sw[1])*ty)*(1 if idx==0 else -1))*3
                    g.append((score,[(l,xy,angle,layer,box),(i[1],i[2],i[3],i[4],i[5]),(o[1],o[2],o[3],o[4],o[5])]))
        if not g:
            if '--fixed' in sys.argv:print(idx+1,'closest L',ls[:1],'closest Cin',ins[:1],flush=True)
            return fail('stage '+str(idx+1)+' unconnected component set')
        g.sort(key=lambda row:row[0]);groups.append(g)
    for i,g in enumerate(groups):
        distinct={}
        for score,row in g:
            key=tuple(o[-1] for o in row)
            if key not in distinct:distinct[key]=(score,row)
        groups[i]=list(distinct.values())
    # Treat each pre-screened stage or bypass as one candidate set. Packed compatibility
    # tables allow forward checking before traversing candidate combinations.
    original_stages=len(sets)
    def diverse(g):
        buckets={}
        for option in g:
            _,row=option
            # Keep trials on opposite sides of an adjacent switch terminal.
            sense=tuple((round(r[1][0]/1.5),round(r[1][1]/1.5),r[3]) for r in row)
            buckets.setdefault(sense,[]).append(option)
        out=[]
        for rank in range(3):
            for vals in buckets.values():
                if len(vals)>rank:out.append(vals[rank])
        return out[:1200]
    groups=[diverse(g) for g in groups]
    if cpu:
        for ref in bypass_refs:
            g=[];unique=set()
            change_face=ref in ('C482','C485') and '--flex-input' in sys.argv
            pitch=.25 if change_face else .5; span=8 if change_face else 4
            for dx,dy in sorted(product(range(-span,span+1),repeat=2),key=lambda q:abs(q[0])+abs(q[1])):
                xy=plus(transform(fs[ref]['xy']),(pitch*dx,pitch*dy))
                for angle,side_id in product(range(4),((1,0) if change_face else (side[fs[ref]['side']],))):
                    if ref=='C412' and math.dist(placed_pad(ref,'1',xy,angle),transform(pad('U4','52')))>2.0:continue
                    if change_face and math.dist(placed_pad(ref,'1',xy,angle),transform(pad('U4','30' if ref=='C482' else '22')))>2.5:continue
                    r=draw(ref,xy,angle,side_id)
                    if r in unique or not legal(r) or any(overlap(r,a) for a in occupied):continue
                    unique.add(r);g.append((abs(dx)+abs(dy),[(ref,xy,angle,side_id,r)]))
            if not g:return fail('no remaining location '+ref)
            groups.append(g)
    if '--diagnose' in sys.argv:print('stage and local options',list(map(len,groups)),flush=True)
    rectangles=[np.array([[f[-1] for f in row] for score,row in g]) for g in groups]
    fits={}
    for i,A in enumerate(rectangles):
        for j,B in enumerate(rectangles[:i]):
            matrix=np.ones((len(A),len(B)),dtype=bool)
            for ai in range(A.shape[1]):
                a=A[:,ai,:][:,None,:]
                for bi in range(B.shape[1]):
                    b=B[:,bi,:][None,:,:]
                    matrix&=~((a[:,:,0]==b[:,:,0])&(a[:,:,1]<b[:,:,3]+.1)&(b[:,:,1]<a[:,:,3]+.1)&(a[:,:,2]<b[:,:,4]+.1)&(b[:,:,2]<a[:,:,4]+.1))
            for u,v,m in [(i,j,matrix),(j,i,matrix.T)]:
                fits[u,v]=[int.from_bytes(bytes(r),'little') for r in np.packbits(m,axis=1,bitorder='little')]
    visits=0
    def fit(available,chosen):
        nonlocal visits
        visits+=1
        if not available:return chosen
        if visits>100000:return None
        stage=min(available,key=lambda i:(i>=original_stages,available[i].bit_count()))
        mask=available[stage]
        while mask:
            bit=mask&-mask;select=bit.bit_length()-1;mask-=bit
            remain={i:old&fits[stage,i][select] for i,old in available.items() if i!=stage}
            if all(remain.values()):
                success=fit(remain,chosen+[(stage,select)])
                if success:return success
        return None
    allowed={i:(1<<len(g))-1 for i,g in enumerate(groups)}
    changed=True
    while changed:
        changed=False
        for i,mask in list(allowed.items()):
            good=0
            while mask:
                bit=mask&-mask;mask-=bit;idx=bit.bit_length()-1
                if all(j==i or (fits[i,j][idx]&a) for j,a in allowed.items()):good|=bit
            if not good:
                other=[j+1 for j,m in allowed.items() if i!=j and not any(fits[i,j][k]&m for k in range(len(groups[i])))]
                return fail('arc clash at '+(str(i+1) if i<original_stages else bypass_refs[i-original_stages])+' versus '+str(other))
            if good!=allowed[i]:allowed[i]=good;changed=True
    solution=fit(allowed,[])
    if not solution and '--exact' in sys.argv:
        from pmic_pose_milp import choose
        solution,diagnosis=choose(groups,allowed)
        if not solution and '--core' in sys.argv:
            subset=list(range(original_stages))
            def possible(ids):
                subg=[groups[i] for i in ids]
                return choose(subg,{j:(1<<len(g))-1 for j,g in enumerate(subg)})[0] is not None
            if possible(subset):subset=list(range(len(groups)))
            for i in list(subset):
                rest=[j for j in subset if i!=j]
                if not possible(rest):subset=rest
            print('irreducible footprint-group labels',[(i+1 if i<original_stages else bypass_refs[i-original_stages]) for i in subset],flush=True)
        print('native footprint choices:',diagnosis,flush=True)
    if not solution:
        if '--diagnose' in sys.argv:
            results=[]
            for drop in range(len(groups)):
                visits=0
                if fit({i:(1<<len(g))-1 for i,g in enumerate(groups) if i!=drop},[]):results.append(drop+1 if drop<original_stages else bypass_refs[drop-original_stages])
            print('single relaxations',results,flush=True)
        return fail(diagnosis if '--exact' in sys.argv else 'packing visit bound' if visits>100000 else 'no mutually compatible placements within retained options')
    chosen=[]
    for idx,opt in solution:
        score,row=groups[idx][opt]
        if idx<original_stages:chosen.append((idx+1,score,row))
        else:
            for ref,xy,q,layer,r in row:poses[ref]=(xy,q,layer)
    return chosen,poses

states=[];solutions=[]
shifts=[(0,0)] if '--fixed' in sys.argv else sorted(product(range(-8,9,2),range(-4,11,2)),key=lambda q:abs(q[0])+abs(q[1]))
if '--fixed' not in sys.argv:
    nearby=list(product([i/4 for i in range(-8,9)],[i/4 for i in range(-4,13)]))
    coarse=list(product(range(-23,19,2),range(-5,23,2)))
    shifts=sorted(set(nearby+coarse+shifts),key=lambda q:abs(q[0])+abs(q[1]))
if cpu:shifts=[(0,0)]
if '--translate-pmic' in sys.argv:
    shifts=[(-.5,0),(-1,0),(-1.5,0),(.5,0),(1,0),(-.5,.5),(-1,.5),(0,.5),(0,-.5),(-.5,-.5),(1,.5),(-1,-.5),(-.5,1),(-1,1),(0,1)]

if '--only-current' in sys.argv:shifts=[(0,0)]
rotate='--rotate-pmic' in sys.argv
if rotate:shifts=[(0,0),(-.25,0),(.25,0),(0,.15),(0,-.15),(-.4,.1)]
for shift in shifts:
    for angle,shift_cpu in product(((1,2,3) if rotate else (0,) if '--fixed' in sys.argv or cpu else (0,1,2,3)),([(dx,dy) for dx in (0,.05,.15,.25,.5,.75,1,-.25,-.5) for dy in (0,.05,.15,.25,.5,.75)] if cpu else [(0,0)])):
        if '--only-current' in sys.argv and (angle!=0 or shift_cpu!=(0,0)):continue
        if ('--translate-pmic' in sys.argv or rotate) and shift_cpu!=(0,0):continue
        center=plus(fs['U4']['xy'],shift);rows,rig=configs(center,angle,shift_cpu)
        states.append(dict(center_mm=center,turn=angle,cpu_shift_mm=shift_cpu,complete=bool(rows)))
        if rows:
            solutions.append(dict(center_mm=center,turn=angle,rigid=rig,groups=rows))
            if len(solutions)>=2:break
    if len(solutions)>=2:break
out=dict(source_sha256=native['sha256'],adopted=False,model='courtyard floorplan only; input vias, current delivery, GND, feedback and external joins require copper reconstruction',failure_modes=dict(reasons),states=states,solutions=solutions)
(root/('pmic-rotated-rigid-fifth.json' if reuse5 else 'pmic-five-stage-rotated.json' if rotate else 'pmic-five-stage-flex-input.json' if '--flex-input' in sys.argv else 'pmic-five-stage-translated.json' if '--translate-pmic' in sys.argv else 'pmic-five-stage-local-bank.json' if repack else 'pmic-five-stage-joint-bypass.json' if five else 'pmic-four-stage-joint-bypass.json' if cpu else 'pmic-four-stage-fixed.json' if '--fixed' in sys.argv else 'pmic-four-stage-floorplan.json')).write_text(json.dumps(out,indent=2)+'\n')
print(len(states),len(solutions),reasons,flush=True)
