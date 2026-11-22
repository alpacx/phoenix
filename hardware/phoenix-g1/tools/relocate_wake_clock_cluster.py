"""Trial alternate buffered wake oscillator, bypass and source termination positions."""
from pathlib import Path
import json,os,hashlib,subprocess,shutil
import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((root/(n+'.json')).read_text());base=read('layout-usb-enable-trunk');probe=read('wake-clock-refined-window');src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']==probe['parent_sha256']
folder=root/'runs/relocated-wake-clock';folder.mkdir(exist_ok=True);out=folder/src.name;dr=folder/'drc.json'
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
orig=p.LoadBoard(str(src));orig.BuildConnectivity();labels=lambda fp:[str(fp.GetReference())+'.'+str(q.GetNumber()) for q in fp.Pads()];uid=lambda o:o.m_Uuid.AsString()
def assignments(b):
 idx={uid(q):f.GetReference()+'.'+q.GetNumber() for f in b.GetFootprints() for q in f.Pads()};conn=b.GetConnectivity()
 return {f.GetReference()+'.'+q.GetNumber():sorted(idx[uid(o)] for o in conn.GetConnectedItems(q) if uid(o) in idx) for f in b.GetFootprints() if f.GetReference() in ('Y2001','C2007','R2003') for q in f.Pads()}
old=assignments(orig);rejected=[];winner=None
for row in probe['placement']['F.Cu']['best']:
 b=p.LoadBoard(str(src))
 for ref,key in [('Y2001','oscillator'),('C2007','bypass'),('R2003','series')]:
  f=b.FindFootprintByReference(ref);pos,ang=row[key];f.SetOrientationDegrees(ang);f.SetPosition(p.VECTOR2I(*pos))
 if screen(b):rejected.append(dict(pose=row,reason='mechanical reservation'));continue
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],capture_output=True,check=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()))
 if any(r['type'] not in ('track_dangling','via_dangling') for r in delta):rejected.append(dict(pose=row,new_drc=delta));continue
 saved=p.LoadBoard(str(out));saved.BuildConnectivity();new=assignments(saved);lost={q:len(set(group)-set(new[q])) for q,group in old.items()}
 winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),pose=row,new_drc=delta,lost_original_pad_contacts=lost);break
(root/'wake-clock-relocation-coupon.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,rejected=rejected,assembly_ready=False),indent=2)+'\n');print(bool(winner),len(rejected),flush=True);os._exit(0)
