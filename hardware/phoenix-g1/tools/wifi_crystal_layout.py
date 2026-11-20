"""Joint rear placement for the crystal and series resistor beside the module."""
from pathlib import Path
import hashlib,json,math,subprocess,shutil,os
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'sense-filter-return.json').read_text());src=root/cp['board']
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
def line(one,two):
    assert one.GetNetCode()==two.GetNetCode()
    t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(200000);t.SetNetCode(one.GetNetCode());t.SetStart(one.GetPosition());t.SetEnd(two.GetPosition());return t
fps=[f for f in b.GetFootprints() if f.GetReference() not in (yref,rref)]
boxes=[f.GetCourtyard(layer).BBox() for f in fps if f.GetLayer()==layer and f.GetCourtyard(layer).BBox().Inflate(13000000).Contains(origin)]
objs=[o for o in list(b.GetTracks())+[q for f in fps for q in f.Pads()] if o.IsOnLayer(layer) and o.GetBoundingBox().Inflate(13000000).Contains(origin)]
obs=[(o.GetNetCode(),o.GetEffectiveShape(layer)) for o in objs]
def clear(o,items):
    shape=o.GetEffectiveShape(layer)
    return all(o.GetNetCode()==n or not shape.Collide(s,200000) for n,s in items)
def sites(f,ball,terminal):
    opts=[]
    for angle in (0,90,180,270):
        f.SetOrientationDegrees(angle)
        for i in range(-30,31):
            for j in range(-30,31):
                loc=ball.GetPosition()+p.VECTOR2I(i*200000,j*200000);f.SetPosition(loc)
                box=f.GetCourtyard(layer).BBox()
                if any(box.Intersects(other) for other in boxes):continue
                pads=list(f.Pads());t=line(ball,pin(f,terminal))
                if t.GetLength()>6500000 or not all(clear(o,obs) for o in pads+[t]):continue
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
folder=root/('runs/soc-crystal-series' if soc else 'runs/wifi-crystal-series');folder.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
held=[];record=None
for _,sy,sr in sorted(best)[:16]:
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
(root/('soc-crystal-series.json' if soc else 'wifi-crystal-series.json')).write_text(json.dumps(record or dict(candidates=len(best),individual=[len(ys),len(rs)],accepted=False),indent=2)+'\n')
print(bool(record),flush=True);os._exit(0)
