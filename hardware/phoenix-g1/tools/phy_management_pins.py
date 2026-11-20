"""Connect the PHY configuration and management pull-ups to their signal pins."""
import json,hashlib,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'phy-bias-verified.json').read_text());source=root/cp['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
original=p.LoadBoard(str(source));current=source;records=[]
layers=[p.F_Cu,p.In2_Cu]
for ref,num in [('R527','32'),('R514','14')]:
    b=p.LoadBoard(str(current));target=b.FindFootprintByReference('U5').FindPadByNumber(num)
    resistor=b.FindFootprintByReference(ref).FindPadByNumber('1')
    assert target.GetNetCode()==resistor.GetNetCode()
    pos=target.GetPosition()
    points=[(pos.x+dx,pos.y+dy) for dx in range(-350000,350001,50000) for dy in range(-350000,350001,50000) if (dx==0 or dy==0) and target.HitTest(p.VECTOR2I(pos.x+dx,pos.y+dy))]
    geos={l:geometry(b,l,target.GetNetCode()) for l in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)}
    for l,(copper,pads) in geos.items():
        for zone in b.Zones():
            if zone.GetIsRuleArea() and zone.IsOnLayer(l) and (zone.GetDoNotAllowTracks() or zone.GetDoNotAllowVias()):
                box=zone.GetBoundingBox();pads.append((box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom()))
    dest_pad=tuple(resistor.GetPosition())
    obj=dict(seeds=[points,[]],goals={ref:dest_pad},layers=[geos[l] for l in layers],through=list(geos.values()))
    sol=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('phy_bias_paths.py'))],input=json.dumps(obj),text=True,capture_output=True,check=True).stdout)
    if not sol:
        print(ref,'no path',flush=True);continue
    for (l,x,y),(k,u,v) in zip(sol['path'],sol['path'][1:]):
        if l==k:
            t=p.PCB_TRACK(b);t.SetLayer(layers[l]);t.SetWidth(200000);t.SetStart(p.VECTOR2I(x,y));t.SetEnd(p.VECTOR2I(u,v))
        else:
            assert (x,y)==(u,v)
            t=p.PCB_VIA(b);t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetWidth(450000);t.SetDrill(200000);t.SetPosition(p.VECTOR2I(x,y))
        t.SetNetCode(target.GetNetCode());b.Add(t)
    folder=root/'runs'/('phy-management-'+ref);folder.mkdir(exist_ok=True)
    for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/file,folder/file)
    dest=folder/source.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dest),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(dest)],check=True,capture_output=True)
    diff=introduced(json.loads((source.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    saved=p.LoadBoard(str(dest));pres=verify_preservation(original,saved);q=saved.FindFootprintByReference(ref).FindPadByNumber('1')
    connected=target.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(q)}
    if not diff and connected:current=dest
    records.append(dict(ref=ref,pin=num,connected=connected,new_drc=diff,preservation=pres))
    print(ref,connected,diff,flush=True)
(root/'phy-management-verified.json').write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),records=records),indent=2)+'\n')
os._exit(0)
