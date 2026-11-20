"""Challenge the complete, serialized upstream and local-PHY geometry."""
import hashlib,json,os
from pathlib import Path
import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
src=root/'runs/phy-bulk-corridor-In2.Cu-east'
dst=root/'runs/c522-joint-bypass'
name='phy-joint.kicad_pcb'
base=p.LoadBoard(str(src/name))
board=p.LoadBoard(str(dst/name))
def conn(b,one,two):
    b.BuildConnectivity()
    def pad(t):return b.FindFootprintByReference(t[0]).FindPadByNumber(t[1])
    return pad(two).m_Uuid.AsString() in {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(pad(one))}
checks=[(('C511','1'),('C522','1')),(('U5','38'),('C522','1')),(('C511','2'),('C522','2')),(('R530','2'),('C515','1'))]
assert all(conn(board,*pair) for pair in checks)
replaced=set()
for f in [root/'runs/c522-pin38-escape/report.json',root/'c522-joint-bypass.json']:
    replaced.update(json.loads(f.read_text())['preservation']['explicitly_replaced_copper'])
pres=verify_preservation(base,board,replaced_copper=replaced)
diff=introduced(json.loads((src/'drc.json').read_text()),json.loads((dst/'drc.json').read_text()))
def mounts(b):return {(v['reservation'],v['ref']) for v in screen(b)}
conflicts=sorted(mounts(board)-mounts(base))
held=[];cases=[]
array=[(64550000,34250000),(65099999,34250000)]
for removed in [[array[0]],[array[1]],array]:
    b=p.LoadBoard(str(dst/name))
    matched=[v for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and tuple(v.GetPosition()) in removed and v.GetNetname()=='+1V0_PHY']
    assert len(matched)==len(removed)
    for v in matched:
        assert v.GetWidth(p.F_Cu)==600000 and v.GetDrillValue()==300000
        b.Remove(v);held.append(v)
    cases.append(dict(removed_nm=removed,load_connected=conn(b,*checks[0])))
stats={}
for net in ('PHY_XIN','PHY_XOUT'):
    def length(b):
        return sum(p.ToMM(t.GetLength()) for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname()==net)
    stats[net]={'before_mm':length(base),'after_mm':length(board)}
result=json.loads((root/'c522-joint-bypass.json').read_text())
from math import dist
path=result['site']['power']
stats['distribution_mm']=sum(dist(a,z) for a,z in zip(path,path[1:]))
stats['local_pin_back_mm']=result['site']['pin_length']
stats['return_back_mm']=dist(result['site']['return_pad'],result['return_via_mm'])
assert [q['load_connected'] for q in cases]==[True,True,False]
assert not diff and not conflicts
rep=dict(metrics=stats,board=str((dst/name).relative_to(root)),sha256=hashlib.sha256((dst/name).read_bytes()).hexdigest(),preservation=pres,checks=checks,new_drc=diff,new_mount_conflicts=conflicts,via_cuts=cases,power_layout_accepted=False,assembly_ready=False)
(root/'c522-verified.json').write_text(json.dumps(rep,indent=2)+'\n')
print(cases,conflicts,diff,flush=True);os._exit(0)
