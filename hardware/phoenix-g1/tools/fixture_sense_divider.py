"""Pair the VBUS sense pull-down with its filter capacitor outside H8104."""
from pathlib import Path
import hashlib,json,os,subprocess,shutil
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
cap='--cap' in sys.argv
cp=json.loads((root/('sense-front-verified.json' if cap else 'fixture-vias-verified.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));moving,fixed=('C1503','R1506') if cap else ('R1506','C1503')
f=b.FindFootprintByReference(moving);c=b.FindFootprintByReference(fixed)
layer=c.GetLayer();site=c.GetPosition()
pads=lambda fp:[fp.FindPadByNumber(n) for n in ('1','2')]
layers=[q.GetNetCode() for q in pads(c)];assert layers==[q.GetNetCode() for q in pads(f)]
fps=[g for g in b.GetFootprints() if g.GetReference()!=moving]
boxes=[g.GetCourtyard(layer).BBox() for g in fps if g.GetLayer()==layer and g.GetCourtyard(layer).BBox().Inflate(5000000).Contains(site)]
obj=[o for o in list(b.GetTracks())+[q for g in fps for q in g.Pads()] if o.IsOnLayer(layer) and o.GetBoundingBox().Inflate(5000000).Contains(site)]
shapes=[(o.GetNetCode(),o.GetEffectiveShape(layer)) for o in obj]
def clear(o):return all(net==o.GetNetCode() or not o.GetEffectiveShape(layer).Collide(shape,200000) for net,shape in shapes)
def tracks():
    out=[]
    for a,z in zip(pads(c),pads(f)):
        t=p.PCB_TRACK(b);t.SetNetCode(a.GetNetCode());t.SetLayer(layer);t.SetWidth(200000);t.SetStart(a.GetPosition());t.SetEnd(z.GetPosition());out.append(t)
    return out
options=[]
for angle in (0,90,180,270):
    f.SetOrientationDegrees(angle)
    for i in range(-32,33):
        for j in range(-32,33):
            loc=site+p.VECTOR2I(i*100000,j*100000);f.SetPosition(loc)
            if any(f.GetCourtyard(layer).BBox().Intersects(box) for box in boxes):continue
            wires=tracks()
            if not all(clear(o) for o in pads(f)+wires):continue
            if any(w.GetEffectiveShape(layer).Collide(q.GetEffectiveShape(layer),200000) for w,q in zip(wires,reversed(pads(f)))):continue
            if wires[0].GetEffectiveShape(layer).Collide(wires[1].GetEffectiveShape(layer),200000):continue
            options.append((sum(w.GetLength() for w in wires),angle,tuple(loc)))
dest=root/('runs/sense-cap' if cap else 'runs/sense-divider');dest.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,dest/file)
held=[]
tested=0
for length,a,loc in sorted(options):
    f.SetPosition(p.VECTOR2I(*loc));f.SetOrientationDegrees(a)
    if any(row['ref']==moving for row in screen(b)):continue
    tested+=1
    if tested>12:break
    wires=tracks()
    for w in wires:b.Add(w)
    out=dest/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dest/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((dest/'drc.json').read_text()))
    if not delta:
        saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved)
        for one,two in zip(pads(saved.FindFootprintByReference('C1503')),pads(saved.FindFootprintByReference('R1506'))):
            assert one.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(two)}
        cp=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),referenced_nodes=['C1503.1','C1503.2'],preservation=pres,new_drc=delta)
        break
    for w in wires:b.Remove(w);held.append(w)
print(len(options),cp['board'],flush=True)
(root/('sense-cap.json' if cap else 'sense-divider.json')).write_text(json.dumps(cp,indent=2)+'\n');os._exit(0)
