"""Verify the integrated mechanical and electrical checkpoint on a freshly loaded PCB."""
import hashlib,json,os
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from audit_mount_component_reservations import screen
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def checkpoint(file):
    c=json.loads((root/file).read_text());path=root/c['board']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==c['sha256']
    return path
import sys
final='--trunk' in sys.argv
start=checkpoint('c522-verified.json');end=checkpoint('rear-bias-trunk.json' if final else 'sense-filter-return.json')
base=p.LoadBoard(str(start));saved=p.LoadBoard(str(end))
# The two replaced supply segments were first added after the source checkpoint.
pres=verify_preservation(base,saved)
def connected(b,one,two):
    def pad(name):
        ref,num=name.split('.')
        return b.FindFootprintByReference(ref).FindPadByNumber(num)
    return pad(two).m_Uuid.AsString() in {t.m_Uuid.AsString() for t in b.GetConnectivity().GetConnectedItems(pad(one))}
pairs=[('C511.1','C522.1'),('U5.38','C522.1'),('C511.2','C522.2'),('R530.2','C515.1'),('R521.1','R510.2'),('TP14.1','U17.4'),('TP9.1','U16.2'),('TP5.1','C465.1'),('R1505.1','C2007.1'),('R1505.2','R1506.1'),('R1505.2','C1503.1'),('C1503.2','C511.2'),('R1506.2','C511.2')]
pairs.extend(('C515.1',f'{r}.2') for r in ['R514','R521','R525','R526','R527'])
assert all(connected(saved,*pair) for pair in pairs)
negative=[];held=[]
for ref,dest in [('TP14','U17.4'),('TP5','C465.1'),('TP9','U16.2'),('R526','C515.1'),('R527','C515.1')]:
    b=p.LoadBoard(str(end));f=b.FindFootprintByReference(ref);n='2' if ref.startswith('R') else '1';q=f.FindPadByNumber(n)
    items=[t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetLayer()==f.GetLayer() and t.GetNetCode()==q.GetNetCode() and any(q.HitTest(pos) for pos in (t.GetStart(),t.GetEnd()))]
    for t in items:b.Remove(t);held.append(t)
    b.BuildConnectivity();lost=not connected(b,ref+'.'+n,dest)
    assert connected(b,'C511.1','C522.1') and connected(b,'R530.2','C515.1')
    if final:assert lost and items
    negative.append(dict(pad=ref+'.'+n,removed_tracks=len(items),disconnection_detected=lost))
def mounts(b):return {(r['reservation'],r['ref']) for r in screen(b)}
before,after=mounts(base),mounts(saved);assert after<=before
delta=introduced(json.loads((start.parent/'drc.json').read_text()),json.loads((end.parent/'drc.json').read_text()))
assert not delta
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru'):
    assert (start.parent/file).read_bytes()==(end.parent/file).read_bytes()
def hashfile(path):return hashlib.sha256(path.read_bytes()).hexdigest()
rep=dict(board=str(end.relative_to(root)),sha256=hashfile(end),parent_sha256=hashfile(start),verified_pairs=pairs,cut_tests=negative,preservation=pres,new_drc=delta,resolved_mount_conflicts=sorted(before-after),remaining_mount_conflicts=sorted(after),soc_sense_pin_connected=connected(saved,'U1.1P14','R1505.2'),production_qualified=False)
(root/('integrated-fixture-trunk.json' if final else 'integrated-fixture-bias.json')).write_text(json.dumps(rep,indent=2)+'\n')
print(len(before),len(after),len(pairs),negative,pres,flush=True);os._exit(0)
