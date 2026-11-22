"""Fit the source resistor directly to the CPU-side clock escape on the front copper."""
from pathlib import Path
import hashlib,json,math,shutil,subprocess
from collections import Counter
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((root/(n+'.json')).read_text())
entry=read('layout-emmc-data-power');reach=read('emmc-clock-front-reach');src=root/entry['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==reach['parent_sha256']==entry['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();v=lambda q:p.VECTOR2I(*q);uid=lambda o:o.m_Uuid.AsString()
res=b.FindFootprintByReference('R8004');host=b.FindFootprintByReference('U1').FindPadByNumber('M25')
for q in res.Pads():assert not b.GetConnectivity().GetConnectedTracks(q)
others=[f for f in b.GetFootprints() if f.GetReference()!='R8004']
near=[o for o in [*b.GetTracks(),*(q for f in others for q in f.Pads())] if inflated_box(o,9000000).Contains(host.GetPosition())]
courts=[f.GetCourtyard(p.F_Cu) for f in others if f.GetLayer()==p.F_Cu and inflated_box(f,9000000).Contains(host.GetPosition())]
front=[(o.GetNetCode(),o.GetEffectiveShape(p.F_Cu)) for o in near if o.IsOnLayer(p.F_Cu)]
holes=[o.GetEffectiveHoleShape() for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
res.Flip(res.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
pin=res.FindPadByNumber('1');other=res.FindPadByNumber('2')
stats=Counter();options=[]
for angle in (0,90,180,270):
    res.SetOrientationDegrees(angle)
    for row in reach['sites']:
        target=v(row['path_nm'][-1])
        for dx,dy in ((0,0),(100000,0),(-100000,0),(0,150000),(0,-150000)):
            res.Move(target+v((dx,dy))-pin.GetPosition())
            if not pin.HitTest(target):continue
            stats['terminations_with_contact']+=1
            cy=res.GetCourtyard(p.F_Cu)
            if any(cy.Collide(c,100000) for c in courts):continue
            stats['legal_courtyard']+=1
            if any(q.GetEffectiveShape(p.F_Cu).Collide(sh,202000) for q in res.Pads() for code,sh in front if q.GetNetCode()!=code):continue
            if any(q.GetEffectiveShape(p.F_Cu).Collide(h,252000) for q in res.Pads() for h in holes):continue
            options.append((row['cost_nm'],tuple(res.GetPosition()),angle,row['path_nm']))
folder=root/'runs/emmc-clock-front-termination';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
winner=None;attempted=[]
for cost,xy,angle,path in sorted(options)[:20]:
    trial=p.LoadBoard(str(src));f=trial.FindFootprintByReference('R8004');f.Flip(f.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT);f.SetOrientationDegrees(angle);f.SetPosition(v(xy))
    pts=[]
    for q in path:
        if len(pts)>1 and (q[0]-pts[-1][0])*(pts[-1][1]-pts[-2][1])==(q[1]-pts[-1][1])*(pts[-1][0]-pts[-2][0]):pts.pop()
        pts.append(q)
    for a,z in zip(pts,pts[1:]):trial.Add(make(trial,a,z,200000,host.GetNetCode(),p.F_Cu))
    out=folder/src.name;p.ZONE_FILLER(trial).Fill(trial.Zones());p.SaveBoard(str(out),trial)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));attempted.append(dict(position=xy,angle=angle,new_drc=delta))
    if delta:continue
    saved=p.LoadBoard(str(out));saved.BuildConnectivity()
    r=saved.FindFootprintByReference('R8004').FindPadByNumber('1');cpu=saved.FindFootprintByReference('U1').FindPadByNumber('M25')
    if uid(r) not in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(cpu)} or screen(saved):continue
    winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),new_drc=delta,position=xy,angle=angle,source_mm=cost/1e6,preservation=verify_preservation(p.LoadBoard(str(src)),saved));break
(root/'emmc-clock-front-termination.json').write_text(json.dumps(dict(parent_sha256=entry['sha256'],stats=stats,options=len(options),attempted=attempted,candidate=winner,assembly_ready=False),indent=2)+'\n')
print(stats,len(options),bool(winner))
