"""Reuse the vacated clock trace for the terminated output up to the original radio pad."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
import pcbnew as p
from pcb_power_leg import route_leg,make
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda k:json.loads((root/(k+'.json')).read_text())
base=read('layout-usb-enable-trunk');cp=read('wake-clock-trunk-recovery');src=root/cp['board'];origpath=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];assert hashlib.sha256(origpath.read_bytes()).hexdigest()==base['sha256']
orig=p.LoadBoard(str(origpath));orig.BuildConnectivity();b=p.LoadBoard(str(src));b.BuildConnectivity()
uid=lambda o:o.m_Uuid.AsString();chip=b.FindFootprintByReference('U25').FindPadByNumber('24');old=orig.FindFootprintByReference('R2003');pins=[old.FindPadByNumber(n) for n in ('1','2')]
oldids={uid(o) for o in orig.GetConnectivity().GetConnectedItems(pins[0]) if isinstance(o,p.PCB_TRACK)}
tracks=[t for t in b.GetTracks() if uid(t) in oldids];assert len(tracks)==len(oldids)>0
assert not any(isinstance(q,p.PAD) for q in b.GetConnectivity().GetConnectedItems(tracks[0]))
assert all(t.GetNetname()=='WIFI_LPO_SRC' for t in tracks)
for t in tracks:t.SetNetCode(chip.GetNetCode())
link=route_leg(b,chip.GetNetname(),tuple(pins[0].GetPosition()),p.F_Cu,tuple(pins[1].GetPosition()),p.F_Cu,200000,2)
if not link['connected']:raise ValueError(link)
folder=root/'runs/wake-repurposed-termination';folder.mkdir(exist_ok=True);out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);dr=folder/'drc.json'
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],capture_output=True,check=True);delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()));saved=p.LoadBoard(str(out));saved.BuildConnectivity();ids={uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('U25').FindPadByNumber('24'))}
assert oldids<=ids and not delta,(oldids-ids,delta)
(root/'wake-repurposed-termination.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),reclaimed=sorted(oldids),link=link,new_drc=delta,assembly_ready=False),indent=2)+'\n');print(len(oldids),flush=True);os._exit(0)
