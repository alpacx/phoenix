"""Transfer the validated analog-link placement and its copper without importing the RF experiments."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def read(name):
    rec=json.loads((root/(name+'.json')).read_text())
    return rec['result'][0] if 'result' in rec else rec
def load(rec):
    path=root/rec['board']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==rec['sha256']
    return p.LoadBoard(str(path))
base=read('layout-usb-enable-trunk');before=read('rf-external-return-cleanup');after=read('rf-edge-r1601-joined')
assert json.loads((root/'rf-edge-r1601-joined.json').read_text())['parent_sha256']==before['sha256']
old,exp,b=load(before),load(after),load(base)
initial=load(base)
existing={t.m_Uuid.AsString() for t in old.GetTracks()}
link=exp.FindFootprintByReference('R1601');f=b.FindFootprintByReference('R1601')
if f.GetLayer()!=link.GetLayer(): f.Flip(f.GetPosition(),False)
f.SetOrientationDegrees(link.GetOrientationDegrees());f.SetPosition(link.GetPosition())
added=[]
for t in exp.GetTracks():
    if t.m_Uuid.AsString() in existing:continue
    assert t.GetNetname() in ('USB_AVDD_0V9','VDDA_0V9') and t.GetWidth()==300000 and t.GetLayer()==p.B_Cu
    seg=p.PCB_TRACK(b);seg.SetLayer(t.GetLayer());seg.SetNet(b.FindNet(t.GetNetname()));seg.SetStart(t.GetStart());seg.SetEnd(t.GetEnd());seg.SetWidth(t.GetWidth());b.Add(seg);added.append(seg.m_Uuid.AsString())
assert added
folder=root/'runs/usb-analog-0v9-filter';folder.mkdir(exist_ok=True)
src=root/base['board'];out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
saved=p.LoadBoard(str(out));guard=verify_preservation(initial,saved)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));assert not delta,delta
pairs=[['R1601.1','C1642.1'],['R1601.2','C1679.1'],['R1601.2','C1680.1']]
def pad(name):
    ref,num=name.split('.')
    return saved.FindFootprintByReference(ref).FindPadByNumber(num)
for a,z in pairs:
    assert pad(z).m_Uuid.AsString() in {q.m_Uuid.AsString() for q in saved.GetConnectivity().GetConnectedItems(pad(a))}
(root/'usb-analog-0v9-filter.json').write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=base['sha256'],coupon_sha256=after['sha256'],pairs=pairs,added_copper=added,rs_position_nm=tuple(f.GetPosition()),preservation=guard,new_drc=delta,assembly_ready=False),indent=2)+'\n')
print(len(added),pairs,flush=True);os._exit(0)
