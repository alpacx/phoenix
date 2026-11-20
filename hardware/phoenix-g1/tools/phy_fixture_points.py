"""Move three isolated fixture pads out of mounting reservations onto their actual nets."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
solid='--solid' in sys.argv
cp=json.loads((root/('integrated-fixture-bias.json' if solid else 'phy-rear-bias-verified.json')).read_text());source=root/cp['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
original=p.LoadBoard(str(source));current=source;records=[]
def mounts(board):return {(r['reservation'],r['ref']) for r in screen(board)}
def xy(pos):return [p.ToMM(i) for i in pos]
for ref,terminal,number in ([('TP14','U17','4')] if solid else [('TP14','U17','4'),('TP9','U16','2'),('TP5','C465','1')]):
    b=p.LoadBoard(str(current));b.BuildConnectivity()
    f=b.FindFootprintByReference(ref);q=f.FindPadByNumber('1')
    target=b.FindFootprintByReference(terminal).FindPadByNumber(number)
    assert target.GetNetCode()==q.GetNetCode()
    if not solid:assert len(list(b.GetConnectivity().GetConnectedItems(q)))==1
    layer=f.GetLayer();net=q.GetNetCode();orig=f.GetPosition();seeds=set()
    for o in b.GetConnectivity().GetConnectedItems(target):
        if not o.IsOnLayer(layer):continue
        if isinstance(o,p.PCB_TRACK):
            a,z=tuple(o.GetStart()),tuple(o.GetEnd())
            count=max(1,math.ceil(o.GetLength()/600000))
            seeds.update(tuple(round(u+(v-u)*i/count) for u,v in zip(a,z)) for i in range(count+1))
        else:seeds.add(tuple(o.GetPosition()))
    allfp=[g for g in b.GetFootprints() if g.GetReference()!=ref]
    boxes=[g.GetCourtyard(layer).BBox() for g in allfp if g.GetLayer()==layer]
    ob=[o for o in list(b.GetTracks())+[pad for g in allfp for pad in g.Pads()] if o.IsOnLayer(layer) and o.GetNetCode()!=net]
    vias=[v.GetPosition() for v in b.GetTracks() if isinstance(v,p.PCB_VIA)]
    options=[]
    edge=b.GetBoardEdgesBoundingBox()
    for seed in sorted(seeds,key=lambda s:math.dist(s,tuple(target.GetPosition())))[:24]:
        a=p.VECTOR2I(*seed)
        shapes=[o.GetEffectiveShape(layer) for o in ob if o.GetBoundingBox().Inflate(6000000).Contains(a)]
        near=[z for z in boxes if p.BOX2I(z.GetOrigin(),z.GetSize()).Inflate(6000000).Contains(a)]
        for r in [0,.8,1.1,1.5,2,2.5,3.2,4]:
            for angle in range(0,360,15 if r else 360):
                v=math.radians(angle);pos=a+p.VECTOR2I(p.FromMM(r*math.cos(v)),p.FromMM(r*math.sin(v)));f.SetPosition(pos)
                box=f.GetCourtyard(layer).BBox()
                if not edge.Contains(box) or any(box.Intersects(z) for z in near):continue
                if solid and any(q.GetBoundingBox().Inflate(350000).Contains(v) for v in vias):continue
                t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(200000);t.SetStart(a);t.SetEnd(pos)
                if any(q.GetEffectiveShape(layer).Collide(s,200000) or t.GetEffectiveShape(layer).Collide(s,200000) for s in shapes):continue
                options.append((r,math.dist(tuple(pos),tuple(orig)),seed,tuple(pos)))
    stable=mounts(original);held=[]
    for length,_,seed,pos in sorted(options)[:120]:
        f.SetPosition(p.VECTOR2I(*pos))
        if any(x[1]==ref for x in mounts(b)) or mounts(b)-stable:continue
        t=None
        if length:
            t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(200000);t.SetStart(p.VECTOR2I(*seed));t.SetEnd(p.VECTOR2I(*pos));t.SetNetCode(net);b.Add(t)
        dest=root/'runs'/(('solid-fixture-' if solid else 'fixture-')+ref);dest.mkdir(exist_ok=True)
        for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/file,dest/file)
        out=dest/source.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dest/'drc.json'),str(out)],check=True,capture_output=True)
        diff=introduced(json.loads((source.parent/'drc.json').read_text()),json.loads((dest/'drc.json').read_text()))
        if not diff:
            saved=p.LoadBoard(str(out));pres=verify_preservation(original,saved)
            test=saved.FindFootprintByReference(ref).FindPadByNumber('1')
            assert target.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(test)}
            records.append(dict(ref=ref,terminal=terminal,pad=number,net=q.GetNetname(),pos_mm=xy(f.GetPosition()),stub_mm=length,preservation=pres))
            current=out;break
        if t:b.Remove(t);held.append(t)
    print(ref,len(options),current.parent.name,flush=True)
saved=p.LoadBoard(str(current))
(root/('fixture-solid-verified.json' if solid else 'fixture-verified.json')).write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),resolved=sorted(mounts(original)-mounts(saved)),records=records),indent=2)+'\n')
os._exit(0)
