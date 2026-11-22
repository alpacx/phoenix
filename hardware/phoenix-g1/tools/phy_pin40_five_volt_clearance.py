"""Reform the existing 0.80 mm +5V_MAIN bend to leave a full-width PHY landing."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
pmic='--pmic-bypass' in sys.argv
stage='pmic-3v3-via-clearance' if pmic else 'phy-pin40-5v-clearance'
parent=json.loads((root/('layout-usb-shell.json' if pmic else 'layout-phy-pin40.json')).read_text());src=root/parent['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==parent['sha256']
b=p.LoadBoard(str(src));original=p.LoadBoard(str(src));layer=p.In2_Cu;code=b.GetNetcodeFromNetname('+5V_MAIN')
ids={'85f521dc-7388-42cb-8803-c8f346d7bba3','872b4201-7444-4e84-8d74-332797475a6f','648803d6-8c67-4ad8-8154-b3d667c6f3c4'}
width=800000
a,z=(60900000,24900000),(54000000,32950000)
bounds=[50000000,19500000,66000000,36500000]
if pmic:
    width=300000;layer=p.B_Cu;code=b.GetNetcodeFromNetname('+3V3_SYS')
    ids={'0b2d3739-6243-4aba-9de8-dd36755f0601','6584c6e9-e6c6-4f69-bd33-e57362e8b471'}
    a,z=(63400000,11050000),(65980000,9900000);bounds=[61700000,8000000,67300000,13000000]
cut=[t for t in b.GetTracks() if t.m_Uuid.AsString() in ids]
assert len(cut)==len(ids) and all(t.GetWidth()==width and t.GetLayer()==layer and t.GetNetCode()==code for t in cut)
for t in cut:b.Remove(t)
pos=tuple(b.FindFootprintByReference('C518').FindPadByNumber('1').GetPosition())
obs,pads=geometry(b,layer,code,oval_caps=True)
if pmic:pos=(64310000,9450000)
obs.append([pos,pos,900000 if pmic else 1050000])
areas=[z.Outline().Outline(0) for z in b.Zones() if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks()]
keep=[[tuple(k.CPoint(i)) for i in range(k.PointCount())] for k in areas]
req=dict(grid_nm=50000,bounds=bounds,layers=[[obs,pads,keep]],through=[],via_keepouts=[[],[]],start=[[a]],end=[[z]],width_nm=width)
sol=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('control_board_grid.py'))],input=json.dumps(req),text=True,capture_output=True,check=True).stdout)
out=src;change=None
if sol:
    path=[p.VECTOR2I(x,y) for _,x,y in sol['path']]
    for a,z in zip(path,path[1:]):
        t=p.PCB_TRACK(b);t.SetWidth(width);t.SetLayer(layer);t.SetStart(a);t.SetEnd(z);t.SetNetCode(code);b.Add(t)
    folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
    for name in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):shutil.copy2(src.parent/name,folder/name)
    candidate=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(candidate),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(candidate)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if not delta:
        saved=p.LoadBoard(str(candidate));proof=verify_preservation(original,saved,replaced_copper=ids)
        assert not screen(saved)
        change=dict(path_nm=[tuple(k) for k in path],width_mm=width/1e6,preservation=proof);out=candidate
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=parent['sha256'],change=change,assembly_ready=False),indent=2)+'\n')
print(bool(sol),bool(change),flush=True);os._exit(0)
