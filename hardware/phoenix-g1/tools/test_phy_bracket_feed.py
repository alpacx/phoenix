"""Test the least intrusive available bracket shift before adopting any mechanical change."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'layout-opposite-bypass.json').read_text())
options=json.loads((root/'phy-bracket-freedom.json').read_text())
assert options['source_sha256']==cp['sha256']
src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));hole=b.FindFootprintByReference('H8105')
zone=next(z for z in b.Zones() if z.GetZoneName()=='H8105 mechanical reservation')
pos=p.VECTOR2I(*options['positions'][0]['center_nm']);shift=pos-hole.GetPosition()
assert 0<shift.EuclideanNorm()<=300000
hole.Move(shift);zone.Move(shift)
folder=root/'runs/phy-bracket-trial';folder.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved);assert not screen(saved)
if delta:out=src
(root/'phy-bracket-trial.json').write_text(json.dumps(dict(board=str(out.relative_to(root)),parent_sha256=cp['sha256'],sha256=hashlib.sha256(out.read_bytes()).hexdigest(),position_trial_nm=tuple(pos),new_drc=delta,preservation=pres,assembly_ready=False),indent=2)+'\n')
print(len(delta),flush=True);os._exit(0)
