"""Verify saved copper and challenge the two via arrays in the upstream PHY feed."""
import hashlib,json,os
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
name='phy-joint.kicad_pcb'
base=root/'runs/input-ground-local-002'
folder=root/'runs/phy-bulk-corridor-In2.Cu-east'
path=folder/name
b=p.LoadBoard(str(path))
old=p.LoadBoard(str(base/name))
removed=json.loads((root/'r530-output-array.json').read_text())[0]['preservation']['explicitly_replaced_copper']
preserved=verify_preservation(old,b,replaced_copper=removed)
def connected(board):
    board.BuildConnectivity()
    q=board.FindFootprintByReference('R530').FindPadByNumber('2')
    dest=board.FindFootprintByReference('C515').FindPadByNumber('1')
    return dest.m_Uuid.AsString() in {t.m_Uuid.AsString() for t in board.GetConnectivity().GetConnectedItems(q)}
arrays=[[(54.61,26.675),(55.11,27.05)],[(62.015,24.60),(62.575,24.60)]]
tests=[]
held=[]
for pair in arrays:
    for points in ([pair[0]],[pair[1]],pair):
        board=p.LoadBoard(str(path))
        keys={tuple(p.FromMM(x) for x in xy) for xy in points}
        vias=[v for v in board.GetTracks() if isinstance(v,p.PCB_VIA) and tuple(v.GetPosition()) in keys and v.GetNetname()=='+3V3_PHY']
        assert len(vias)==len(points)
        for v in vias:
            assert v.GetWidth(p.F_Cu)==600000 and v.GetDrillValue()==300000
            board.Remove(v)
            held.append(v)
        actual=connected(board)
        assert actual==(len(points)==1)
        tests.append(dict(removed_mm=points,connected=actual))
def mounts(board):
    return {(r['reservation'],r['ref']) for r in screen(board)}
conflicts=sorted(mounts(b)-mounts(old))
delta=introduced(json.loads((base/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
inner=[t for t in b.GetTracks() if t.GetLayer()==p.In2_Cu and t.GetNetname()=='+3V3_PHY' and t.GetClass()=='PCB_TRACK']
assert inner and all(t.GetWidth()==1050000 for t in inner)
assert not conflicts and not delta and connected(b)
report=dict(board=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_sha256=hashlib.sha256((base/name).read_bytes()).hexdigest(),preservation=preserved,via_tests=tests,new_mount_conflicts=conflicts,new_drc=delta,connected=True,inner_length_mm=sum(p.ToMM(t.GetLength()) for t in inner),inner_width_mm=1.05,power_layout_accepted=False,assembly_ready=False,holds=['Input feed geometry only. Review DC drop, PI and long routing, oscillator supply/return, via overlap with capacitor pad and fabrication process.','Local regulator and pin fanout, effective capacitance, compact inductor and C522 remain open.'])
(root/'phy-upstream-verified.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['inner_length_mm'],len(tests),flush=True)
os._exit(0)
