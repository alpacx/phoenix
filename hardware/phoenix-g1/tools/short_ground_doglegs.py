"""Route short bent returns to existing ground vias; preserve all prior copper."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pcbnew as p
from pcb_preservation import verify_preservation
from pcb_bounds import inflated_box
from drc_regression import introduced
from audit_mount_component_reservations import screen

root = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/phy-power-parallel'
offset_mesh='--ground-land-offsets' in sys.argv
local_island_mesh='--island-mesh' in sys.argv
outer_mesh = '--outer-ground-mesh' in sys.argv
core_mesh = '--core-ground-mesh' in sys.argv or outer_mesh
all_ground = '--all-ground-surface' in sys.argv or core_mesh or local_island_mesh or offset_mesh
interior = '--package-local-vias' in sys.argv
perimeter = '--package-perimeter' in sys.argv or interior
surface = '--surface' in sys.argv or all_ground
stage = 'ground-land-offsets' if offset_mesh else 'island-mesh' if local_island_mesh else 'outer-ground-mesh' if outer_mesh else 'core-ground-mesh' if core_mesh else 'ground-all-local-surface' if all_ground else 'ground-package-local' if interior else 'ground-package-perimeter' if perimeter else 'ground-surface-bends' if surface else 'ground-doglegs'
prior = json.loads((root/('layout-memory-ground-neighbors.json' if offset_mesh else 'layout-island-returns.json' if local_island_mesh else 'outer-bga-ground.json' if outer_mesh else 'core-ground-interstitial.json' if core_mesh else 'layout-phy-full-feed.json' if all_ground else 'layout-package-returns.json' if interior else 'layout-ground-bends.json' if perimeter else 'ground-doglegs.json' if surface else 'layout-mdio-pullup.json')).read_text())
source = root/prior['board']
assert hashlib.sha256(source.read_bytes()).hexdigest() == prior['sha256']
board = p.LoadBoard(str(source))
board.BuildConnectivity()
def group(b):
    anchor = b.FindFootprintByReference('C511').FindPadByNumber('2')
    return {k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(anchor)}
ground = group(board)
vias = [v.GetPosition() for v in board.GetTracks() if isinstance(v,p.PCB_VIA) and v.m_Uuid.AsString() in ground]
pads = [q for f in board.GetFootprints() for q in f.Pads()]
added = []
for q in pads:
    f = q.GetParentFootprint()
    if offset_mesh and f.GetReference() not in {"U1","U2","U8001"}:continue
    if perimeter:
        if f.GetReference() not in {'U1','U2','U8001'}:
            continue
        centers=[k.GetPosition() for k in f.Pads() if k.GetNetCode()]
        x,y=q.GetPosition()
        if not interior and x not in (min(k.x for k in centers),max(k.x for k in centers)) and y not in (min(k.y for k in centers),max(k.y for k in centers)):
            continue
    if q.GetNetname() != 'GND' or q.m_Uuid.AsString() in ground or not all_ground and not perimeter and not f.GetReference().startswith(('C','Y','J2001','U22','U23')):
        continue
    layer = f.GetLayer()
    a = q.GetPosition()
    if core_mesh and (f.GetReference() not in ({'U1','U2','U8001'} if outer_mesh else {'U1'}) or not any(math.dist(tuple(a),tuple(v))<=1500000 for v in vias)):continue
    near = [v for v in vias if math.dist(tuple(a),tuple(v)) <= 1900000]
    if interior:
        near=[v for v in near if math.dist(tuple(a),tuple(v))<=1100000]
    if surface:
        near=[]
        for target in pads+list(board.GetTracks()):
            if target.m_Uuid.AsString() not in ground or not target.IsOnLayer(layer) or not inflated_box(target,2800000 if local_island_mesh else 1900000).Contains(a):
                continue
            if isinstance(target,p.PCB_TRACK):
                u,v=target.GetStart(),target.GetEnd()
                dx,dy=v-u
                fraction=max(0,min(1,((a.x-u.x)*dx+(a.y-u.y)*dy)/max(1,dx*dx+dy*dy)))
                near.append(p.VECTOR2I(round(u.x+fraction*dx),round(u.y+fraction*dy)))
            else:
                near.append(target.GetPosition())
    if not near:
        continue
    obstacles = [k.GetEffectiveShape(layer) for k in pads+list(board.GetTracks()) if k.IsOnLayer(layer) and k.GetNetCode()!=q.GetNetCode() and inflated_box(k,3500000 if local_island_mesh else 2500000).Contains(a)]
    holes = [k.GetEffectiveHoleShape() for k in pads+list(board.GetTracks()) if offset_mesh and
             (isinstance(k,p.PCB_VIA) or isinstance(k,p.PAD) and k.GetDrillSize().x) and k.GetNetCode()!=q.GetNetCode() and inflated_box(k,2500000).Contains(a)]
    def line(first,last):
        t=p.PCB_TRACK(board)
        t.SetStart(first);t.SetEnd(last);t.SetWidth(500000 if local_island_mesh else 300000);t.SetNetCode(q.GetNetCode());t.SetLayer(layer)
        return t
    options=[]
    offsets=(-100000,-50000,0,50000,100000) if offset_mesh else (-150000,0,150000)
    for dx in offsets:
        for dy in offsets:
            start=a+p.VECTOR2I(dx,dy)
            if not q.HitTest(start):
                continue
            for end in near:
                x,y=end-start
                diagonal=min(abs(x),abs(y))
                diagonal=p.VECTOR2I(int(math.copysign(diagonal,x)),int(math.copysign(diagonal,y)))
                for corner in (start+diagonal,end-diagonal):
                    points=[start,corner,end]
                    segments=[line(u,v) for u,v in zip(points,points[1:]) if u!=v]
                    length=sum(t.GetLength() for t in segments)
                    if segments and length<=(2800000 if local_island_mesh else 1900000) and all(not t.GetEffectiveShape(layer).Collide(s,200000) for t in segments for s in obstacles) and all(not t.GetEffectiveShape(layer).Collide(h,252000) for t in segments for h in holes):
                        options.append((length,segments))
    if not options:
        continue
    length,segments=min(options,key=lambda entry:entry[0])
    for t in segments:board.Add(t)
    if all_ground:
        board.BuildConnectivity()
        ground=group(board)
        assert q.m_Uuid.AsString() in ground
    added.append((f.GetReference(),q.GetNumber(),length/1e6))
out=root/'runs'/stage/source.name
out.parent.mkdir(exist_ok=True)
for n in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):shutil.copy2(source.parent/n,out.parent/n)
p.ZONE_FILLER(board).Fill(board.Zones())
p.SaveBoard(str(out),board)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out.parent/'drc.json'),str(out)],check=True,capture_output=True)
report=lambda path:json.loads(path.with_name('drc.json').read_text())
delta=introduced(report(source),report(out))
assert not delta,delta
saved=p.LoadBoard(str(out))
pres=verify_preservation(p.LoadBoard(str(source)),saved)
assert not screen(saved)
ground=group(saved)
for ref,num,length in added:
    assert saved.FindFootprintByReference(ref).FindPadByNumber(num).m_Uuid.AsString() in ground
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=prior['sha256'],added=added,preservation=pres,assembly_ready=False),indent=2)+'\n')
print(added,flush=True)
os._exit(0)
