"""Exercise two-ended PHY power distribution in an isolated, refilled board."""
from pathlib import Path
import json, os, shutil, subprocess
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation

root = Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
source = root/'runs/phy-offset-link-0-1-ground-reuse-array'
name = 'phy-joint.kicad_pcb'
original = p.LoadBoard(str(source/name))
reference = json.loads((root/'runs/input-ground-local-002/drc.json').read_text())
report=[]
def point(pair):
    return p.VECTOR2I(*(p.FromMM(x) for x in pair))
def trace(board, net, layer, a, z):
    t=p.PCB_TRACK(board)
    t.SetNetCode(net)
    t.SetLayer(layer)
    t.SetWidth(p.FromMM(1.05))
    t.SetStart(point(a))
    t.SetEnd(point(z))
    board.Add(t)
import sys
detour = "--detour" in sys.argv
for layer in (p.B_Cu,p.In2_Cu,p.In3_Cu):
    b=p.LoadBoard(str(source/name))
    net=b.GetNetcodeFromNetname('+3V3_PHY')
    start=[(54.61,26.675),(55.11,27.05)]
    end=[(61.765,24.6),(62.34,24.3)]
    if detour:
        end=[(61.74,24.575),(62.365,24.625)]
    east="--east" in sys.argv
    if east:
        if layer!=p.In2_Cu:continue
        end=[(62.015,24.60),(62.575,24.60)]
        trace(b,net,p.F_Cu,(61.975,24.55),end[0])
        trace(b,net,p.F_Cu,end[0],(62.33,24.60))
    for v in end:
        via=p.PCB_VIA(b)
        via.SetLayerPair(p.F_Cu,p.B_Cu)
        via.SetViaType(p.VIATYPE_THROUGH)
        via.SetWidth(600000)
        via.SetDrill(300000)
        via.SetNetCode(net)
        via.SetPosition(point(v))
        b.Add(via)
    path = start + ([(55.66,27.60),(56.65,27.60)] if detour else []) + end
    mixed="--mixed" in sys.argv
    if mixed and layer!=p.In3_Cu:continue
    if mixed:
        from phy_corridor_path import geometry
        obj=dict(power=[geometry(b,l,net) for l in (p.In2_Cu,p.In3_Cu)],all=[geometry(b,l,net) for l in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)])
        run=subprocess.run(["/usr/bin/env","python3",str(Path(__file__).with_name("phy_transition_grid.py"))],input=json.dumps(obj),text=True,capture_output=True,check=True)
        result=json.loads(run.stdout)
        print(result,flush=True)
        if not result["vias"]:continue
        positions=[tuple(i/1e6 for i in pos) for pos in result["vias"]]
        for pos in positions:
            v=p.PCB_VIA(b)
            v.SetViaType(p.VIATYPE_THROUGH)
            v.SetLayerPair(p.F_Cu,p.B_Cu)
            v.SetWidth(600000)
            v.SetDrill(300000)
            v.SetPosition(point(pos))
            v.SetNetCode(net)
            b.Add(v)
        for l,points in zip((p.In2_Cu,p.In3_Cu),result["paths"]):
            coords=[tuple(i/1e6 for i in pos) for pos in points]+positions[1:]
            for a,z in zip(coords,coords[1:]):trace(b,net,l,a,z)
        trace(b,net,p.In2_Cu,*start)
        path=end
    elif detour:
        from phy_corridor_path import route
        middle=route(b,layer,net,start[-1],end[0])
        print("path",middle,flush=True)
        if not middle: continue
        path=start[:1]+middle+end[1:]
    for a,z in zip(path,path[1:]):
        trace(b,net,layer,a,z)
    dest=root/'runs'/('phy-bulk-corridor-'+b.GetLayerName(layer)+('-east' if east else '-mixed' if mixed else '-detour' if detour else ''))
    dest.mkdir(exist_ok=True)
    for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
        shutil.copy2(source/file,dest/file)
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(str(dest/name),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dest/'drc.json'),str(dest/name)],check=True,capture_output=True)
    saved=p.LoadBoard(str(dest/name))
    preservation=verify_preservation(original,saved)
    q=saved.FindFootprintByReference('R530').FindPadByNumber('2')
    group={o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(q)}
    bulk=saved.FindFootprintByReference('C515').FindPadByNumber('1')
    delta=introduced(reference,json.loads((dest/'drc.json').read_text()))
    report.append(dict(layer=b.GetLayerName(layer),preservation=preservation,bulk_connected=bulk.m_Uuid.AsString() in group,new_drc=delta))
(root/('phy-bulk-east.json' if east else 'phy-bulk-mixed.json' if mixed else 'phy-bulk-detour.json' if detour else 'phy-bulk-corridors.json')).write_text(json.dumps(report,indent=2)+'\n')
print([(r['layer'],r['bulk_connected'],len(r['new_drc'])) for r in report],flush=True)
os._exit(0)
