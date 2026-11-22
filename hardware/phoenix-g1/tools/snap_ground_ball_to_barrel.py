"""Reuse a newly placed grounded via instead of drilling near an existing barrel."""
from pathlib import Path
from collections import Counter
import json,hashlib,math,shutil,subprocess
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from pcb_power_leg import make
from pcb_bounds import inflated_box
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';base=json.loads((r/'layout-npu-local-bypass.json').read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
def pad(board,n):
    ref,num=n.split('.');return board.FindFootprintByReference(ref).FindPadByNumber(num)
def group(board,n):return {o.m_Uuid.AsString() for o in board.GetConnectivity().GetConnectedItems(pad(board,n))}
old_db=json.loads((src.parent/'drc.json').read_text());gids=group(b,'U4.69')
returns=[tuple(t.GetPosition()) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in gids]
out=r/'runs/bga-reused-ground';out.mkdir(exist_ok=True,parents=True);file=out/src.name
for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table')
def save():
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(file)],capture_output=True,check=True)
    return json.loads((out/'drc.json').read_text())
remaining={q for g in base['open_nets']['GND'] if 'U4.69' not in g for q in g}
proof=[];joins=base['remaining_minimum_joins'];accepted=[]
for name in sorted(remaining):
    fn=r/('bga-ground-qualified-'+name+'.json')
    if not fn.exists():continue
    dataset=json.loads(fn.read_text())
    q=pad(b,name);side=q.GetParentFootprint().GetLayer();code=q.GetNetCode()
    options=[]
    for v in dataset['sites']:
        pts=[tuple(xy) for xy in v['path_nm']]
        for via in returns:
            dist=math.dist(pts[-1],via)
            if dist>700000:continue
            path=pts+([via] if pts[-1]!=via else [])
            points=[]
            for x in path:
                if len(points)>1:
                    a,z=points[-2:]
                    if (x[0]-z[0])*(z[1]-a[1])==(x[1]-z[1])*(z[0]-a[0]):points.pop()
                points.append(x)
            options.append((sum(math.dist(i,j) for i,j in zip(points,points[1:])),points,via))
    tries=[]
    for _,points,via in sorted(options)[:8]:
        ts=[make(b,i,j,200000,code,side) for i,j in zip(points,points[1:]) if i!=j]
        for t in ts:b.Add(t)
        db=save();fresh=p.LoadBoard(str(file));fresh.BuildConnectivity();diff=introduced(old_db,db)
        good=pad(fresh,name).m_Uuid.AsString() in group(fresh,'U4.69')
        tries.append(dict(path=points,delta=diff,physically_grounded=good))
        if not diff and good and len(db['unconnected_items'])<joins:
            joins=len(db['unconnected_items']);accepted.append(name);break
        for t in ts:b.Remove(t)
    proof.append(dict(name=name,candidates=len(options),trials=tries))
db=save();fresh=p.LoadBoard(str(file));fresh.BuildConnectivity()
report=dict(parent_sha256=base['sha256'],trials=proof,accepted=accepted,remaining=len(db['unconnected_items']))
if accepted:
    gset=group(fresh,'U4.69');nets=base['open_nets'].copy();gs=nets['GND'];main=next(g for g in gs if 'U4.69' in g);joins=[g for g in gs if g!=main and pad(fresh,g[0]).m_Uuid.AsString() in gset]
    nets['GND']=[g for g in gs if g!=main and g not in joins]+[sorted(main+[n for g in joins for n in g])]
    assert sum(len(g)-1 for g in nets.values())==report['remaining'] and not introduced(old_db,db)
    pairs=sorted({tuple(sorted(p)) for p in base['verified_pairs']}|{tuple(sorted((n,'U4.69'))) for n in accepted})
    cache={}
    for a,z in pairs:
        if a not in cache:cache[a]=group(fresh,a)
        assert pad(fresh,z).m_Uuid.AsString() in cache[a]
    cp=dict(board=str(file.relative_to(r)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),parent_sha256=base['sha256'],verified_pairs=pairs,preservation=verify_preservation(p.LoadBoard(str(src)),fresh),open_nets=nets,remaining_minimum_joins=report['remaining'],new_drc=[],drc_counts=dict(Counter(x['type'] for x in db['violations'])),assembly_ready=False)
    (r/'layout-reused-ground-barrels.json').write_text(json.dumps(cp,indent=2)+'\n')
(r/'bga-reused-ground-barrels.json').write_text(json.dumps(report,indent=2)+'\n');print(accepted,report['remaining'])
