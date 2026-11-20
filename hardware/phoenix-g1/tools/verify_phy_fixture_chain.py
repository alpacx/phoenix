"""Reload the cumulative board and check power, RX bias and fixture continuity."""
import hashlib,json,os
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def checked(filename):
    cp=json.loads((root/filename).read_text())
    path=root/cp['board']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==cp['sha256']
    return path
src=checked('c522-verified.json')
dest=checked('fixture-vias-verified.json')
old=p.LoadBoard(str(src));b=p.LoadBoard(str(dest));pres=verify_preservation(old,b)
def linked(a,z):
    def pad(s):
        r,n=s.split('.')
        return b.FindFootprintByReference(r).FindPadByNumber(n)
    return pad(z).m_Uuid.AsString() in {o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(pad(a))}
pairs=[('R530.2','C515.1'),('C511.1','C522.1'),('C522.1','U5.38'),('C522.2','C511.2'),('R521.1','R510.2'),('TP14.1','U17.4'),('TP9.1','U16.2'),('TP5.1','C465.1')]
pairs.extend(('C515.1',f'{r}.2') for r in ('R514','R521','R525','R527'))
assert all(linked(*pair) for pair in pairs)
assert not linked('C515.1','R526.2')
def mounts(board):return {(r['reservation'],r['ref']) for r in screen(board)}
before,after=mounts(old),mounts(b)
assert after<=before
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((dest.parent/'drc.json').read_text()))
assert not delta
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru'):
    assert (src.parent/file).read_bytes()==(dest.parent/file).read_bytes()
report=dict(board=str(dest.relative_to(root)),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),preservation=pres,verified_pad_pairs=pairs,new_drc=delta,mount_conflicts_before=len(before),mount_conflicts_after=len(after),resolved_mount_conflicts=sorted(before-after),remaining_mount_conflicts=sorted(after),assembly_ready=False)
(root/'phy-fixture-checkpoint.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['mount_conflicts_before'],report['mount_conflicts_after'],report['preservation'],flush=True);os._exit(0)
