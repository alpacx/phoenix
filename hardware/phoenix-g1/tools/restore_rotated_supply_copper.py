"""Salvage native power copper around a rotated PMIC only where old pad groups rejoin."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def read(path):return json.loads(path.read_text())
def file_from(name):
    meta=read(root/(name+'.json'));path=root/meta['board'];assert meta['sha256']==hashlib.sha256(path.read_bytes()).hexdigest();return path
accepted=file_from('layout-pmic-pwron-filter');start=file_from('rotated-existing-scl-complete')
current=start
uid=lambda o:o.m_Uuid.AsString()
def partition(board):
    board.BuildConnectivity()
    parts={uid(q):f.GetReference()+'.'+q.GetNumber() for f in board.GetFootprints() for q in f.Pads() if q.GetNumber() and q.GetNetCode()}
    by={uid(q):q for f in board.GetFootprints() for q in f.Pads() if uid(q) in parts}
    result={}
    for key in by:
        if key in result:continue
        group=frozenset(({uid(o) for o in board.GetConnectivity().GetConnectedItems(by[key])}|{key})&parts.keys())
        for other in group:result[other]=group
    return parts,result
original_board=p.LoadBoard(str(accepted));owners=[original_board]
old_parts,history=partition(original_board)
details=[]
for net,suffix in [('+3V3_SYS','system'),('+3V3_IO','io'),('GND','ground'),('PMIC_PWRON_N','pwron')]:
    old=p.LoadBoard(str(accepted));b=p.LoadBoard(str(current));prior=p.LoadBoard(str(current));owners.extend([old,b,prior]);labels,before=partition(prior)
    old_copper={uid(t):t for t in old.GetTracks() if t.GetNetname()==net}
    existing={uid(t) for t in b.GetTracks()}
    missing=set(old_copper)-existing
    if not missing:continue
    inserted={}
    owners.append(old_copper)
    for key in missing:
        t=old_copper[key];old.Remove(t);b.Add(t);assert t.GetNetname()==net;inserted[key]=t
    folder=root/'runs'/('rotated-recovered-original-'+suffix);folder.mkdir(exist_ok=True)
    for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(current.parent/name,folder/name)
    out=folder/current.name;base_drc=read(current.parent/'drc.json')
    def drc():
        p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
        return introduced(base_drc,read(folder/'drc.json'))
    passes=[]
    for trial in range(25):
        delta=drc()
        if not delta:break
        offenders={key for i in delta for key in i['items'] if key in inserted}
        if not offenders:break
        passes.append(dict(types=sorted({i['type'] for i in delta}),discarded=len(offenders)))
        for key in offenders:b.Remove(inserted.pop(key))
    if delta:
        details.append(dict(net=net,held=delta,passes=passes));continue
    labels,after=partition(b)
    # Extract only copper islands which recover an original physical pad bond.
    restored_groups={g for key,g in after.items() if any(len(history.get(key,set()) & g)>len(history.get(key,set()) & before[key]) for key in g)}
    useful=set()
    for key,t in inserted.items():
        pads={uid(i) for i in b.GetConnectivity().GetConnectedItems(t)} & labels.keys()
        if any(pads & group for group in restored_groups):useful.add(key)
    for key in set(inserted)-useful:b.Remove(inserted.pop(key))
    if not inserted:
        details.append(dict(net=net,candidates=len(missing),retained=[],passes=passes));continue
    delta=drc()
    if delta:
        details.append(dict(net=net,held=delta,passes=passes));continue
    saved=p.LoadBoard(str(out));owners.append(saved);guard=verify_preservation(prior,saved)
    _,new=partition(saved)
    reunited=[]
    for group in set(history.values()):
        clusters_old={before[id] for id in group};clusters_new={new[id] for id in group}
        if len(clusters_new)<len(clusters_old):
            reunited.append(dict(prior_fragments=len(clusters_old),new_fragments=len(clusters_new),members=sorted({labels[id] for id in group})))
    if not reunited:continue
    rec=dict(net=net,candidates=len(missing),retained=sorted(inserted),reunited=reunited,passes=passes,preserved_groups=guard['existing_connected_pad_groups_preserved'],board_sha256=hashlib.sha256(out.read_bytes()).hexdigest())
    meta=read(current.parent/'output-legs.json');meta['board_sha256']=rec['board_sha256'];meta['restored_'+suffix]=rec;(folder/'output-legs.json').write_text(json.dumps(meta,indent=2)+'\n')
    details.append(rec);current=out;print(net,'retained',len(inserted),'reunited',len(reunited),flush=True)
(root/'rotated-supply-copper-recovery.json').write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),parent_sha256=hashlib.sha256(start.read_bytes()).hexdigest(),results=details,assembly_ready=False),indent=2)+'\n')
print([(r['net'],len(r.get('retained',[])),len(r.get('held',[]))) for r in details],flush=True);os._exit(0)
