"""Report real connected pad groups and validate every named endpoint after reload."""
from collections import defaultdict
import hashlib,json,os
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def report(name):return json.loads((root/(name+'.json')).read_text())
def board(name):
    cp=report(name);path=root/cp['board']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==cp['sha256']
    return p.LoadBoard(str(path))
import sys
reset='--before-reset' not in sys.argv
stage='reset-pull-feed' if reset else 'cap-edge-ground'
before=board('pmic-control-bus');after=board(stage)
preservation=verify_preservation(before,after)
def inventory(b):
    b.BuildConnectivity();nets=defaultdict(list)
    for f in b.GetFootprints():
        for q in f.Pads():
            if q.GetNetCode() and q.GetNumber():nets[q.GetNetname()].append((f.GetReference()+'.'+q.GetNumber(),q))
    open_nets={}
    for n,pads in nets.items():
        if len(pads)<2:continue
        seen=set();groups=[]
        for label,q in pads:
            uid=q.m_Uuid.AsString()
            if uid in seen:continue
            connected={i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(q)}|{uid}
            groups.append(sorted(s for s,k in pads if k.m_Uuid.AsString() in connected));seen.update(connected)
        if len(groups)>1:open_nets[n]=groups
    return open_nets
original=inventory(before);current=inventory(after)
pairs=report('reconciled-c1623')['verified_pairs']+report('integrated-fixture-trunk')['verified_pairs']+[i['pair'] for i in report('low-speed-links')['accepted']]+[['U1.1B11','U2.T11'],['R201.1','U2.A5']]
for part in ('cap-returns-verified','cap-existing-vias','res-returns-verified','fixture-clocks-ground','cap-edge-ground'):
    pairs += [[i['ref']+'.'+i['pad'],'C511.2'] for i in report(part)['added']]
if reset:pairs.extend([['R412.2','C411.1'],['R412.1','R416.1']])
def get(s):
    r,n=s.split('.');return after.FindFootprintByReference(r).FindPadByNumber(n)
pairs=sorted(set(tuple(sorted(v)) for v in pairs))
for a,z in pairs:assert get(z).m_Uuid.AsString() in {k.m_Uuid.AsString() for k in after.GetConnectivity().GetConnectedItems(get(a))},(a,z)
assert not screen(after)
cp=report(stage)
data=dict(board=cp['board'],sha256=cp['sha256'],verified_pairs=pairs,preservation=preservation,original_minimum_joins=sum(len(g)-1 for g in original.values()),remaining_minimum_joins=sum(len(g)-1 for g in current.values()),open_nets=current,assembly_ready=False)
(root/('layout-reset-connectivity.json' if reset else 'layout-connectivity.json')).write_text(json.dumps(data,indent=2)+'\n')
print(len(pairs),len(current),data['original_minimum_joins'],data['remaining_minimum_joins'],flush=True);os._exit(0)
