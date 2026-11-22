"""Joint rear placement for the crystal and series resistor beside the module."""
from pathlib import Path
import hashlib,json,math,subprocess,shutil,os
from collections import Counter
import pcbnew as p
from pcb_preservation import verify_preservation
from pcb_bounds import inflated_box
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
cluster='--wifi-cluster' in sys.argv
reserve='--review-vbat' in sys.argv or cluster
current='--current' in sys.argv or reserve
cp=json.loads((root/('layout-pmic-pwron-filter.json' if current else 'sense-filter-return.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
import sys
soc='--soc' in sys.argv
b=p.LoadBoard(str(src));layer=p.F_Cu if soc else p.B_Cu
yref,rref,mref=('Y1','R1501','U1') if soc else ('Y2002','R2004','U25')
y=b.FindFootprintByReference(yref);r=b.FindFootprintByReference(rref);mod=b.FindFootprintByReference(mref)
for f in (y,r):
    if f.GetLayer()!=layer:f.Flip(f.GetPosition(),False)
pin=lambda f,n:f.FindPadByNumber(str(n))
a,z=pin(mod,'AG25' if soc else 10),pin(mod,'AF25' if soc else 11);origin=a.GetPosition()
removed=[]
if reserve:
    removed=[o for o in b.GetTracks() if o.GetNetname()=='WIFI_VBAT' and inflated_box(o,3600000).Contains(origin) and (o.IsOnLayer(layer) or isinstance(o,p.PCB_VIA))]
    for o in removed:b.Remove(o)
def line(one,two):
    assert one.GetNetCode()==two.GetNetCode()
    t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(200000);t.SetNetCode(one.GetNetCode());t.SetStart(one.GetPosition());t.SetEnd(two.GetPosition())
    if current and not soc and one.GetParentFootprint().GetReference()=='U25':
        outer=one.GetBoundingBox(layer).GetRight()-40000
        toe=p.VECTOR2I(outer,one.GetPosition().y);t.SetStart(toe)
        assert t.GetEffectiveShape(layer).Collide(one.GetEffectiveShape(layer),0)
    return t
variable_refs={yref,rref}|({'C2008','C2009','C2002'} if cluster else set())
fps=[f for f in b.GetFootprints() if f.GetReference() not in variable_refs]
boxes=[f.GetCourtyard(layer).BBox() for f in fps if f.GetLayer()==layer and inflated_box(f,13000000).Contains(origin)]
objs=[o for o in list(b.GetTracks())+[q for f in fps for q in f.Pads()] if o.IsOnLayer(layer) and inflated_box(o,13000000).Contains(origin)]
obs=[(o.GetNetCode(),o.GetEffectiveShape(layer)) for o in objs]
def clear(o,items):
    shape=o.GetEffectiveShape(layer)
    return all(o.GetNetCode()==n or not shape.Collide(s,200000) for n,s in items)
diagnostics={};crystal_conflicts={}
def sites(f,ball,terminal):
    opts=[];counts=Counter();diagnostics[f.GetReference()]=counts
    for angle in (0,90,180,270):
        f.SetOrientationDegrees(angle)
        for i in range(-30,31):
            for j in range(-30,31):
                loc=ball.GetPosition()+p.VECTOR2I(i*200000,j*200000);f.SetPosition(loc)
                box=f.GetCourtyard(layer).BBox()
                if any(box.Intersects(other) for other in boxes):continue
                counts['courtyards']+=1
                pads=list(f.Pads());t=line(ball,pin(f,terminal))
                if t.GetLength()>6500000:continue
                counts['within_budget']+=1
                if not all(clear(o,obs) for o in pads):
                    if cluster and f.GetReference()==yref:
                        impacts=set()
                        for pad0 in pads:
                            sh=pad0.GetEffectiveShape(layer)
                            for ob,(nc,shape) in zip(objs,obs):
                                if nc!=pad0.GetNetCode() and sh.Collide(shape,200000):impacts.add((ob.GetNetname(),ob.GetParentFootprint().GetReference()+'.'+ob.GetNumber() if isinstance(ob,p.PAD) else ob.m_Uuid.AsString()))
                        key=tuple(sorted({n for n,_ in impacts}))
                        score=(len(impacts),t.GetLength())
                        if key not in crystal_conflicts or score<crystal_conflicts[key][0]:
                            crystal_conflicts[key]=(score,dict(nets=key,interference=sorted(impacts),length_mm=t.GetLength()/1e6,angle=angle,xy_nm=tuple(loc)))
                    continue
                counts['all_lands']+=1
                if not clear(t,obs):continue
                counts['from_pin']+=1
                if not clear(t,[(q.GetNetCode(),q.GetEffectiveShape(layer)) for q in pads]):continue
                opts.append((t.GetLength(),angle,tuple(loc)))
    return sorted(opts)
ys=sites(y,a,1);rs=sites(r,z,1)
print('individual',len(ys),len(rs),flush=True)
def put(f,site):
    _,ang,loc=site;f.SetOrientationDegrees(ang);f.SetPosition(p.VECTOR2I(*loc))
best=[]
for sy in ys[:220]:
    put(y,sy);ty=line(a,pin(y,1));ybox=y.GetCourtyard(layer).BBox()
    extra=[(o.GetNetCode(),o.GetEffectiveShape(layer)) for o in list(y.Pads())+[ty]]
    for sr in rs[:220]:
        put(r,sr)
        if r.GetCourtyard(layer).BBox().Intersects(ybox):continue
        tr=line(z,pin(r,1));link=line(pin(r,2),pin(y,3))
        if link.GetLength()>3800000 or not clear(link,obs):continue
        rpads=list(r.Pads())
        if not all(clear(o,extra) for o in rpads+[tr,link]):continue
        if not clear(link,[(o.GetNetCode(),o.GetEffectiveShape(layer)) for o in rpads+[tr]]):continue
        best.append((sy[0]+sr[0]+link.GetLength(),sy,sr))
print('joint',len(best),flush=True)
case=('soc-crystal-series' if soc else 'wifi-crystal-series')+('-cluster-window' if cluster else '-supply-window' if reserve else '-toe' if current else '')
folder=root/'runs'/case;folder.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
held=[];record=None
for _,sy,sr in ([] if reserve else sorted(best)[:16]):
    put(y,sy);put(r,sr)
    if any(row['ref'] in (yref,rref) for row in screen(b)):continue
    routes=[line(a,pin(y,1)),line(z,pin(r,1)),line(pin(r,2),pin(y,3))]
    for t in routes:b.Add(t)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if not delta:
        saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved)
        pairs=[(mref,a.GetNumber(),yref,1),(mref,z.GetNumber(),rref,1),(rref,2,yref,3)]
        for f,n,g,m in pairs:
            group=saved.GetConnectivity().GetConnectedItems(pin(saved.FindFootprintByReference(f),n))
            assert pin(saved.FindFootprintByReference(g),m).m_Uuid.AsString() in {o.m_Uuid.AsString() for o in group}
        record=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),lengths_mm=[p.ToMM(t.GetLength()) for t in routes],pairs=pairs,preservation=pres,new_drc=delta,clock_qualified=False)
        break
    for t in routes:b.Remove(t);held.append(t)
(root/(case+'.json')).write_text(json.dumps(record or dict(candidates=len(best),individual=[len(ys),len(rs)],screen=diagnostics,ranked_obstructions=[k[1] for k in sorted(crystal_conflicts.values(),key=lambda k:k[0])[:20]],accepted=False,board_sha256=cp['sha256'],hypothetically_removed=[o.m_Uuid.AsString() for o in removed],best=sorted(best)[:10]),indent=2)+'\n')
print(bool(record),flush=True);os._exit(0)
