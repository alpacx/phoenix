"""Tie together USB connector shell tabs on the rear face within the connector outline."""
import hashlib,itertools,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
from phy_corridor_path import geometry

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
inner='--inner' in sys.argv
stage='usb-shell-inner' if inner else 'usb-shell-tabs'
prior=json.loads((root/('usb-shell-tabs.json' if inner else 'layout-peripheral-supply-balls.json')).read_text());src=root/prior['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==prior['sha256']
board=p.LoadBoard(str(src));board.BuildConnectivity()
shell=board.FindFootprintByReference('J1');layer=p.In3_Cu if inner else p.B_Cu
tabs=[q for q in shell.Pads() if q.GetNetname()=='USB_SHIELD']
assert len(tabs)==4 and all(q.IsOnLayer(layer) and q.GetAttribute()==p.PAD_ATTRIB_PTH for q in tabs)
def connected(b,a,z):
    return z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(a)}
def gettab(b,uid):
    return next(q for q in b.FindFootprintByReference('J1').Pads() if q.m_Uuid.AsString()==uid)
obs,pads=geometry(board,layer,tabs[0].GetNetCode(),oval_caps=True)
areas=[z.Outline().Outline(i) for z in board.Zones() if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks() for i in range(z.Outline().OutlineCount())]
polys=[[tuple(k.CPoint(i)) for i in range(k.PointCount())] for k in areas]
box=shell.GetCourtyard(p.F_Cu).BBox()
bounds=[max(750000,box.GetLeft()+500000),box.GetTop()+500000,box.GetRight()-500000,box.GetBottom()-500000]
records=[]
for a,z in sorted(itertools.combinations(tabs,2),key=lambda x:(x[0].GetPosition()-x[1].GetPosition()).EuclideanNorm()):
    if connected(board,a,z):continue
    req=dict(grid_nm=100000,bounds=bounds,layers=[[obs,pads,polys]],through=[],via_keepouts=[[],[]],start=[[tuple(a.GetPosition())]],end=[[tuple(z.GetPosition())]],width_nm=1000000)
    sol=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('control_board_grid.py'))],input=json.dumps(req),capture_output=True,text=True,check=True).stdout)
    if not sol:continue
    path=[p.VECTOR2I(x,y) for _,x,y in sol['path']]
    for u,v in zip(path,path[1:]):
        t=p.PCB_TRACK(board);t.SetLayer(layer);t.SetWidth(1000000);t.SetNetCode(a.GetNetCode());t.SetStart(u);t.SetEnd(v);board.Add(t)
    board.BuildConnectivity()
    assert connected(board,a,z)
    records.append(dict(tab_ids=[q.m_Uuid.AsString() for q in (a,z)],path_nm=[tuple(k) for k in path],length_mm=sum((v-u).EuclideanNorm() for u,v in zip(path,path[1:]))/1e6))
out=src
if records:
    folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
    for n in ('fp-lib-table','phy-joint.kicad_dru','phy-joint.kicad_pro'):shutil.copy2(src.parent/n,folder/n)
    out=folder/src.name;p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(out),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));assert not delta,delta
    saved=p.LoadBoard(str(out));saved.BuildConnectivity()
    assert not screen(saved)
    verify_preservation(p.LoadBoard(str(src)),saved)
    for rec in records:assert connected(saved,*[gettab(saved,uid) for uid in rec['tab_ids']])
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=prior['sha256'],records=records,assembly_ready=False),indent=2)+'\n')
print(records,flush=True);os._exit(0)
