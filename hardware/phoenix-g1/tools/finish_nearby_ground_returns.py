"""Reconnect isolated ground pads to existing grounded vias using bounded surface paths."""
from pathlib import Path
import hashlib,json,math,subprocess,shutil
from collections import Counter
import pcbnew as p
from phy_corridor_path import geometry
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced
tools=Path(__file__).resolve().parent
root=tools.parent/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'layout-soc-ground-existing-barrel.json').read_text())
src=root/base['board'];assert base['sha256']==hashlib.sha256(src.read_bytes()).hexdigest()
b=p.LoadBoard(str(src));b.BuildConnectivity()
def pad(board,label):
    ref,num=label.split(".");return board.FindFootprintByReference(ref).FindPadByNumber(num)
def group(board,label):return {o.m_Uuid.AsString() for o in board.GetConnectivity().GetConnectedItems(pad(board,label))}
grounded=group(b,"U4.69");code=pad(b,"U4.69").GetNetCode()
ends=[tuple(v.GetPosition()) for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and v.m_Uuid.AsString() in grounded]
g0=base['open_nets']['GND'];geos={l:geometry(b,l,code,oval_caps=True) for l in (p.F_Cu,p.B_Cu)}
added=[];trials=[]
for g in g0:
    if "U4.69" in g:continue
    q=pad(b,g[0]);layer=q.GetParentFootprint().GetLayer()
    starts=[tuple(pad(b,n).GetPosition()) for n in g]
    targets=[z for z in ends if min(math.dist(z,x) for x in starts)<3000000]
    if not targets:continue
    req=dict(geometry=geos[layer],width=250000,sites=starts,target=targets,limit=3500000)
    proc=subprocess.run(["python3",str(tools/"screen_cpu_launch_corridor.py")],input=json.dumps(req),text=True,capture_output=True,check=True)
    row=json.loads(proc.stdout);trials.append(dict(terminals=g,targets=len(targets),reachable=row['front_nodes'],path=row['path']))
    if row['path']:
        for a,z in zip(row['path'],row['path'][1:]):b.Add(make(b,a,z,250000,code,layer))
        added.append(g)
out=root/"runs/nearby-ground-returns";out.mkdir(exist_ok=True,parents=True);f=out/src.name
d=dict(parent_sha256=base['sha256'],trials=trials,groups=added)
if added:
    for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),f.with_suffix(ext))
    shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table')
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(f),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(f)],check=True,capture_output=True)
    db=json.loads((out/'drc.json').read_text());delta=introduced(json.loads((src.parent/'drc.json').read_text()),db)
    b=p.LoadBoard(str(f));b.BuildConnectivity();main=group(b,"U4.69")
    assert all(pad(b,n).m_Uuid.AsString() in main for g in added for n in g)
    proof=verify_preservation(p.LoadBoard(str(src)),b)
    d.update(board=str(f.relative_to(root)),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),remaining_minimum_joins=len(db['unconnected_items']),new_drc=delta,preservation=proof)
    if not delta and d['remaining_minimum_joins']==base['remaining_minimum_joins']-len(added):
        opens=base['open_nets'].copy();main_names=next(g for g in g0 if "U4.69" in g)
        opens["GND"]=[g for g in g0 if g!=main_names and g not in added]+[sorted(main_names+[n for g in added for n in g])]
        pairs=sorted({tuple(sorted(pair)) for pair in base['verified_pairs']}|{tuple(sorted((g[0],"U4.69"))) for g in added})
        cached={}
        for a,z in pairs:
            if a not in cached:cached[a]=group(b,a)
            assert pad(b,z).m_Uuid.AsString() in cached[a]
        cp=dict(board=d['board'],sha256=d['sha256'],parent_sha256=base['sha256'],verified_pairs=pairs,preservation=proof,open_nets=opens,remaining_minimum_joins=d['remaining_minimum_joins'],new_drc=[],drc_counts=dict(Counter(x['type'] for x in db['violations'])),assembly_ready=False)
        (root/'layout-nearby-ground-returns.json').write_text(json.dumps(cp,indent=2)+'\n')
(root/'nearby-ground-returns.json').write_text(json.dumps(d,indent=2)+'\n')
print(len(trials),added,d.get('remaining_minimum_joins'),len(d.get('new_drc',[])))
