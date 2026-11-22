"""Place the two unconnected RX strap resistors near their series resistors."""
import math,os,json,hashlib,subprocess,shutil
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
wifi='--wifi' in sys.argv
divider='--divider' in sys.argv
cap='--filter' in sys.argv
memory='--memory-zq' in sys.argv
io_bank='--emmc-input-bank' in sys.argv
emmc='--emmc-vccq-link' in sys.argv or io_bank
accessory='--connector-pullups' in sys.argv or emmc
aux='--control-passives' in sys.argv or accessory
reset='--reset-bias' in sys.argv or aux
local='--local-controls' in sys.argv or reset
local_pins={'R413':('7','2'), 'R513':('39','1'), 'R528':('33','1'), 'R529':('34','1')}
if reset:local_pins={'R412':('1','2')}
if aux:local_pins={'R1507':('2','2'),'R1504':('1','1')}
if accessory:local_pins={'R2101':('23','1'),'R2103':('34','1'),'R2104':('35','1')}
if emmc:local_pins={'R8006':('1','2')}
trace_width=500000 if emmc else 200000
cp=json.loads((root/('emmc-trunks.json' if io_bank else 'connector-pullups.json' if emmc else 'layout-pmic-bus.json' if accessory else 'lead-escape.json' if aux else 'layout-connectivity.json' if reset else 'pmic-control-bus.json' if local else 'memory-reset-verified.json' if memory else 'local-passive-feeds.json' if cap else 'strap-remaining-verified.json' if divider else 'phy-fixture-checkpoint.json' if wifi else 'phy-bias-verified.json')).read_text());source=root/cp['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
original=p.LoadBoard(str(source));current=source
prior=json.loads((source.parent/'drc.json').read_text());records=[]
def pt(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def mm(pos):return tuple(p.ToMM(v) for v in pos)
def mounts(b):return {(v['reservation'],v['ref']) for v in screen(b)}
for ref,series in ([('R8006','C8003')] if io_bank else [('R8006','C8006')] if emmc else [('R2101','J3'),('R2103','J3'),('R2104','J3')] if accessory else [('R1507','U16'),('R1504','TP10')] if aux else [('R412','C411')] if reset else [('R413','U4'),('R513','U5'),('R528','U5'),('R529','U5')] if local else [('R201','U2')] if memory else [('C1503','R1506')] if cap else [('R1506','R1505')] if divider else [('R2014','U25')] if wifi else [('R521','R510'),('R526','R507')]):
    b=p.LoadBoard(str(current));f=b.FindFootprintByReference(ref);target=b.FindFootprintByReference(series).FindPadByNumber(local_pins[ref][0] if local else 'A5' if memory else '1' if cap else '16' if wifi else '2')
    pin=local_pins[ref][1] if local else '1'
    assert f.FindPadByNumber(pin).GetNetCode()==target.GetNetCode()
    start=target.GetPosition();sig=target.GetNetname()
    if local and not reset:
        center=b.FindFootprintByReference(series).GetPosition()
        box=target.GetBoundingBox()
        if box.GetWidth()>box.GetHeight():
            start.x+=(1 if start.x>center.x else -1)*(box.GetWidth()//2-20000)
        else:
            start.y+=(1 if start.y>center.y else -1)*(box.GetHeight()//2-20000)
        assert target.HitTest(start)
    layer=b.FindFootprintByReference(series).GetLayer()
    if f.GetLayer()!=layer:f.Flip(f.GetPosition(),False)
    footprints=[g for g in b.GetFootprints() if g.GetReference()!=ref]
    boxes=[g.GetCourtyard(layer).BBox() for g in footprints if g.GetLayer()==layer and g.GetCourtyard(layer).BBox().Inflate(6500000).Contains(start)]
    obs=[(o.GetNetname(),o.GetEffectiveShape(layer)) for o in list(b.GetTracks())+[q for g in footprints for q in g.Pads()] if o.IsOnLayer(layer) and o.GetBoundingBox().Inflate(6500000).Contains(start)]
    def clear(shape,net):return all(n==net or not shape.Collide(s,200000) for n,s in obs)
    sites=[]
    for a in (0,90,180,270):
        f.SetOrientationDegrees(a)
        grid=range(-55,56) if local else range(-32,33)
        for dx in grid:
            for dy in grid:
                loc=start+pt(dx*.1,dy*.1);f.SetPosition(loc)
                if not b.GetBoardEdgesBoundingBox().Contains(f.GetCourtyard(layer).BBox()) or any(f.GetCourtyard(layer).BBox().Intersects(z) for z in boxes):continue
                one,two=(f.FindPadByNumber(n) for n in (pin,'2' if pin=='1' else '1'))
                if not all(clear(q.GetEffectiveShape(layer),q.GetNetname()) for q in (one,two)):continue
                t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(trace_width);t.SetStart(start);t.SetEnd(one.GetPosition())
                if t.GetLength()>(4800000 if local else 2200000) or not clear(t.GetEffectiveShape(layer),sig) or t.GetEffectiveShape(layer).Collide(two.GetEffectiveShape(layer),200000):continue
                sites.append((t.GetLength(),a,tuple(loc)))
    accepted=False
    tested=0
    for length,a,loc in sorted(sites):
        f.SetOrientationDegrees(a);f.SetPosition(p.VECTOR2I(*loc))
        positions=mounts(b)
        if positions-mounts(original) or any(k[1]==ref for k in positions):continue
        tested+=1
        if tested>12:break
        t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(trace_width);t.SetNetCode(target.GetNetCode());t.SetStart(start);t.SetEnd(f.FindPadByNumber(pin).GetPosition());b.Add(t)
        dest=root/'runs'/(f'emmc-input-site-{ref}' if io_bank else f'phy-strap-site-{ref}')
        dest.mkdir(exist_ok=True)
        for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/file,dest/file)
        out=dest/source.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dest/'drc.json'),str(out)],check=True,capture_output=True)
        diff=introduced(prior,json.loads((dest/'drc.json').read_text()))
        if not diff:
            saved=p.LoadBoard(str(out));pres=verify_preservation(original,saved)
            q=saved.FindFootprintByReference(ref).FindPadByNumber(pin)
            assert target.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(q)}
            records.append(dict(ref=ref,target=series,center_mm=mm(f.GetPosition()),stub_mm=length/1e6,new_drc=diff,preservation=pres))
            current=out;accepted=True;break
        b.Remove(t)
    print(ref,len(sites),accepted,flush=True)
(root/('emmc-input-bank.json' if io_bank else 'emmc-vccq-link.json' if emmc else 'connector-pullups.json' if accessory else 'control-passives.json' if aux else 'reset-bias-verified.json' if reset else 'local-controls-verified.json' if local else 'memory-zq-verified.json' if memory else 'sense-filter-verified.json' if cap else 'sense-front-verified.json' if divider else 'wifi-cmd-strap.json' if wifi else 'phy-strap-placement.json')).write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),records=records),indent=2)+'\n')
os._exit(0)
