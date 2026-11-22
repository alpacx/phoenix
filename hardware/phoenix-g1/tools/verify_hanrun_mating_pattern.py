"""Match the five even signal drill centers to the manufacturer drawing and recheck CAD."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from hanrun_pad_stagger import apply,even_centers,filename
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-coincident-cleanup.json').read_text());src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
folder=root/'runs/hanrun-hole-stagger';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru'):shutil.copy2(src.parent/name,folder/name)
table=(src.parent/'fp-lib-table').read_text()
pattern=r'(\(name "Phoenix_Reviewed"\).*?\(uri ")([^"]+)(")'
match=re.search(pattern,table);assert match
origin=Path(match[2]).resolve();library=root/'hanrun-reviewed.pretty';library.mkdir(exist_ok=True)
for original in origin.glob('*.kicad_mod'):
    dest=library/original.name
    if original.name==filename:
        shutil.copy2(original,dest);apply(dest)
    elif not dest.exists():dest.symlink_to(os.path.relpath(original,library))
table=re.sub(pattern,lambda m:m[1]+'${KIPRJMOD}/../../hanrun-reviewed.pretty'+m[3],table,count=1)
(folder/'fp-lib-table').write_text(table)
b=p.LoadBoard(str(src));jack=b.FindFootprintByReference('J2')
assert jack.GetOrientationDegrees()==-90 and jack.GetLayer()==p.F_Cu and jack.GetFPIDAsString()=='Phoenix_Reviewed:RJ45-TH_HR911130A'
libfp=p.FootprintLoad(str(library),Path(filename).stem)
assert libfp
changes=[]
for name,x in even_centers.items():
    pad=jack.FindPadByNumber(name);libpad=libfp.FindPadByNumber(name);pos=pad.GetPosition()
    expected=jack.GetPosition()+p.VECTOR2I(-libpad.GetPosition().y,libpad.GetPosition().x)
    assert expected-pos==p.VECTOR2I(0,-110000),(name,tuple(expected-pos))
    assert libpad.GetPosition().x==round(1e6*x)
    changes.append(dict(pad=name,before_nm=tuple(pos),after_nm=tuple(expected)))
    pad.SetPosition(expected)
# Raising this 0.4 mm ground return 0.1 mm in its middle restores the mounting-pad clearance.
uid='a03ed707-186c-4da8-8c14-f0807808f61f'
ground=next(t for t in b.GetTracks() if t.m_Uuid.AsString()==uid)
assert (tuple(ground.GetStart()),tuple(ground.GetEnd()),ground.GetWidth(),ground.GetNetname(),ground.GetLayer())==((71150000,23350000),(73550000,23350000),400000,'GND',p.B_Cu)
pts=[tuple(ground.GetStart()),(71250000,23250000),(73450000,23250000),tuple(ground.GetEnd())]
code=ground.GetNetCode();b.Remove(ground)
for start,end in zip(pts,pts[1:]):
    t=p.PCB_TRACK(b);t.SetLayer(p.B_Cu);t.SetNetCode(code);t.SetWidth(400000);t.SetStart(p.VECTOR2I(*start));t.SetEnd(p.VECTOR2I(*end));b.Add(t)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
saved=p.LoadBoard(str(out));preservation=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=[uid]);assert not screen(saved)
j=saved.FindFootprintByReference('J2')
for row in changes:assert tuple(j.FindPadByNumber(row['pad']).GetPosition())==tuple(row['after_nm'])
result=dict(source='reference/HR911130A.pdf, Rev A, p. 2',parent_sha256=meta['sha256'],changes=changes,preservation=preservation,new_drc=delta,assembly_ready=False)
if not delta:result.update(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest())
(root/'hanrun-hole-stagger.json').write_text(json.dumps(result,indent=2)+'\n')
print(len(changes),delta,flush=True);os._exit(0)
