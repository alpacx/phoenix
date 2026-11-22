"""Reload the selected cumulative layout, verify saved pad pairs and cut the two PMIC bus branches."""
from collections import defaultdict,Counter
import hashlib,json,os
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def read(stem):return json.loads((root/(stem+'.json')).read_text())
def load(cp):
    path=root/cp['board']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==cp['sha256']
    b=p.LoadBoard(str(path));b.BuildConnectivity();return b
def pad(b,s):
    r,n=s.split('.');f=b.FindFootprintByReference(r)
    assert hasattr(f,'FindPadByNumber'),(r,n,type(f),b.GetFileName())
    return f.FindPadByNumber(n)
def connected(b,a,z):
    return pad(b,z).m_Uuid.AsString() in {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(pad(b,a))}
import sys,subprocess
if '--cut' in sys.argv:
    _,_,stage,a,z,checkpoint=sys.argv
    probe=load(read(checkpoint))
    rec=next(r for r in read(stage)['records'] if r['pair']==[a,z])
    ids=set(rec['added'])
    via=next(t for t in probe.GetTracks() if t.m_Uuid.AsString() in ids and isinstance(t,p.PCB_VIA))
    probe.Remove(via);probe.BuildConnectivity()
    assert not connected(probe,a,z)
    assert connected(probe,'R530.2','C515.1') and connected(probe,'C511.1','U5.38')
    os._exit(0)
expanded='--storage-and-io' in sys.argv
checkpoint='control-groups' if expanded else 'emmc-distribution'
base=read('layout-reset-connectivity');cp=read(checkpoint);before=load(base);b=load(cp)
replaced=read('pmic-sda-clearance')['change']['preservation']['explicitly_replaced_copper']
pres=verify_preservation(before,b,replaced_copper=replaced);assert not screen(b)
pairs=list(base['verified_pairs'])
for stage in ['off-pad-services','perimeter-controls','sda-link','header-signals','emmc-distribution']:
    pairs.extend(r['pair'] for r in read(stage)['records'])
if expanded:
    for stage in ('emmc-trunks','bias-feeds','control-groups'):
        pairs.extend(row['pair'] for row in read(stage)['records'])
    pairs.extend([r['ref']+'.'+r['pad'],'C511.2'] for r in read('storage-ground')['added'])
pairs.extend([['R1507.2','U16.2'],['R1504.1','TP10.1']])
pairs.extend([r['ref']+'.'+r['pad'],'C511.2'] for r in read('surface-ground')['added'])
pairs=sorted({tuple(sorted(pair)) for pair in pairs})
for a,z in pairs:assert connected(b,a,z),(a,z)
cut=[]
for stage,pair in [('perimeter-controls',['U4.1','R414.2']),('sda-link',['U4.2','R415.2'])]:
    subprocess.run([sys.executable,__file__,'--cut',stage,*pair,checkpoint],check=True)
    cut.append(pair)
nets=defaultdict(list)
for f in b.GetFootprints():
    for q in f.Pads():
        if q.GetNetCode() and q.GetNumber():nets[q.GetNetname()].append((f.GetReference()+'.'+q.GetNumber(),q))
unresolved={}
for net,qp in nets.items():
    seen=set();groups=[]
    for name,q in qp:
        if q.m_Uuid.AsString() in seen:continue
        ids={k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(q)}|{q.m_Uuid.AsString()}
        seen.update(ids);groups.append(sorted(name for name,k in qp if k.m_Uuid.AsString() in ids))
    if len(groups)>1:unresolved[net]=groups
def drc(cp):return json.loads(((root/cp['board']).parent/'drc.json').read_text())
report=drc(cp);delta=introduced(drc(base),report);assert not delta
audit=dict(board=cp['board'],sha256=cp['sha256'],parent_sha256=base['sha256'],verified_pairs=pairs,pmic_removed_branch_tests=cut,preservation=pres,open_nets=unresolved,remaining_minimum_joins=sum(len(g)-1 for g in unresolved.values()),drc_counts=Counter(v['type'] for v in report['violations']),new_drc=delta,assembly_ready=False)
(root/('layout-storage-io.json' if expanded else 'layout-pmic-bus.json')).write_text(json.dumps(audit,indent=2)+'\n')
print(len(pairs),len(unresolved),audit['remaining_minimum_joins'],audit['drc_counts'],flush=True);os._exit(0)
