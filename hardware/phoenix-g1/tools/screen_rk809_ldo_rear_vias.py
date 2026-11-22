"""Test through-via access for LDO4 and LDO9 with a short terminal neck and 0.4 mm exit."""
from pathlib import Path
import hashlib,json,math,os,sys
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
ldo6='--pmu-rail' in sys.argv
sd='--sd-rail' in sys.argv
base=json.loads((root/('layout-emmc-data-power.json' if sd else 'layout-cpu-enable-bias.json' if ldo6 else 'layout-exp-spi0-pullup.json')).read_text());src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));pmic=b.FindFootprintByReference('U4');layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
v=lambda xy:p.VECTOR2I(*xy);result=[]
for n,ref in ([('29','C464')] if sd else [('31','C465')] if ldo6 else [('28','C463'),('6','C468')]):
    pin=pmic.FindPadByNumber(n);at=pin.GetPosition();a=tuple(at);bb=pin.GetBoundingBox();axis=0 if bb.GetWidth()>bb.GetHeight() else 1;sgn=1 if a[axis]>tuple(pmic.GetPosition())[axis] else -1
    edge=list(a);edge[axis]+=sgn*(bb.GetWidth() if axis==0 else bb.GetHeight())//2
    near=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if inflated_box(o,3750000).Contains(at) and o.GetNetCode()!=pin.GetNetCode()]
    obs={l:[(o.GetEffectiveShape(l),o.GetBoundingBox()) for o in near if o.IsOnLayer(l)] for l in layers}
    holes=[o.GetEffectiveHoleShape() for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    def clean(o,l,margin):
        sh=o.GetEffectiveShape(l);box=inflated_box(o,margin+10000)
        return not any(box.Intersects(g) and sh.Collide(s,margin) for s,g in obs[l]) and not any(sh.Collide(h,252000) for h in holes)
    def tr(a,z,w):
        t=p.PCB_TRACK(b);t.SetStart(v(a));t.SetEnd(v(z));t.SetWidth(w);t.SetLayer(p.F_Cu);t.SetNetCode(pin.GetNetCode());return t
    leads=[]
    lead_obstacles={}
    for offset in (-25000,15000,45000,65000,90000):
        start=edge.copy();start[axis]+=sgn*offset
        for rr in (150000,250000,350000,450000,550000):
            elbow=edge.copy();elbow[axis]+=sgn*rr
            lead=tr(start,elbow,200000)
            if sd:
                for obj in near:
                    if obj.IsOnLayer(p.F_Cu) and lead.GetEffectiveShape(p.F_Cu).Collide(obj.GetEffectiveShape(p.F_Cu),202000):
                        key=obj.GetNetname() + ' ' + obj.m_Uuid.AsString()
                        lead_obstacles[key]=lead_obstacles.get(key,0)+1
            if clean(lead,p.F_Cu,202000) and lead.GetEffectiveShape(p.F_Cu).Collide(pin.GetEffectiveShape(p.F_Cu),0):leads.append((start,elbow))
    barrel=p.PCB_VIA(b);barrel.SetWidth(450000);barrel.SetDrill(200000);barrel.SetViaType(p.VIATYPE_THROUGH);barrel.SetLayerPair(p.F_Cu,p.B_Cu)
    sites=[];clear_barrels=0
    for dx in range(-52,53):
      for dy in range(-52,53):
        pt=(edge[0]+dx*50000,edge[1]+dy*50000)
        if math.dist(edge,pt)>2650000:continue
        barrel.SetPosition(v(pt));sh=barrel.GetEffectiveShape(p.F_Cu);hole=barrel.GetEffectiveHoleShape()
        if sh.Collide(pin.GetEffectiveShape(p.F_Cu),75000) or any(not clean(barrel,l,202000) for l in layers) or any(z.Collide(sh,0) for z in zones):continue
        box=inflated_box(barrel,350000)
        if any(box.Intersects(g) and hole.Collide(s,252000) for l in layers for s,g in obs[l]) or any(hole.Collide(h,252000) for h in holes):continue
        clear_barrels+=1;choices=[]
        for start,elbow in leads:
            dx=pt[0]-elbow[0];dy=pt[1]-elbow[1];d=min(abs(dx),abs(dy));xx=int(math.copysign(d,dx));yy=int(math.copysign(d,dy))
            for c in ((elbow[0]+xx,elbow[1]+yy),(pt[0]-xx,pt[1]-yy)):
                path=[elbow,c,pt];segs=[tr(x,z,400000) for x,z in zip(path,path[1:]) if x!=z]
                if all(clean(t,p.F_Cu,202000) for t in segs):choices.append((math.dist(start,elbow)+sum(t.GetLength() for t in segs),[start]+path))
        if choices:
            length,path=min(choices);sites.append(dict(via_nm=pt,length_mm=length/1e6,path_nm=path))
    result.append(dict(pin=n,capacitor=ref,legal_necks=len(leads),lead_obstacles=lead_obstacles,legal_barrel_positions=clear_barrels,sites=sorted(sites,key=lambda e:e['length_mm'])))
(root/('ldo5-sd-via-window.json' if sd else 'ldo6-pmu-via-window.json' if ldo6 else 'ldo-local-rear-windows.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],rows=result,assembly_ready=False),indent=2)+'\n')
print([(r['pin'],r['legal_necks'],r['legal_barrel_positions'],len(r['sites'])) for r in result],flush=True);os._exit(0)
