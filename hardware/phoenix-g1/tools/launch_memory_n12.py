"""Screen N12's two power barrels against the current board and rank interior bank access."""
import hashlib
import itertools
import json
import math
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make,barrel
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((r/(n+'.json')).read_text())
cp=read('layout-memory-zq-supply');src=r/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));original=p.LoadBoard(str(src));b.BuildConnectivity()
q=b.FindFootprintByReference('U2').FindPadByNumber('N12');code=q.GetNetCode()
uid=lambda x:x.m_Uuid.AsString()
bank=b.FindFootprintByReference('C1666').FindPadByNumber('1')
bankids={uid(i) for i in b.GetConnectivity().GetConnectedItems(bank)}
origin=tuple(q.GetPosition())
neighbours=[o for o in [*b.GetTracks(),*(pad for fp in b.GetFootprints() for pad in fp.Pads())] if inflated_box(o,8000000).Contains(q.GetPosition())]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
foreign={l:[o.GetEffectiveShape(l) for o in neighbours if o.GetNetCode()!=code and o.IsOnLayer(l)] for l in layers}
holes=[o.GetEffectiveHoleShape() for o in neighbours if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
lands=[o.GetEffectiveShape(o.GetParentFootprint().GetLayer()) for o in neighbours if isinstance(o,p.PAD)]
cases=next(row['access']['source_map'] for row in read('memory-perimeter-supply-current')['tested'] if row['ball']=='N12')
paths={}
for row in cases:
    at=tuple(row['pt_nm']);pts=[tuple(a) for a in row['route_nm']]
    assert q.HitTest(p.VECTOR2I(*pts[0]))
    via=barrel(b,at,code);sh=via.GetEffectiveShape(p.F_Cu);dr=via.GetEffectiveHoleShape()
    if any(sh.Collide(f,202000) or dr.Collide(f,252000) for fs in foreign.values() for f in fs):continue
    if any(sh.Collide(h,252000) or dr.Collide(h,252000) for h in holes):continue
    if any(sh.Collide(s,52000) for s in lands):continue
    tracks=[make(b,x,y,500000,code,p.F_Cu) for x,y in zip(pts,pts[1:]) if x!=y]
    if any(t.GetEffectiveShape(p.F_Cu).Collide(f,202000) for t in tracks for f in foreign[p.F_Cu]):continue
    if any(t.GetEffectiveShape(p.F_Cu).Collide(h,252000) for t in tracks for h in holes):continue
    paths[at]=pts
pairs=[]
for a,z in itertools.combinations(paths,2):
    gap=math.dist(a,z)
    if not 600000<=gap<=1050000:continue
    for layer in (p.In3_Cu,p.In2_Cu,p.B_Cu):
        tr=make(b,a,z,500000,code,layer);sh=tr.GetEffectiveShape(layer)
        if any(sh.Collide(s,202000) for s in foreign[layer]) or any(sh.Collide(h,252000) for h in holes):continue
        mid=tuple(round((x+y)/2) for x,y in zip(a,z))
        parts=[o for o in neighbours if uid(o) in bankids and o.IsOnLayer(layer) and not isinstance(o,p.PCB_VIA)]
        anchors=[tuple(x.GetPosition()) for x in parts if isinstance(x,p.PAD)]
        anchors.extend(tuple(point) for t in parts if not isinstance(t,p.PAD) and t.GetWidth()>=500000 for point in (t.GetStart(),t.GetEnd()))
        if not anchors:continue
        separation=min(math.dist(mid,point) for point in anchors)
        pairs.append((separation+.5*max(sum(math.dist(x,y) for x,y in zip(paths[at],paths[at][1:])) for at in (a,z)),a,z,layer))
folder=r/'runs/memory-n12-escape';folder.mkdir(exist_ok=True)
for ext in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/ext,folder/ext)
winner=None;attempts=[]
for _,a,z,layer in sorted(pairs):
    work=p.LoadBoard(str(src));placed=set();vias=[]
    for at in (a,z):
        via=barrel(work,at,code);work.Add(via);vias.append(uid(via))
        for x,y in zip(paths[at],paths[at][1:]):
            edge=tuple(sorted([x,y]))
            if x!=y and edge not in placed:
                work.Add(make(work,x,y,500000,code,p.F_Cu));placed.add(edge)
    tie=make(work,a,z,500000,code,layer);work.Add(tie)
    out=folder/src.name;p.ZONE_FILLER(work).Fill(work.Zones());p.SaveBoard(str(out),work)
    dr=folder/'drc.json'
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()))
    attempts.append(dict(pair=[a,z],new_drc=delta))
    if delta:continue
    saved=p.LoadBoard(str(out));saved.BuildConnectivity();pin=saved.FindFootprintByReference('U2').FindPadByNumber('N12')
    group={uid(t) for t in saved.GetConnectivity().GetConnectedItems(pin)}
    if not set(vias+[uid(tie)])<=group or screen(saved):continue
    winner=dict(board=str(out.relative_to(r)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),tie=uid(tie),vias=vias,via_nm=[a,z],layer=work.GetLayerName(layer),preservation=verify_preservation(original,saved));break
(r/'memory-n12-escape.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],screened_sites=len(paths),pair_layer_options=len(pairs),attempts=attempts,candidate=winner,assembly_ready=False),indent=2)+'\n')
print(len(paths),len(pairs),len(attempts),bool(winner))
