"""Shorten the existing 3V3 QFN neck while clearing the adjacent SDA escape."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'perimeter-controls.json').read_text());source=root/cp['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
base=p.LoadBoard(str(source));origin=p.VECTOR2I(55650000,6600000)
prior=json.loads((source.parent/'drc.json').read_text())
folder=root/'runs/pmic-sda-clearance';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/name,folder/name)
record=None
for x,y in [(55.70,6.90),(55.75,6.95),(55.65,6.90),(55.60,6.85),(55.55,6.87),(55.8,6.98)]:
    b=p.LoadBoard(str(source));site=p.VECTOR2I(p.FromMM(x),p.FromMM(y));changed=[];neck=None
    for t in b.GetTracks():
        if t.GetStart()!=origin and t.GetEnd()!=origin:continue
        assert t.GetNetname()=='+3V3_SYS'
        changed.append(t.m_Uuid.AsString())
        if isinstance(t,p.PCB_VIA):t.SetPosition(site)
        else:
            is_neck=t.GetLayer()==p.F_Cu
            old=t.GetLength()
            if t.GetStart()==origin:t.SetStart(site)
            else:t.SetEnd(site)
            if is_neck:neck=(old,t.GetLength())
    assert len(changed)==4 and neck
    if neck[1]>neck[0]:continue
    if any(q.GetBoundingBox().Inflate(276000).Contains(site) for f in b.GetFootprints() for q in f.Pads()):continue
    out=folder/source.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(prior,json.loads((folder/'drc.json').read_text()))
    if delta:print(x,y,delta[0]['type'],flush=True);continue
    saved=p.LoadBoard(str(out));pres=verify_preservation(base,saved,replaced_copper=changed);assert not screen(saved)
    record=dict(site_mm=[x,y],neck_mm=[n/1e6 for n in neck],preservation=pres);break
if not record:out=source
(root/'pmic-sda-clearance.json').write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],change=record,assembly_ready=False),indent=2)+'\n')
print(record and record['site_mm'],flush=True);os._exit(0)
