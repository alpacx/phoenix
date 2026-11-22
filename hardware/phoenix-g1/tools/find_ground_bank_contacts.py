"""Attach remaining isolated package balls to a nearby accessible point of the actual ground copper."""
import hashlib,json,math,subprocess,shutil,heapq
from functools import lru_cache
from collections import defaultdict,Counter
from pathlib import Path
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';cp=json.loads((r/'layout-reused-ground-barrels.json').read_text());src=r/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();V=lambda pt:p.VECTOR2I(*pt);uid=lambda t:t.m_Uuid.AsString()
def pad(board,n):
 ref,num=n.split('.');return board.FindFootprintByReference(ref).FindPadByNumber(num)
def group(board,n):return {uid(o) for o in board.GetConnectivity().GetConnectedItems(pad(board,n))}
src_ground=group(b,'U4.69');allobj=[*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())];out=r/'runs/bga-ground-copper-contact';out.mkdir(exist_ok=True,parents=True);file=out/src.name
for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table');old=json.loads((src.parent/'drc.json').read_text())
def save():
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(file)],capture_output=True,check=True)
    return json.loads((out/'drc.json').read_text())
def compact(path):
    pts=[]
    for z in path:
        if len(pts)>1:
            a,q=pts[-2:]
            if (q[0]-a[0])*(z[1]-q[1])==(q[1]-a[1])*(z[0]-q[0]):pts.pop()
        pts.append(z)
    return pts
added=[];rows=[];joins=cp['remaining_minimum_joins']
for g in cp['open_nets']['GND']:
    if 'U4.69' in g:continue
    q=pad(b,g[0]);side=q.GetParentFootprint().GetLayer();code=q.GetNetCode();box=inflated_box(q,4500000);objs=[o for o in allobj if box.Intersects(o.GetBoundingBox())]
    zone=[z.Outline() for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
    index=defaultdict(list);goal=defaultdict(list);tilesz=500000
    def cells(bb):
        return ((i,j) for i in range(bb.GetLeft()//tilesz,bb.GetRight()//tilesz+1) for j in range(bb.GetTop()//tilesz,bb.GetBottom()//tilesz+1))
    for o in objs:
        if uid(o) in src_ground and o.IsOnLayer(side):
            for key in cells(o.GetBoundingBox()):goal[key].append((o,o.GetEffectiveShape(side)))
        if o.GetNetCode()==code:continue
        shape=o.GetEffectiveShape(side) if o.IsOnLayer(side) else None
        hole=o.GetEffectiveHoleShape() if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x else None
        if shape or hole:
            for key in cells(inflated_box(o,450000)):index[key].append((shape,hole))
    queue=[];cost={};parents={}
    for label in g:
        q0=pad(b,label);x,y=q0.GetPosition()
        for i in (-50000,0,50000):
         for j in (-50000,0,50000):
            pt=(x+i,y+j)
            if q0.HitTest(V(pt)):cost[pt]=0;heapq.heappush(queue,(0,pt))
    track=make(b,(0,0),(0,0),200000,code,side)
    @lru_cache(None)
    def clear(a,z):
        track.SetStart(V(a));track.SetEnd(V(z));sh=track.GetEffectiveShape(side)
        return not any((s and sh.Collide(s,202000)) or (h and sh.Collide(h,252000)) for s,h in index[(a[0]//tilesz,a[1]//tilesz)]) and not any(sh.Collide(k,0) for k in zone)
    route=None;used=None
    while queue:
        d,at=heapq.heappop(queue)
        if cost[at]!=d:continue
        match=next((o for o,s in goal[(at[0]//tilesz,at[1]//tilesz)] if s.Collide(V(at),0)),None)
        if match:
            path=[at]
            while path[-1] in parents:path.append(parents[path[-1]])
            route=compact(path[::-1]);used=uid(match);break
        for i,j in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
            z=at[0]+50000*i,at[1]+50000*j;nd=d+math.hypot(i,j)*50000
            if nd<=3500000 and nd<cost.get(z,math.inf) and clear(at,z):
                cost[z]=nd;parents[z]=at;heapq.heappush(queue,(nd,z))
    row=dict(pads=g,states=len(cost),path=route,terminal=used);rows.append(row)
    if not route or len(route)<2:continue
    copper=[make(b,a,z,200000,code,side) for a,z in zip(route,route[1:])]
    for t in copper:b.Add(t)
    db=save();fresh=p.LoadBoard(str(file));fresh.BuildConnectivity();delta=introduced(old,db)
    if delta or any(uid(pad(fresh,n)) not in group(fresh,'U4.69') for n in g) or len(db['unconnected_items'])>=joins:
        row['rejected']=delta
        for t in copper:b.Remove(t)
    else:added.extend(g);joins=len(db['unconnected_items'])
db=save();fresh=p.LoadBoard(str(file));fresh.BuildConnectivity()
report=dict(parent_sha256=cp['sha256'],added=added,rows=rows,remaining=len(db['unconnected_items']))
if added:
    gs=cp['open_nets']['GND'];main=next(x for x in gs if 'U4.69' in x);gid=group(fresh,'U4.69');joined=[x for x in gs if x!=main and uid(pad(fresh,x[0])) in gid]
    nets=cp['open_nets'].copy();nets['GND']=[x for x in gs if x not in joined and x!=main]+[sorted(main+[n for x in joined for n in x])]
    assert sum(len(x)-1 for x in nets.values())==report['remaining'] and not introduced(old,db)
    pairs=sorted({tuple(sorted(pair)) for pair in cp['verified_pairs']}|{tuple(sorted((n,'U4.69'))) for n in added});cache={}
    for a,z in pairs:
        if a not in cache:cache[a]=group(fresh,a)
        assert uid(pad(fresh,z)) in cache[a]
    state=dict(board=str(file.relative_to(r)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],verified_pairs=pairs,preservation=verify_preservation(p.LoadBoard(str(src)),fresh),open_nets=nets,remaining_minimum_joins=report['remaining'],new_drc=[],drc_counts=dict(Counter(x['type'] for x in db['violations'])),assembly_ready=False)
    (r/'layout-ground-copper-contact.json').write_text(json.dumps(state,indent=2)+'\n')
(r/'bga-ground-copper-contacts.json').write_text(json.dumps(report,indent=2)+'\n');print(added,report['remaining'])
