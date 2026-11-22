"""Open a compliant U6.12 breakout while reconnecting its original AON_READY neighbor."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
import pcbnew as p
from native_front_splice import wire,compact,recover
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'layout-lcd-select-trunk.json').read_text());probe=json.loads((root/'usb-mux-enable-aon-window.json').read_text());src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']==probe['source_sha256'];ret='03cfdf46-4da6-49b4-93f5-da1a296aa0ce';uid=lambda o:o.m_Uuid.AsString()
folder=root/'runs/usb-enable-aon-fanout';folder.mkdir(exist_ok=True);out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
attempts=[];winner=None
for row in probe['sites']:
    b=p.LoadBoard(str(src));pin=b.FindFootprintByReference('U6').FindPadByNumber('12');t=next(t for t in b.GetTracks() if uid(t)==ret);assert t.GetNetname()=='AON_READY'
    old=[(tuple(t.GetStart()),tuple(t.GetEnd()),t.GetWidth(),t.GetNetCode())];b.Remove(t)
    path=compact(row['path_nm']);at=path[-1];via=p.PCB_VIA(b);via.SetPosition(p.VECTOR2I(*at));via.SetWidth(450000);via.SetDrill(200000);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetViaType(p.VIATYPE_THROUGH);via.SetNetCode(pin.GetNetCode());b.Add(via);vid=uid(via)
    for a,z in zip(path,path[1:]):b.Add(wire(b,a,z,pin.GetNetCode(),200000))
    restore,info=recover(b,old,'AON_READY',False);rec=dict(via_nm=at,recovery=info);attempts.append(rec)
    if not restore:continue
    for a,z in zip(restore,restore[1:]):b.Add(wire(b,a,z,info['code'],info['width']))
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));rec['new_drc']=delta
    if any(r['type']!='via_dangling' or r['items']!=[vid] for r in delta):continue
    saved=p.LoadBoard(str(out));saved.BuildConnectivity();q=saved.FindFootprintByReference('U6').FindPadByNumber('12')
    if vid not in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(q)} or screen(saved):continue
    proof=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper={ret});winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),via_uuid=vid,preservation=proof);break
(root/'usb-enable-aon-fanout.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,attempts=attempts,assembly_ready=False),indent=2)+'\n');print(bool(winner),len(attempts),attempts[:1],flush=True);os._exit(0)
