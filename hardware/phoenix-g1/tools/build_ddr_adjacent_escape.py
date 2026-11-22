"""Trial a simultaneous two-ball fanout while preserving all other pad connectivity."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import os
import shutil
import subprocess
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-ground-island-barrels.json').read_text())
src=root/meta['board']
review=json.loads((root/'ddr-restore-neighbor.json').read_text())
assert meta['sha256']==hashlib.sha256(src.read_bytes()).hexdigest()==review['source_sha256']
row=next((r for r in review['rows'] if r['path_nm']),None)
if row is None:raise SystemExit('No paired escape meeting the hole clearance on the current PCB')
b=p.LoadBoard(str(src))
b.BuildConnectivity()
original=b.FindFootprintByReference('U1').FindPadByNumber(row['restored_ball'])
group={i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(original)}
cut=[k for k in b.GetTracks() if k.m_Uuid.AsString() in group]
assert len([v for v in cut if isinstance(v,p.PCB_VIA)])==1
assert all(k.GetNetname()==row['net'] and (isinstance(k,p.PCB_VIA) or k.GetLayer()==p.F_Cu) for k in cut)
for k in cut:b.Remove(k)
for net,points in [(row['net'],row['path_nm']),(row['missing'],row['missing_path_nm'])]:
    # Collapse contiguous runs on the same grid direction.
    pts=[points[0]]
    previous=None
    for a,z in zip(points,points[1:]):
        d=(z[0]-a[0],z[1]-a[1])
        if previous is not None and d!=previous:pts.append(a)
        previous=d
    pts.append(points[-1])
    for u,z in zip(pts,pts[1:]):
        t=p.PCB_TRACK(b)
        t.SetNetCode(b.GetNetcodeFromNetname(net))
        t.SetWidth(100000)
        t.SetLayer(p.F_Cu)
        t.SetStart(p.VECTOR2I(*u))
        t.SetEnd(p.VECTOR2I(*z))
        b.Add(t)
    v=p.PCB_VIA(b)
    v.SetViaType(p.VIATYPE_THROUGH)
    v.SetLayerPair(p.F_Cu,p.B_Cu)
    v.SetPosition(p.VECTOR2I(*pts[-1]))
    v.SetNetCode(b.GetNetcodeFromNetname(net))
    v.SetWidth(450000)
    v.SetDrill(200000)
    b.Add(v)
folder=root/'runs/ddr-adjacent-escape'
folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
    shutil.copy2(src.parent/name,folder/name)
out=folder/src.name
p.ZONE_FILLER(b).Fill(b.Zones())
p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
load_counts=lambda d:Counter(v['type'] for v in json.loads((d/'drc.json').read_text())['violations'] if v.get('severity') in ('error','warning'))
counts=load_counts(folder)
old_counts=load_counts(src.parent)
saved=p.LoadBoard(str(out))
saved.BuildConnectivity()
pres=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper={k.m_Uuid.AsString() for k in cut})
assert not screen(saved)
via_ids={k.m_Uuid.AsString() for k in saved.GetTracks() if isinstance(k,p.PCB_VIA)}
ends=[]
for net in (row['missing'],row['net']):
    ep=[]
    for ref in ('U1','U2'):
        q=next(q for q in saved.FindFootprintByReference(ref).Pads() if q.GetNetname()==net)
        ids={k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(q)} & via_ids
        assert len(ids)==1
        ep.append(tuple(next(k for k in saved.GetTracks() if k.m_Uuid.AsString() in ids).GetPosition()))
    ends.append(dict(net=net,via_nm=ep))
r=dict(source_sha256=meta['sha256'],sha256=hashlib.sha256(out.read_bytes()).hexdigest(),board=str(out.relative_to(root)),is_experiment=True,adopted=False,ends=ends,before_counts=dict(old_counts),after_counts=dict(counts),preservation=pres)
(root/'ddr-adjacent-escape.json').write_text(json.dumps(r,indent=2)+'\n')
print(ends,old_counts,counts,flush=True)
os._exit(0)
