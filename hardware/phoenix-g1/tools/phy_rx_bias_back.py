"""Place RX pull-ups on the rear using a short, individually checked signal tap."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
rx0='--rx0' in sys.argv
divider='--divider' in sys.argv
wifi='--wifi-front' in sys.argv
face,dest_layer=(p.B_Cu,p.F_Cu) if wifi else (p.F_Cu,p.B_Cu)
cp=json.loads((root/('sense-filter-return.json' if wifi else 'strap-remaining-verified.json' if divider else 'phy-rear-bias-verified.json' if rx0 else 'phy-bias-verified.json')).read_text());source=root/cp['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
original=p.LoadBoard(str(source));current=source;records=[]
def mm(v):return tuple(p.ToMM(i) for i in v)
def vec(a):return p.VECTOR2I(*a)
def mounts(b):return {(r['reservation'],r['ref']) for r in screen(b)}
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
for ref,series in ([('R2014','U25')] if wifi else [('R1506','R1505')] if divider else [('R507','U5')] if rx0 else [('R521','R510'),('R526','R507')]):
    b=p.LoadBoard(str(current));f=b.FindFootprintByReference(ref);
    if f.GetLayer()!=dest_layer:f.Flip(f.GetPosition(),False)
    q=b.FindFootprintByReference(series).FindPadByNumber('16' if wifi else '25' if rx0 else '2');origin=q.GetPosition();net=q.GetNetCode()
    signal,other=('2','1') if rx0 else ('1','2')
    if rx0:origin=origin+p.VECTOR2I(0,-250000)
    if wifi:origin=origin+p.VECTOR2I(0,430000)
    assert q.HitTest(origin) and f.FindPadByNumber(signal).GetNetCode()==net
    fpts=[g for g in b.GetFootprints() if g.GetReference()!=ref]
    objs=[o for o in list(b.GetTracks())+[pad for g in fpts for pad in g.Pads()] if o.GetBoundingBox().Inflate(5000000).Contains(origin)]
    shapes={l:[(o.GetNetCode(),o.GetEffectiveShape(l)) for o in objs if o.IsOnLayer(l)] for l in layers}
    def clear(shape,l,n):return all(k==n or not shape.Collide(s,200000) for k,s in shapes[l])
    def track(a,z,l):
        t=p.PCB_TRACK(b);t.SetLayer(l);t.SetWidth(200000);t.SetNetCode(net);t.SetStart(a);t.SetEnd(z);return t
    via=p.PCB_VIA(b);via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetWidth(450000);via.SetDrill(200000);via.SetNetCode(net)
    targets=[]
    for dx in range(-24,25):
        for dy in range(-24,25):
            site=origin+p.VECTOR2I(dx*50000,dy*50000);via.SetPosition(site)
            if all(clear(via.GetEffectiveShape(l),l,net) for l in layers) and clear(track(origin,site,face).GetEffectiveShape(face),face,net):
                targets.append(tuple(site))
    boxes=[g.GetCourtyard(dest_layer).BBox() for g in fpts if g.GetLayer()==dest_layer and g.GetCourtyard(dest_layer).BBox().Inflate(5000000).Contains(origin)]
    options=[]
    for a in (0,90,180,270):
        f.SetOrientationDegrees(a)
        for dx in range(-22,23):
            for dy in range(-22,23):
                loc=origin+p.VECTOR2I(dx*100000,dy*100000);f.SetPosition(loc)
                if any(f.GetCourtyard(dest_layer).BBox().Intersects(box) for box in boxes):continue
                one,two=(f.FindPadByNumber(n) for n in (signal,other))
                if not all(clear(pad.GetEffectiveShape(dest_layer),dest_layer,pad.GetNetCode()) for pad in (one,two)):continue
                for pos in sorted(targets,key=lambda pos:math.dist(pos,tuple(one.GetPosition())))[:8]:
                    via.SetPosition(vec(pos));rear=track(vec(pos),one.GetPosition(),dest_layer)
                    if math.dist(pos,tuple(origin))+rear.GetLength()>2200000:continue
                    if clear(rear.GetEffectiveShape(dest_layer),dest_layer,net) and all(not s.Collide(two.GetEffectiveShape(dest_layer),200000) for s in (rear.GetEffectiveShape(dest_layer),via.GetEffectiveShape(dest_layer))):
                        options.append((math.dist(pos,tuple(origin))+rear.GetLength(),a,tuple(loc),pos))
                        break
    print(ref,len(targets),len(options),flush=True)
    held=[]
    for length,a,loc,pos in sorted(options)[:12]:
        f.SetPosition(vec(loc));f.SetOrientationDegrees(a);via.SetPosition(vec(pos))
        if mounts(b)-mounts(original):continue
        tracks=[track(origin,vec(pos),face),track(vec(pos),f.FindPadByNumber(signal).GetPosition(),dest_layer)]
        added=[via]+[t for t in tracks if t.GetLength()>0]
        for t in added:b.Add(t)
        dest=root/'runs'/('phy-rx-back-'+ref);dest.mkdir(exist_ok=True)
        for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/file,dest/file)
        out=dest/source.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dest/'drc.json'),str(out)],check=True,capture_output=True)
        diff=introduced(json.loads((source.parent/'drc.json').read_text()),json.loads((dest/'drc.json').read_text()))
        if not diff:
            saved=p.LoadBoard(str(out));pres=verify_preservation(original,saved)
            pin=saved.FindFootprintByReference(ref).FindPadByNumber(signal)
            assert q.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(pin)}
            records.append(dict(ref=ref,series=series,stub_mm=length/1e6,preservation=pres,new_drc=diff));current=out;break
        for t in added:b.Remove(t);held.append(t)
(root/('wifi-cmd-front.json' if wifi else 'sense-back-verified.json' if divider else 'phy-rx0-escape.json' if rx0 else 'phy-rx-back.json')).write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),records=records),indent=2)+'\n')
os._exit(0)
