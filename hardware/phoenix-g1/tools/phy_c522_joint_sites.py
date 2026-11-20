import json,subprocess,os
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
b=p.LoadBoard(str(root/'runs/c522-pin38-escape/phy-joint.kicad_pcb'))
g=geometry(b,p.B_Cu,b.GetNetcodeFromNetname('+1V0_PHY'))
c=b.FindFootprintByReference('C522');c.Flip(c.GetPosition(),False)
sites=json.loads((root/'c522-rear-wide.json').read_text())
for site in sites:
    c.SetPosition(p.VECTOR2I(*(p.FromMM(i) for i in site['center'])));c.SetOrientationDegrees(site['angle'])
    box=c.FindPadByNumber('2').GetBoundingBox()
    site['ground_box']=[box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom()]
starts=[tuple(t.GetPosition()) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='+1V0_PHY' and t.GetDrillValue()==300000]
obj=dict(geometry=g,starts=starts,sites=sites)
r=subprocess.run(['python3',str(Path(__file__).with_name('phy_c522_joint_grid.py'))],input=json.dumps(obj),capture_output=True,text=True,check=True)
(root/'c522-joint-sites.json').write_text(r.stdout)
print(len(json.loads(r.stdout)),flush=True);os._exit(0)
