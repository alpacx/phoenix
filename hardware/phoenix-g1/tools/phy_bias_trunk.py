"""Use one continuous low-current bias trace through the three adjacent rear loads."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'fixture-solid-verified.json').read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));ref=['R527','R526','R525']
pads=[b.FindFootprintByReference(r).FindPadByNumber('2') for r in ref]
net=pads[0].GetNetCode();points=[p.VECTOR2I(73000000,32400000)]+[q.GetPosition() for q in pads]
items=[t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetLayer()==p.B_Cu and t.GetNetCode()==net and t.GetStart()==points[0] and t.GetEnd() in points[1:]]
assert len(items)==3
for t in items:b.Remove(t)
added=[]
for a,z in zip(points,points[1:]):
    t=p.PCB_TRACK(b);t.SetLayer(p.B_Cu);t.SetWidth(200000);t.SetStart(a);t.SetEnd(z);t.SetNetCode(net);b.Add(t);added.append(t)
folder=root/'runs/rear-bias-trunk';folder.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
dest=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dest),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(dest)],check=True,capture_output=True)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
if not delta:
    saved=p.LoadBoard(str(dest));pres=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=[t.m_Uuid.AsString() for t in items])
    group={o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('C515').FindPadByNumber('1'))}
    assert all(q.m_Uuid.AsString() in group for q in pads)
    cp=dict(board=str(dest.relative_to(root)),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),old_mm=sum(t.GetLength() for t in items)/1e6,new_mm=sum(t.GetLength() for t in added)/1e6,new_drc=delta,preservation=pres)
(root/'rear-bias-trunk.json').write_text(json.dumps(cp,indent=2)+'\n')
print(cp['board'],delta,flush=True);os._exit(0)
