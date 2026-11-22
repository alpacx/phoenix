"""Refill and test individual ordinary ground vias off the BGA lands, then verify cumulative groups."""
from pathlib import Path
from collections import Counter
import hashlib,json,math,subprocess,shutil
import pcbnew as p
from pcb_power_leg import make,barrel
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
import sys
remaining='--remaining-ground' in sys.argv
qualified='--qualified-ground' in sys.argv
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';base=json.loads((root/('layout-bga-ground-remaining.json' if qualified else 'layout-bga-ground-drops.json' if remaining else 'layout-emmc-strobe-pulldown.json')).read_text());src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));code=b.FindNet('GND').GetNetCode();back=b.FindFootprintByReference('U4').FindPadByNumber('69')
out=root/('runs/bga-ground-qualified' if qualified else 'runs/bga-ground-remaining' if remaining else 'runs/bga-ground-drop');out.mkdir(exist_ok=True,parents=True);file=out/src.name
for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table')
old=json.loads((src.parent/'drc.json').read_text())
def native(board,label):
    a,z=label.split('.');return board.FindFootprintByReference(a).FindPadByNumber(z)
def checkout(board):
    p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(file),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(file)],capture_output=True,check=True)
    return json.loads((out/'drc.json').read_text())
def compact(points):
    result=[]
    for v in points:
        if len(result)>1:
            a,z=result[-2:];dx=z[0]-a[0];dy=z[1]-a[1]
            if dx*(v[1]-z[1])==dy*(v[0]-z[0]):result.pop()
        result.append(v)
    return result
rows=[];accepted=[]
for report in sorted(root.glob('bga-ground-qualified-*.json' if qualified else 'bga-ground-remaining-*.json' if remaining else 'bga-ground-drop-*.json')):
    info=json.loads(report.read_text())
    if info['source_sha256']!=base['sha256']:continue
    ref=info['pin'];pad=native(b,ref);side=pad.GetParentFootprint().GetLayer()
    candidates=[]
    for opt in info['sites']:
        xy=opt['path_nm'][-1];v=barrel(b,xy,code);box=inflated_box(v,300000);land=v.GetEffectiveShape(side);hole=v.GetEffectiveHoleShape()
        if any(box.Intersects(q.GetBoundingBox()) and land.Collide(q.GetEffectiveShape(q.GetParentFootprint().GetLayer()),100000) for f in b.GetFootprints() for q in f.Pads()):continue
        if any(t.GetNetCode()!=code and box.Intersects(t.GetBoundingBox()) and any(t.IsOnLayer(l) and hole.Collide(t.GetEffectiveShape(l),252000) for l in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)) for t in b.GetTracks()):continue
        if any(not next(z for z in b.Zones() if z.GetNetCode()==code and z.HasFilledPolysForLayer(l)).GetFilledPolysList(l).Contains(v.GetPosition()) for l in (p.In1_Cu,p.In4_Cu)):continue
        candidates.append(opt)
    tries=[];row={'ref':ref,'solder_clear_candidates':len(candidates),'attempts':tries};rows.append(row)
    for opt in sorted(candidates,key=lambda o:o['length_mm'])[:4]:
        points=compact([tuple(p) for p in opt['path_nm']]);added=[make(b,a,z,200000,code,side) for a,z in zip(points,points[1:])]+[barrel(b,points[-1],code)]
        for o in added:b.Add(o)
        db=checkout(b);delta=introduced(old,db);fresh=p.LoadBoard(str(file));fresh.BuildConnectivity()
        g={o.m_Uuid.AsString() for o in fresh.GetConnectivity().GetConnectedItems(native(fresh,'U4.69'))}
        ok=native(fresh,ref).m_Uuid.AsString() in g
        tries.append(dict(via_nm=points[-1],length_mm=opt['length_mm'],delta=delta,connected=ok))
        if not delta and ok and len(db['unconnected_items'])<base['remaining_minimum_joins']-len(accepted):
            accepted.append(ref);break
        for o in added:b.Remove(o)
        p.ZONE_FILLER(b).Fill(b.Zones())
db=checkout(b);fresh=p.LoadBoard(str(file));fresh.BuildConnectivity()
report=dict(parent_sha256=base['sha256'],rows=rows,accepted=accepted,remaining=len(db['unconnected_items']))
if accepted:
    assert not introduced(old,db)
    proof=verify_preservation(p.LoadBoard(str(src)),fresh)
    nets=base['open_nets'].copy();gs=nets['GND'];main=next(g for g in gs if 'U4.69' in g)
    gset={o.m_Uuid.AsString() for o in fresh.GetConnectivity().GetConnectedItems(native(fresh,'U4.69'))}
    joined=[g for g in gs if g!=main and native(fresh,g[0]).m_Uuid.AsString() in gset]
    nets['GND']=[g for g in gs if g!=main and g not in joined]+[sorted(main+[n for g in joined for n in g])]
    assert sum(len(v)-1 for v in nets.values())==report['remaining']
    pairs=sorted({tuple(sorted(pair)) for pair in base['verified_pairs']}|{tuple(sorted((s,'U4.69'))) for s in accepted})
    cache={}
    for a,z in pairs:
        if a not in cache:cache[a]={o.m_Uuid.AsString() for o in fresh.GetConnectivity().GetConnectedItems(native(fresh,a))}
        assert native(fresh,z).m_Uuid.AsString() in cache[a]
    cp=dict(board=str(file.relative_to(root)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),parent_sha256=base['sha256'],verified_pairs=pairs,preservation=proof,open_nets=nets,remaining_minimum_joins=report['remaining'],new_drc=[],drc_counts=dict(Counter(v['type'] for v in db['violations'])),assembly_ready=False)
    (root/('layout-bga-ground-qualified.json' if qualified else 'layout-bga-ground-remaining.json' if remaining else 'layout-bga-ground-drops.json')).write_text(json.dumps(cp,indent=2)+'\n')
(root/('ground-bga-physical-qualified.json' if qualified else 'ground-bga-physical-remaining.json' if remaining else 'ground-bga-physical-drops.json')).write_text(json.dumps(report,indent=2)+'\n');print(accepted,report['remaining'])
