"""Route the supply side of PHY bias resistors and independently check saved pad groups."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from phy_corridor_path import geometry
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
rear='--rear' in sys.argv
checkpoint=json.loads((root/('phy-rx-back.json' if rear else 'c522-verified.json')).read_text())
source=root/checkpoint['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==checkpoint['sha256']
original=p.LoadBoard(str(source))
prior=json.loads((source.parent/'drc.json').read_text())
refs=['R521'] if rear else ['R514','R521','R525','R526','R527']
layers=[p.B_Cu if rear else p.F_Cu,p.In2_Cu]
def members(board):
    board.BuildConnectivity()
    pad=board.FindFootprintByReference('C515').FindPadByNumber('1')
    return list(board.GetConnectivity().GetConnectedItems(pad))
def pads(items):
    return {(o.GetParentFootprint().GetReference(),o.GetNumber()) for o in items if isinstance(o,p.PAD)}
initial=pads(members(original));records=[]
folder=root/('runs/phy-rear-bias-distribution' if rear else 'runs/phy-bias-distribution')
folder.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/file,folder/file)
current=source
previous=root/('phy-rear-bias-verified.json' if rear else 'phy-bias-verified.json')
if previous.exists():
    saved_report=json.loads(previous.read_text())
    current=root/saved_report['board']
    assert hashlib.sha256(current.read_bytes()).hexdigest()==saved_report['sha256']
    records=[r for r in saved_report['records'] if r['accepted']]
for iteration in range(len(records),len(refs)):
    b=p.LoadBoard(str(current));group=members(b);existing=pads(group)
    net=b.GetNetcodeFromNetname('+3V3_PHY')
    goals={}
    for ref in refs:
        q=b.FindFootprintByReference(ref).FindPadByNumber('2')
        assert q.GetNetCode()==net
        if (ref,'2') not in existing:goals[ref]=tuple(q.GetPosition())
    if not goals:break
    seeds=[]
    for l in layers:
        points=set()
        for o in group:
            if not o.IsOnLayer(l):continue
            if isinstance(o,p.PCB_TRACK):
                a,z=tuple(o.GetStart()),tuple(o.GetEnd())
                count=max(1,int(o.GetLength()/300000))
                points.update(tuple(round(s+(t-s)*i/count) for s,t in zip(a,z)) for i in range(count+1))
            elif isinstance(o,p.PAD):points.add(tuple(o.GetPosition()))
        seeds.append(sorted(points))
    geos={l:geometry(b,l,net) for l in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)}
    for l,(copper,pad_bounds) in geos.items():
        for zone in b.Zones():
            if zone.GetIsRuleArea() and zone.IsOnLayer(l) and (zone.GetDoNotAllowTracks() or zone.GetDoNotAllowVias()):
                box=zone.GetBoundingBox()
                pad_bounds.append((box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom()))
    obj=dict(layers=[geos[l] for l in layers],through=list(geos.values()),goals=goals,seeds=seeds)
    run=subprocess.run(['python3',str(Path(__file__).with_name('phy_bias_paths.py'))],input=json.dumps(obj),capture_output=True,text=True,check=True)
    solution=json.loads(run.stdout)
    if not solution:break
    pts=solution['path']
    for (l,x,y),(k,u,v) in zip(pts,pts[1:]):
        if l==k:
            item=p.PCB_TRACK(b);item.SetLayer(layers[l]);item.SetWidth(200000)
            item.SetStart(p.VECTOR2I(x,y));item.SetEnd(p.VECTOR2I(u,v))
        else:
            assert (x,y)==(u,v)
            item=p.PCB_VIA(b);item.SetViaType(p.VIATYPE_THROUGH);item.SetLayerPair(p.F_Cu,p.B_Cu);item.SetWidth(450000);item.SetDrill(200000);item.SetPosition(p.VECTOR2I(x,y))
        item.SetNetCode(net);b.Add(item)
    trial=folder/f'pass-{iteration}';trial.mkdir(exist_ok=True)
    for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/file,trial/file)
    dest=trial/source.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dest),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(trial/'drc.json'),str(dest)],check=True,capture_output=True)
    saved=p.LoadBoard(str(dest));pres=verify_preservation(original,saved)
    after=pads(members(saved));delta=introduced(prior,json.loads((trial/'drc.json').read_text()))
    added=sorted(after-initial)
    ok=not delta and (solution['ref'],'2') in after and set(added)<={(r,'2') for r in refs}
    records.append(dict(target=solution['ref'],path=pts,added=added,drc=delta,accepted=ok,preservation=pres))
    print(iteration,solution['ref'],ok,added,delta,flush=True)
    if not ok:break
    current=dest
previous.write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),records=records),indent=2)+'\n')
os._exit(0)
