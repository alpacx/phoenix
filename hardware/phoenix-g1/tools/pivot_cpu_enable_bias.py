"""Pivot R1002 around its connected EN land and route its free supply land."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys
import pcbnew as p
from pcb_preservation import verify_preservation
from pcb_bounds import inflated_box
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'layout-exp-spi0-pullup.json').read_text());src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
prior=json.loads((src.parent/'drc.json').read_text());attempts=[];winner=None
for deg in (180,90,270):
    b=p.LoadBoard(str(src));f=b.FindFootprintByReference('R1002');q=f.FindPadByNumber('2');p0=q.GetPosition()
    f.SetOrientationDegrees(f.GetOrientationDegrees()+deg);f.Move(p0-q.GetPosition());side=f.GetLayer();court=f.GetCourtyard(side)
    conflicts=[other.GetReference() for other in b.GetFootprints() if other.GetReference()!='R1002' and other.GetLayer()==side and inflated_box(other,2500000).Contains(p0) and court.Collide(other.GetCourtyard(side),100000)]
    if conflicts:attempts.append(dict(angle=deg,bodies=conflicts));continue
    folder=root/'runs'/f'cpu-enable-pivot-{deg}';folder.mkdir(exist_ok=True);out=folder/src.name
    for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(prior,json.loads((folder/'drc.json').read_text()))
    if delta:attempts.append(dict(angle=deg,delta=delta));continue
    saved=p.LoadBoard(str(out));proof=verify_preservation(p.LoadBoard(str(src)),saved);assert not screen(saved)
    (root/'cpu-enable-pivot-input.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],sha256=hashlib.sha256(out.read_bytes()).hexdigest(),board=str(out.relative_to(root)),angle=deg,preservation=proof),indent=2)+'\n')
    subprocess.run([sys.executable,str(Path(__file__).with_name('connect_control_groups.py')),'--cpu-enable-pivot-route'],check=True,capture_output=True)
    r=json.loads((root/'cpu-enable-pivot-route.json').read_text());attempts.append(dict(angle=deg,routed=bool(r['records'])))
    if r['records']:
        winner=dict(r,angle=deg);break
(root/'cpu-enable-pivot-evaluation.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,attempts=attempts,assembly_ready=False),indent=2)+'\n')
print(attempts,flush=True);os._exit(0)
