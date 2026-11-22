"""Connect existing control-net copper on different layers through a shared legal off-land via."""
from collections import defaultdict
from pathlib import Path
from functools import lru_cache
import hashlib,json,math,heapq,sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import barrel,make,ls
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';cp=json.loads((r/('layout-rgmii-short-source-clock.json' if '--current-mac' in sys.argv else 'layout-npu-c434-paired-load.json')).read_text());src=r/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();V=lambda pt:p.VECTOR2I(*pt);uid=lambda o:o.m_Uuid.AsString()
def pad(name):
    ref,num=name.split('.');return b.FindFootprintByReference(ref).FindPadByNumber(num)
allobj=[*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())];objects={uid(o):o for o in allobj}
keep=[z for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea()]
index=defaultdict(list);tile=500000;grid=100000
def tiles(bb):return ((i,j) for i in range(bb.GetLeft()//tile,bb.GetRight()//tile+1) for j in range(bb.GetTop()//tile,bb.GetBottom()//tile+1))
for o in allobj:
    code=o.GetNetCode();geom={l:o.GetEffectiveShape(l) for l in ls if o.IsOnLayer(l)}
    hole=o.GetEffectiveHoleShape() if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x else None
    record=(code,geom,hole,isinstance(o,p.PAD),uid(o))
    for k in tiles(inflated_box(o,650000)):index[k].append(record)
ground={uid(t) for t in b.GetConnectivity().GetConnectedItems(pad('U4.69'))};gnd_positions=[tuple(t.GetPosition()) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and uid(t) in ground]
bounds=b.GetBoardEdgesBoundingBox();bounds.Inflate(-400000)
layers=[p.F_Cu,p.In2_Cu,p.In3_Cu,p.B_Cu]
dual='--two-launches' in sys.argv
pmic_toe='--pmic-toe' in sys.argv
nets=[n for n in sys.argv[1:] if not n.startswith('--')] or ['PHY_CFG_EXT','RECOVERY_ADC','RESET_N','PMIC_SLEEP','SOC_VBUS_DET','DEBUG_RX','DEBUG_TX','ETH_RESET_GPIO_N','WIFI_REG_ON','PMIC_INT_N','LCD_RESET_N','THERMAL_SHUTDOWN','EXP_GPIO2','EXP_GPIO3','EXP_UART_TX','EXP_UART_RX','I2C0_SDA','I2C0_SCL','PHY_CFG_LDO0','PHY_CFG_LDO1']
for net in nets:
    gs=cp['open_nets'][net];code=b.FindNet(net).GetNetCode();seeds=defaultdict(set)
    for idx,g in enumerate(gs):
        members={uid(o) for o in b.GetConnectivity().GetConnectedItems(pad(g[0]))}|{uid(pad(x)) for x in g}
        for ident in members:
            o=objects.get(ident)
            if o is None:continue
            bb=o.GetBoundingBox()
            if isinstance(o,p.PCB_TRACK) and not isinstance(o,p.PCB_VIA):
                a,z=tuple(o.GetStart()),tuple(o.GetEnd());n=max(1,math.ceil(o.GetLength()/100000))
                points=[tuple(round((x+(y-x)*i/n)/grid)*grid for x,y in zip(a,z)) for i in range(n+1)]
            else:points=[(i*grid,j*grid) for i in range(bb.GetLeft()//grid,bb.GetRight()//grid+1) for j in range(bb.GetTop()//grid,bb.GetBottom()//grid+1)]
            for l in layers:
                if not o.IsOnLayer(l):continue
                sh=o.GetEffectiveShape(l);seeds[idx,l].update(pt for pt in points if sh.Collide(V(pt),0))
    trace=make(b,(0,0),(0,0),200000,code,p.F_Cu)
    rules={l:[z.Outline() for z in keep if z.IsOnLayer(l) and z.GetDoNotAllowTracks()] for l in layers};vkeep=[z.Outline() for z in keep if z.GetDoNotAllowVias()]
    @lru_cache(None)
    def free(l,a,z):
        if not bounds.Contains(V(z)):return False
        trace.SetLayer(l);trace.SetStart(V(a));trace.SetEnd(V(z));s=trace.GetEffectiveShape(l)
        for n,sh,h,_,_ in index[(a[0]//tile,a[1]//tile)]:
            if n!=code and (l in sh and s.Collide(sh[l],202000) or h and s.Collide(h,252000)):return False
        return not any(s.Collide(rule,0) for rule in rules[l])
    @lru_cache(None)
    def landing(at):
        v=barrel(b,at,code);sh=v.GetEffectiveShape(p.F_Cu);h=v.GetEffectiveHoleShape()
        if any(sh.Collide(z,0) for z in vkeep):return False
        for n,foil,hole,is_pad,_ in index[(at[0]//tile,at[1]//tile)]:
            if hole and sh.Collide(hole,252000):return False
            if is_pad and any(sh.Collide(s,100000) for s in foil.values()):return False
            if n!=code and any(sh.Collide(s,202000) or h.Collide(s,252000) for s in foil.values()):return False
        return min(math.dist(at,g) for g in gnd_positions)<=1500000
    toe_path={}
    if pmic_toe and net=='VDD_GPU_COM':
        doc=json.loads((r/'pmic-functional-outer-toes.json').read_text());assert doc['parent_sha256']==cp['sha256']
        row=next(v for v in doc['rows'] if v['pin']=='8')
        g=next(i for i,labels in enumerate(gs) if 'U4.8' in labels)
        for pt in row['examples']:
            pt=tuple(pt);tip=(pt[0]-300000,pt[1])
            for x in (tip[0]//grid*grid,tip[0]//grid*grid+grid):
             for y in (tip[1]//grid*grid,tip[1]//grid*grid+grid):
                snapped=(x,y)
                if free(p.F_Cu,pt,tip) and free(p.F_Cu,tip,snapped):
                    seeds[g,p.F_Cu].add(snapped);toe_path[g,p.F_Cu,snapped]=[pt,tip]
    parents={};fronts={};candidates=[];records=[]
    for (g,l),pts in seeds.items():
        other=[p0 for (gg,ll),ps in seeds.items() if gg!=g and (dual or ll!=l) for p0 in ps]
        if not pts or not other or dual and l not in (p.F_Cu,p.B_Cu):continue
        # Reject groups beyond the combined 16 mm route budget without visiting their frontiers.
        xx=[x for x,y in other];yy=[y for x,y in other];span=70000000 if dual else 16000000;bounds0=(min(xx)-span,min(yy)-span,max(xx)+span,max(yy)+span)
        legal={a for a in pts if bounds0[0]<=a[0]<=bounds0[2] and bounds0[1]<=a[1]<=bounds0[3] and free(l,a,a)}
        if not legal:continue
        distances={a:0 for a in legal};prev={};queue=[(0,a) for a in legal];heapq.heapify(queue)
        while queue:
            d,a=heapq.heappop(queue)
            if d!=distances[a]:continue
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                z=a[0]+dx*grid,a[1]+dy*grid;dd=d+grid*math.hypot(dx,dy)
                if dd<=(2500000 if dual else 10000000) and dd<distances.get(z,math.inf) and free(l,a,z):
                    distances[z]=dd;prev[z]=a;heapq.heappush(queue,(dd,z))
        def full_path(fr,at):
            ps=[at]
            while ps[-1] in fr:ps.append(fr[ps[-1]])
            return ps[::-1]
        for (k,ol),reached in fronts.items():
            if g==k or l==ol:continue
            shared=distances.keys()&reached.keys();best=None;in_range=0
            for at in sorted(shared,key=lambda x:distances[x]+reached[x]):
                dd=distances[at]+reached[at]
                if dd>16000000:break
                in_range+=1
                if landing(at):
                    best=dict(groups=[gs[g][0],gs[k][0]],layers=[b.GetLayerName(l),b.GetLayerName(ol)],via_nm=at,length_mm=dd/1e6,paths_nm=[full_path(prev,at),full_path(parents[k,ol],at)])
                    candidates.append(best);break
            records.append(dict(groups=[g,k],layers=[b.GetLayerName(l),b.GetLayerName(ol)],intersections=len(shared),tested=in_range,legal=bool(best)))
        parents[g,l]=prev;fronts[g,l]=distances
    viable={};nearby_vias=[]
    if dual:
        for (g,l),fr in fronts.items():
            legal=[at for at in sorted(fr,key=fr.get) if landing(at)]
            chosen=[]
            for at in legal:
                if all(math.dist(at,q['site_nm'])>=500000 for q in chosen):
                    path=full_path(parents[g,l],at);lead=toe_path.get((g,l,path[0]),[])
                    chosen.append(dict(site_nm=at,path_nm=lead+path,branch_mm=(fr[at]+sum(math.dist(a,z) for a,z in zip(lead+[path[0]],(lead+[path[0]])[1:])))/1e6))
            viable[f'{g}-{b.GetLayerName(l)}']=dict(sites=len(legal),representatives=chosen)
            if pmic_toe and 'U4.8' in gs[g]:
                for at in fr:
                    v=barrel(b,at,code);sh=v.GetEffectiveShape(p.F_Cu);h=v.GetEffectiveHoleShape();bad=set()
                    for n,foil,hole,is_pad,xid in index[(at[0]//tile,at[1]//tile)]:
                        if (hole and sh.Collide(hole,252000)) or (is_pad and any(sh.Collide(s,100000) for s in foil.values())) or (n!=code and any(sh.Collide(s,202000) or h.Collide(s,252000) for s in foil.values())):bad.add(xid)
                    if any(sh.Collide(z,0) for z in vkeep):bad.add('design_rule_area')
                    if min(math.dist(at,gp) for gp in gnd_positions)>1500000:bad.add('ground_return_distance')
                    nearby_vias.append(dict(at=at,blockers=[(xid,objects[xid].GetParentFootprint().GetReference()+'.'+objects[xid].GetNumber() if isinstance(objects.get(xid),p.PAD) else objects[xid].GetNetname() if xid in objects else '') for xid in sorted(bad)]))
    (r/(net.lower()+('-rgmii-source-vias.json' if '--current-mac' in sys.argv else '-RK809-toe-launch.json' if pmic_toe else '-dual-launch-islands.json' if dual else '-one-via-islands.json'))).write_text(json.dumps(dict(parent_sha256=cp['sha256'],network=net,frontiers=[dict(group=g,layer=b.GetLayerName(l),nodes=len(ds)) for (g,l),ds in fronts.items()],pairs=records,local_exit=viable,near_via=sorted(nearby_vias,key=lambda v:len(v['blockers']))[:6],candidates=sorted(candidates,key=lambda e:e['length_mm'])),indent=2)+'\n')
    print(net,len(records),len(candidates),flush=True)
