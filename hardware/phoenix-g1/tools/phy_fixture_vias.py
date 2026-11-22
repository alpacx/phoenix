"""Reach rear-side fixture points from front-side reset and PMU reservoir pads."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'fixture-verified.json').read_text());source=root/cp['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
original=p.LoadBoard(str(source));current=source;records=[]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
def mounts(b):return {(v['reservation'],v['ref']) for v in screen(b)}
def stub(b,layer,net,a,z):
    t=p.PCB_TRACK(b);t.SetStart(a);t.SetEnd(z);t.SetWidth(200000);t.SetLayer(layer);t.SetNetCode(net);return t
def xy(pos):return [p.ToMM(i) for i in pos]
for ref,anchor,pin in [('TP9','U16','2'),('TP5','C465','1')]:
    b=p.LoadBoard(str(current));f=b.FindFootprintByReference(ref);q=f.FindPadByNumber('1');src=b.FindFootprintByReference(anchor).FindPadByNumber(pin)
    a=src.GetPosition();net=q.GetNetCode();assert net==src.GetNetCode() and f.GetLayer()==p.B_Cu
    footprints=[g for g in b.GetFootprints() if g.GetReference()!=ref]
    obs=[o for o in list(b.GetTracks())+[s for g in footprints for s in g.Pads()] if o.GetBoundingBox().Inflate(6500000).Contains(a)]
    sh={l:[o.GetEffectiveShape(l) for o in obs if o.IsOnLayer(l) and o.GetNetCode()!=net] for l in layers}
    def free(shape,l):return all(not shape.Collide(z,200000) for z in sh[l])
    via=p.PCB_VIA(b);via.SetWidth(450000);via.SetDrill(200000);via.SetNetCode(net);via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu)
    seeds=[]
    for dx in range(-18,19):
        for dy in range(-18,19):
            v=a+p.VECTOR2I(dx*100000,dy*100000);via.SetPosition(v)
            if src.GetBoundingBox().Inflate(330000).Contains(v):continue
            if all(free(via.GetEffectiveShape(l),l) for l in layers) and free(stub(b,0,net,a,v).GetEffectiveShape(0),0):
                seeds.append(tuple(v))
    boxes=[g.GetCourtyard(p.B_Cu).BBox() for g in footprints if g.GetLayer()==p.B_Cu and g.GetCourtyard(p.B_Cu).BBox().Inflate(6500000).Contains(a)]
    opts=[]
    for dx in range(-20,21):
        for dy in range(-20,21):
            pos=a+p.VECTOR2I(dx*200000,dy*200000);f.SetPosition(pos);box=f.GetCourtyard(p.B_Cu).BBox()
            if not b.GetBoardEdgesBoundingBox().Contains(box) or any(box.Intersects(z) for z in boxes) or not free(q.GetEffectiveShape(p.B_Cu),p.B_Cu):continue
            for seed in sorted(seeds,key=lambda s:math.dist(s,tuple(pos)))[:30]:
                v=p.VECTOR2I(*seed)
                if q.GetBoundingBox().Inflate(330000).Contains(v):continue
                if free(stub(b,p.B_Cu,net,v,pos).GetEffectiveShape(p.B_Cu),p.B_Cu):
                    opts.append((math.dist(seed,tuple(a))+math.dist(seed,tuple(pos)),seed,tuple(pos)));break
    held=[];tested=0
    for length,seed,loc in sorted(opts):
        f.SetPosition(p.VECTOR2I(*loc))
        if any(r[1]==ref for r in mounts(b)):continue
        tested+=1
        if tested>12:break
        v=p.VECTOR2I(*seed);via.SetPosition(v)
        added=[via,stub(b,p.F_Cu,net,a,v),stub(b,p.B_Cu,net,v,f.GetPosition())]
        for t in added:b.Add(t)
        dest=root/'runs'/('fixture-via-'+ref);dest.mkdir(exist_ok=True)
        for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/file,dest/file)
        out=dest/source.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dest/'drc.json'),str(out)],check=True,capture_output=True)
        diff=introduced(json.loads((source.parent/'drc.json').read_text()),json.loads((dest/'drc.json').read_text()))
        if not diff:
            saved=p.LoadBoard(str(out));pres=verify_preservation(original,saved)
            test=saved.FindFootprintByReference(ref).FindPadByNumber('1')
            assert src.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(test)}
            records.append(dict(ref=ref,anchor=anchor,pin=pin,stub_mm=length/1e6,pos_mm=xy(f.GetPosition()),preservation=pres))
            current=out;break
        for t in added:b.Remove(t);held.append(t)
    print(ref,len(seeds),len(opts),current.parent.name,flush=True)
saved=p.LoadBoard(str(current))
(root/'fixture-vias-verified.json').write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),resolved=sorted(mounts(original)-mounts(saved)),records=records),indent=2)+'\n')
os._exit(0)
