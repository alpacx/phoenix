"""Open J3.23's through-via corridor by a local In2 reroute of the adjacent GPIO."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'layout-wifi-io-pullup-bank.json').read_text());src=root/base['board']
window=json.loads((root/'exp-sda-launch-window.json').read_text())
assert hashlib.sha256(src.read_bytes()).hexdigest()==window['parent_sha256']==base['sha256']
prior=json.loads((src.parent/'drc.json').read_text())
folder=root/'runs/exp-sda-gpio1-rework';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
out=folder/src.name
rows=window['single_blocker_windows']['EXP_GPIO1'];attempts=[];winner=None
for row in rows:
    at=tuple(row['point_nm']); uid,=row['touching']
    for dy in (200000,250000,300000,350000):
        b=p.LoadBoard(str(src));pin=b.FindFootprintByReference('J3').FindPadByNumber('23')
        old=next(t for t in b.GetTracks() if t.m_Uuid.AsString()==uid)
        a,z=tuple(old.GetStart()),tuple(old.GetEnd());assert old.GetNetname()=='EXP_GPIO1' and a[1]==z[1] and old.GetWidth()==200000
        code=old.GetNetCode();b.Remove(old)
        def line(aa,zz,net,layer):
            t=p.PCB_TRACK(b);t.SetWidth(200000);t.SetStart(p.VECTOR2I(*aa));t.SetEnd(p.VECTOR2I(*zz));t.SetNetCode(net);t.SetLayer(layer);b.Add(t)
        polygon=[a,(at[0]-600000-dy,a[1]),(at[0]-600000,a[1]-dy),(at[0]+600000,a[1]-dy),(at[0]+600000+dy,a[1]),z]
        for u,v in zip(polygon,polygon[1:]):line(u,v,code,p.In2_Cu)
        line(tuple(pin.GetPosition()),at,pin.GetNetCode(),p.F_Cu)
        via=p.PCB_VIA(b);via.SetPosition(p.VECTOR2I(*at));via.SetWidth(450000);via.SetDrill(200000);via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNetCode(pin.GetNetCode());b.Add(via)
        p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
        delta=introduced(prior,json.loads((folder/'drc.json').read_text()));attempts.append(dict(at=at,dy=dy,delta=delta))
        if any(r['type']!='via_dangling' for r in delta):continue
        saved=p.LoadBoard(str(out));saved.BuildConnectivity()
        if screen(saved):continue
        ids={o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('J3').FindPadByNumber('23'))}
        if via.m_Uuid.AsString() not in ids:continue
        proof=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper={uid})
        winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),site_nm=at,via_uuid=via.m_Uuid.AsString(),preservation=proof,new_drc=delta);break
    if winner:break
(root/'exp-sda-gpio1-launch.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,attempts=attempts,assembly_ready=False),indent=2)+'\n')
print(winner is not None,attempts[-1],flush=True);os._exit(0)
