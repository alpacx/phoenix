"""Carry the qualified hole geometry into the routed PHY study without replacing the parent."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
ex=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments'
root=ex/'phy-power-parallel'
cp=json.loads((root/'integrated-fixture-trunk.json').read_text());src=root/cp['board']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert digest(src)==cp['sha256']
donor=ex/'mechanical-clearance-parallel/h8105-hole.kicad_pcb'
assert digest(donor)==json.loads((donor.parent/'hole-checkpoint.json').read_text())['sha256']
orig=p.LoadBoard(str(src));b=p.LoadBoard(str(src));m=p.LoadBoard(str(donor))
r=b.FindFootprintByReference('R2014');rf=m.FindFootprintByReference('R2014')
assert r.GetLayer()==rf.GetLayer()
r.SetPosition(rf.GetPosition());r.SetOrientationDegrees(rf.GetOrientationDegrees())
assert not b.FindFootprintByReference('H8105')
hole=m.FindFootprintByReference('H8105').Duplicate(False);b.Add(hole)
folder=root/'runs/reconciled-mount';folder.mkdir(exist_ok=True)
for f in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/f,folder/f)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
saved=p.LoadBoard(str(out));delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
hole=saved.FindFootprintByReference('H8105');pad,=list(hole.Pads())
assert pad.GetAttribute()==p.PAD_ATTRIB_NPTH and tuple(pad.GetDrillSize())==(2200000,2200000) and tuple(pad.GetPosition())==(70000000,34000000)
def conflicts(board):return {(r['reservation'],r['ref']) for r in screen(board)}
after=conflicts(saved);assert after<conflicts(orig)
assert not delta,delta
proof=verify_preservation(orig,saved)
result=dict(board=str(out.relative_to(root)),sha256=digest(out),parent_sha256=cp['sha256'],remaining=sorted(after),new_drc=delta,preservation=proof,assembly_ready=False)
(root/'reconciled-mount.json').write_text(json.dumps(result,indent=2)+'\n')
print(len(after),proof,flush=True);os._exit(0)
