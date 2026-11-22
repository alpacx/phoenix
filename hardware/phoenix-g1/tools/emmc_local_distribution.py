"""Route the external VCC/VCCQ capacitor banks without modifying the eMMC ball escape."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess
import pcbnew as p
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'header-signals.json').read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
current=src;records=[];held=[]
def pad(b,s):
    ref,n=s.split('.');return b.FindFootprintByReference(ref).FindPadByNumber(n)
def contact(b,q):
    return {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(q) if isinstance(i,p.PAD)}
pairs=[('R8007.2','C8009.1'),('C8009.1','C8008.1'),('R8007.2','C8007.1'),('R8006.2','C8006.1'),('C8006.1','C8005.1'),('C8006.1','C8004.1'),('C8004.1','C8002.1'),('R8006.2','C8003.1'),('C8002.1','C8010.1')]
for a,z in pairs:
    b=p.LoadBoard(str(current));b.BuildConnectivity();q=pad(b,a);dest=pad(b,z);net=q.GetNetCode();layer=p.B_Cu;width=500000
    assert net==dest.GetNetCode() and q.IsOnLayer(layer) and dest.IsOnLayer(layer)
    group=contact(b,q)|contact(b,dest)
    if dest.m_Uuid.AsString() in contact(b,q):continue
    tracks,pads=geometry(b,layer,net,oval_caps=True)
    for f in b.GetFootprints():
        for k in f.Pads():
            if k.GetNetCode()==net and k.IsOnLayer(layer) and k.m_Uuid.AsString() not in group:
                box=k.GetBoundingBox();pads.append((box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom()))
    for zone in b.Zones():
        if zone.GetIsRuleArea() and zone.IsOnLayer(layer) and zone.GetDoNotAllowTracks():
            box=zone.GetBoundingBox();pads.append((box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom()))
    req=dict(geometry=[tracks,pads],width=width,ends=[tuple(q.GetPosition()),tuple(dest.GetPosition())])
    path=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('reset_link_grid.py'))],input=json.dumps(req),text=True,capture_output=True,check=True).stdout)
    if not path:held.append([a,z]);continue
    for start,end in zip(path,path[1:]):
        t=p.PCB_TRACK(b);t.SetNetCode(net);t.SetLayer(layer);t.SetWidth(width);t.SetStart(p.VECTOR2I(*start));t.SetEnd(p.VECTOR2I(*end));b.Add(t)
    folder=root/'runs'/('emmc-distribution-'+a+'-'+z);folder.mkdir(exist_ok=True)
    for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    saved=p.LoadBoard(str(out));saved.BuildConnectivity()
    if delta or contact(saved,pad(saved,a))!=group:held.append([a,z]);continue
    verify_preservation(p.LoadBoard(str(current)),saved);assert not screen(saved);current=out
    records.append(dict(pair=[a,z],width_mm=.50,length_mm=sum(math.dist(u,v) for u,v in zip(path,path[1:]))/1e6))
(root/'emmc-distribution.json').write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],records=records,held=held,assembly_ready=False),indent=2)+'\n')
print(records,flush=True);os._exit(0)
