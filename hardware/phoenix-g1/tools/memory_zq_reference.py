"""Route only the local calibration reference; keep the VDDQ distribution separate."""
import hashlib,json,math,os,subprocess,shutil
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'memory-zq-verified.json').read_text());src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));u=b.FindFootprintByReference('U2');r=b.FindFootprintByReference('R201').FindPadByNumber('2')
nets=(root.parent/'lpddr4-1gb/ball-disposition.csv').read_text().splitlines()
choices=[]
for row in nets:
    fields=row.split(',')
    if fields[1]!='VDDQ':continue
    q=u.FindPadByNumber(fields[0]);end=tuple(r.GetPosition());origin=tuple(q.GetPosition())
    if math.dist(origin,end)>5e6:continue
    assert q.GetNetCode()==r.GetNetCode()
    copper,pads=geometry(b,p.F_Cu,r.GetNetCode())
    keep={q.m_Uuid.AsString(),r.m_Uuid.AsString()}
    for f in b.GetFootprints():
        for pad in f.Pads():
            if pad.GetNetCode()==r.GetNetCode() and pad.IsOnLayer(p.F_Cu) and pad.m_Uuid.AsString() not in keep:
                box=pad.GetBoundingBox();pads.append((box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom()))
    obj=dict(geometry=[copper,pads],goals={'R201':end},seeds=[origin],origin=origin)
    res=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('local_pad_grid.py'))],input=json.dumps(obj),capture_output=True,text=True,check=True).stdout)
    if res:choices.append((res[0]['length'],q.GetNumber(),res[0]['path']))
print('reachable',[(round(l/1e6,3),n) for l,n,_ in choices],flush=True)
for length,n,path in sorted(choices):
    saved_src=p.LoadBoard(str(src));board=p.LoadBoard(str(src))
    for a,z in zip(path,path[1:]):
        t=p.PCB_TRACK(board);t.SetLayer(p.F_Cu);t.SetWidth(200000);t.SetNetCode(r.GetNetCode());t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));board.Add(t)
    folder=root/'runs/memory-zq-reference';folder.mkdir(exist_ok=True)
    for f in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/f,folder/f)
    out=folder/src.name;p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(out),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if delta:continue
    saved=p.LoadBoard(str(out));pres=verify_preservation(saved_src,saved)
    group={(o.GetParentFootprint().GetReference(),o.GetNumber()) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('R201').FindPadByNumber('2')) if isinstance(o,p.PAD)}
    assert group=={('U2',n),('R201','2')},group
    cp=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),ram_vddq_ball=n,length_mm=length/1e6,preservation=pres,new_drc=delta,rail_powered=False,assembly_ready=False)
    break
(root/'memory-zq-reference.json').write_text(json.dumps(cp,indent=2)+'\n')
print(cp['board'],flush=True);os._exit(0)
