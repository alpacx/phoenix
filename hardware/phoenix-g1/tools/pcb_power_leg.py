"""Bounded same-surface and paired-via power paths for RK809 circuit studies."""
from functools import lru_cache
import heapq
import math
import pcbnew as p
from pcb_bounds import inflated_box

ls=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
def vec(pt):return p.VECTOR2I(*pt)
def make(b,a,z,w,code,l):
    t=p.PCB_TRACK(b);t.SetNetCode(code);t.SetLayer(l);t.SetWidth(w);t.SetStart(vec(a));t.SetEnd(vec(z));return t
def barrel(b,a,code,diameter=450000,drill=200000):
    v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(code);v.SetPosition(vec(a));v.SetWidth(diameter);v.SetDrill(drill);return v
def route_leg(b,net,a,la,z,lz,width,maxsum,passive_vip=False,shifted=False,reuse_supply_barrels=(), allow_supply_bends=False,via_diameter=450000,via_drill=200000,collect_supply_sites=False):
    ground_plane=lz in (p.In1_Cu,p.In4_Cu) and net=='GND'
    plane_polys=[q.GetFilledPolysList(lz) for q in b.Zones() if q.IsOnLayer(lz) and q.GetNetname()=='GND' and q.HasFilledPolysForLayer(lz)] if ground_plane else []
    code=b.FindNet(net).GetNetCode();near=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
    near=[o for o in near if inflated_box(o,round(maxsum*1e6)+1200000).Contains(vec(a))]
    foreign=[o for o in near if o.GetNetCode()!=code]
    holes=[(o.GetEffectiveHoleShape(),o.GetPosition()) for o in foreign if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    shapes={l:[(o.GetEffectiveShape(l),o.GetBoundingBox()) for o in foreign if o.IsOnLayer(l)] for l in ls}
    lands=[(q,q.GetEffectiveShape(q.GetParentFootprint().GetLayer())) for q in near if isinstance(q,p.PAD) and q.GetNetCode()==code]
    zones=list(b.Zones())+[q for f in b.GetFootprints() for q in f.Zones()]
    tracks_keep={l:[q.Outline() for q in zones if q.IsOnLayer(l) and q.GetIsRuleArea() and q.GetDoNotAllowTracks()] for l in ls}
    via_keep=[q.Outline() for q in zones if q.GetIsRuleArea() and q.GetDoNotAllowVias()]
    edges=[(o.GetEffectiveShape(p.Edge_Cuts),o.GetBoundingBox()) for o in list(b.GetDrawings())+[g for fp in b.GetFootprints() for g in fp.GraphicalItems()] if o.IsOnLayer(p.Edge_Cuts) and inflated_box(o,round(maxsum*1e6)+1200000).Contains(vec(a))]
    edge_box=b.GetBoardEdgesBoundingBox()
    edge_box.Inflate(-252000)
    def clear(o,l):
        if not edge_box.Contains(o.GetBoundingBox()):return False
        s=o.GetEffectiveShape(l);bb=inflated_box(o,370000)
        return not(any(bb.Intersects(box) and s.Collide(g,252000) for g,box in edges) or any(bb.Intersects(box) and s.Collide(g,202000) for g,box in shapes[l]) or any(bb.Contains(pos) and s.Collide(h,250000) for h,pos in holes) or any(s.Collide(k,0) for k in tracks_keep[l]))
    @lru_cache(None)
    def path(x,y,l):
        dx,dy=y[0]-x[0],y[1]-x[1];d=min(abs(dx),abs(dy));ex=int(math.copysign(d,dx));ey=int(math.copysign(d,dy))
        for pts in ((x,(x[0]+ex,x[1]+ey),y),(x,(y[0]-ex,y[1]-ey),y)):
            seg=[make(b,u,v,width,code,l) for u,v in zip(pts,pts[1:]) if u!=v]
            if seg and all(clear(t,l) for t in seg):return pts
        return None
    nearby_ground_anchors={}
    if ground_plane:
        b.BuildConnectivity()
        island={t.m_Uuid.AsString() for t in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('U4').FindPadByNumber('69'))}
        anchors={}
        for obj in near:
            if obj.GetNetCode()!=code or obj.m_Uuid.AsString() not in island or not obj.IsOnLayer(la):continue
            if isinstance(obj,p.PCB_VIA):
                if obj.GetViaType()!=p.VIATYPE_THROUGH or obj.GetDrillValue()<200000:continue
            elif not isinstance(obj,p.PAD) or min(obj.GetDrillSize().x,obj.GetDrillSize().y)<200000:continue
            pt=tuple(obj.GetPosition())
            if math.dist(a,pt)<=2300000:
                nearby_ground_anchors[pt]=obj.m_Uuid.AsString()
                trace=path(a,pt,la)
                if trace:anchors[pt]=(trace,obj.m_Uuid.AsString())
        scored=[]
        for i,pt in enumerate(anchors):
            for other in list(anchors)[:i]:
                if math.dist(pt,other)<500000:continue
                scored.append((math.dist(a,pt)+math.dist(a,other),pt,other))
        if scored:
            _,pt,other=min(scored);added=set()
            for at in (pt,other):
                trace,_=anchors[at]
                for u,v in zip(trace,trace[1:]):
                    if u!=v and (u,v) not in added:
                        b.Add(make(b,u,v,width,code,la));added.add((u,v))
            return dict(connected=True,kind='two existing ground barrels',anchors_nm=[pt,other],anchor_ids=[anchors[pt][1],anchors[other][1]])
    if la==lz:
        pts=path(a,z,la)
        if not pts:return dict(connected=False,kind='same surface')
        for x,y in zip(pts,pts[1:]):
            if x!=y:b.Add(make(b,x,y,width,code,la))
        return dict(connected=True,kind='same surface',path_nm=pts)
    def site(at):
        v=barrel(b,at,code,via_diameter,via_drill);s=v.GetEffectiveShape(p.F_Cu);h=v.GetEffectiveHoleShape();bb=inflated_box(v,370000)
        if any(isinstance(o,p.PCB_VIA) and math.dist(tuple(o.GetPosition()),at)<(o.GetDrillValue()/2+via_drill/2+250000) for o in near):return False
        if ground_plane and not any(pol.Contains(vec(at)) for pol in plane_polys):return False
        for pad0,land in lands:
            if not s.Collide(land,75000):continue
            if not passive_vip or pad0.GetParentFootprint().GetReference() not in {f'{stem}{n}' for n in range(1,6) for stem in ('L40','C42','C43')}:return False
            # Require annulus plus 50 um inside the original component land.
            if not all(pad0.HitTest(vec((at[0]+round((via_diameter/2+50000)*math.cos(i*math.tau/32)),at[1]+round((via_diameter/2+50000)*math.sin(i*math.tau/32))))) for i in range(32)):return False
        if any(s.Collide(k,0) for k in via_keep):return False
        for l in ls:
            if not clear(v,l) or any(bb.Intersects(box) and h.Collide(g,250000) for g,box in shapes[l]):return False
        return True
    # A ground barrel terminates at the plane. It has no same-length return
    # trace on that plane, even when callers use the same coordinates for a/z.
    search_margin=round(maxsum*1e6) if ground_plane else 1600000
    def route_lower_bound(at):
        return math.dist(a,at)+(0 if ground_plane else math.dist(at,z))
    xlo=int((min(a[0],z[0])-search_margin)//100000);xhi=int((max(a[0],z[0])+search_margin)//100000)
    ylo=int((min(a[1],z[1])-search_margin)//100000);yhi=int((max(a[1],z[1])+search_margin)//100000)
    choices=[]
    if passive_vip:
        # PCB lands lie on distinct sub-grid coordinates. Include the manufacturable
        # annulus locations relative to each actual land before scanning surrounding space.
        for pin0,_ in lands:
            pc=tuple(pin0.GetPosition())
            if pin0.GetParentFootprint().GetReference() not in {f'{stem}{n}' for n in range(1,6) for stem in ('L40','C42','C43')}:continue
            for dx in range(-6,7):
                for dy in range(-6,7):
                    at=pc[0]+dx*75000,pc[1]+dy*75000
                    score=route_lower_bound(at)
                    if score<=maxsum*1e6:choices.append((score,at))
    for x in range(xlo,xhi+1):
        for y in range(ylo,yhi+1):
            at=x*100000,y*100000;score=route_lower_bound(at)
            if score<=maxsum*1e6:choices.append((score,at))
    # Search once per surface for narrow, obstructed input paths, retaining each
    # predecessor. The transfer width stays constant around each obstruction.
    @lru_cache(None)
    def flood(origin,layer):
        grid=lambda pt:tuple(round(x/50000)*50000 for x in pt)
        st=grid(origin);parent0={};costs={}
        if st!=origin and not clear(make(b,origin,st,width,code,layer),layer):return costs,parent0
        if not clear(make(b,st,st,width,code,layer),layer):return costs,parent0
        costs[st]=math.dist(st,origin);pending=[(costs[st],st)]
        while pending:
            d,pt=heapq.heappop(pending)
            if costs[pt]!=d:continue
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
                nxt=(pt[0]+dx*50000,pt[1]+dy*50000);nd=d+50000*math.hypot(dx,dy)
                if nd>maxsum*1e6 or nd>=costs.get(nxt,math.inf):continue
                if clear(make(b,pt,nxt,width,code,layer),layer):
                    costs[nxt]=nd;parent0[nxt]=pt;heapq.heappush(pending,(nd,nxt))
        return costs,parent0
    def bend(origin,site,layer):
        direct=path(origin,site,layer)
        if direct or not shifted or (net!='+3V3_SYS' and not ground_plane and not allow_supply_bends):return direct
        dist,prev=flood(origin,layer);end=tuple(round(x/50000)*50000 for x in site)
        if end not in dist or not clear(make(b,end,site,width,code,layer),layer):return None
        nodes=[site,end]
        while nodes[-1] in prev:nodes.append(prev[nodes[-1]])
        nodes.append(origin);nodes.reverse();compact=[]
        for at in nodes:
            if compact and at==compact[-1]:continue
            if len(compact)>1:
                i,j=compact[-2:];d=(j[0]-i[0],j[1]-i[1]);e=(at[0]-j[0],at[1]-j[1])
                if d[0]*e[1]==d[1]*e[0] and d[0]*e[0]+d[1]*e[1]>0:compact.pop()
            compact.append(at)
        return compact
    if ground_plane and shifted and len(nearby_ground_anchors)>1:
        paths={pt:bend(a,pt,la) for pt in nearby_ground_anchors}
        usable=[pt for pt,pieces in paths.items() if pieces]
        for pt,other in sorted(((pt,other) for i,pt in enumerate(usable) for other in usable[:i] if math.dist(pt,other)>=500000),key=lambda pair:sum(sum(math.dist(i,j) for i,j in zip(paths[pt],paths[pt][1:])) for pt in pair)):
            added=set()
            for at in (pt,other):
                for u,v in zip(paths[at],paths[at][1:]):
                    key=tuple(sorted((u,v)))
                    if u!=v and key not in added:
                        b.Add(make(b,u,v,width,code,la));added.add(key)
            return dict(connected=True,kind='two existing ground barrels with bent access',anchors_nm=[pt,other],anchor_ids=[nearby_ground_anchors[pt],nearby_ground_anchors[other]],branches_nm=[paths[pt],paths[other]])
    valid={};legal_count=0;source_count=0;sink_count=0;source_paths={}
    existing_supply = {}
    for via in reuse_supply_barrels:
        if via.GetNetCode() != code or via.GetViaType() != p.VIATYPE_THROUGH or via.GetDrillValue()<via_drill or via.GetWidth(p.F_Cu)<via_diameter:
            continue
        at = tuple(via.GetPosition())
        if math.dist(a,at)>maxsum*1e6:
            continue
        branch=bend(a,at,la)
        if branch and sum(math.dist(x,y) for x,y in zip(branch,branch[1:]))<=maxsum*1e6:
            existing_supply[at]=(branch,via.m_Uuid.AsString())
    for score,at in sorted(set(choices)):
        if not site(at):continue
        legal_count+=1
        pa=bend(a,at,la);pz=(at,) if ground_plane else bend(z,at,lz)
        source_count+=int(bool(pa));sink_count+=int(bool(pz))
        if pa and (net=='+3V3_SYS' or allow_supply_bends):source_paths[at]=pa
        if collect_supply_sites:continue
        if pa and pz and sum(math.dist(u,v) for pts in (pa,pz) for u,v in zip(pts,pts[1:]))>maxsum*1e6:continue
        if not pa or not pz:continue
        for existing,(access,identifier) in existing_supply.items():
            distance=math.dist(existing,at)
            if not 600000<=distance<=1050000:
                continue
            b.Add(barrel(b,at,code,via_diameter,via_drill))
            added=set()
            for layer,points in ((la,access),(la,pa),(lz,pz)):
                for u,v in zip(points,points[1:]):
                    key=(layer,*sorted((u,v)))
                    if u!=v and key not in added:
                        b.Add(make(b,u,v,width,code,layer))
                        added.add(key)
            return dict(connected=True,kind='existing source barrel and new parallel barrel',existing_uuid=identifier,existing_nm=existing,new_nm=at,spacing_mm=distance/1e6,branches_nm=[access,pa,pz])
        for neighbor,previous in valid.items():
            distance=math.dist(at,neighbor)
            if not 600000<=distance<=1050000:continue
            for pt,paths in [(at,(pa,pz)),(neighbor,previous)]:
                via=barrel(b,pt,code,via_diameter,via_drill)
                if passive_vip and any(via.GetEffectiveShape(p.F_Cu).Collide(geom,0) for pad0,geom in lands):
                    via.SetCappingMode(p.CAPPING_MODE_CAPPED);via.SetFillingMode(p.FILLING_MODE_FILLED)
                b.Add(via)
                for l,xp in zip((la,lz),paths):
                    for x,y in zip(xp,xp[1:]):
                        if x!=y:b.Add(make(b,x,y,width,code,l))
            return dict(connected=True,kind='two through vias',via_centres_nm=[neighbor,at],diameter_mm=via_diameter/1e6,drill_mm=via_drill/1e6,spacing_mm=distance/1e6,branches_nm=[previous,(pa,pz)])
        valid[at]=(pa,pz)
    return dict(connected=False,kind='two through vias',legal_sites=legal_count,both_faces_reached=len(valid),source_reached=source_count,sink_reached=sink_count,source_map=[dict(pt_nm=xy,route_nm=route) for xy,route in sorted(source_paths.items())])
