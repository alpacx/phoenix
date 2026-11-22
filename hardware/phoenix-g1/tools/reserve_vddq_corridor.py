"""Reserve a measured inner corridor on a work copy for rail-first recovery of expansion MOSI."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import pcbnew as p

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((root/n).read_text())
cp=read('layout-lpddr-vdd1-source.json')
src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
gaps=read('vddq-corridor-obstacles.json');assert gaps['parent_sha256']==cp['sha256']
row=next(x for x in gaps['trials'] if len(x['hits'])==1 and x['hits'][0]['net']=='EXP_SPI_MOSI')
b=p.LoadBoard(str(src));t=next(t for t in b.GetTracks() if t.m_Uuid.AsString()==row['hits'][0]['id'])
entry=dict(id=t.m_Uuid.AsString(),net=t.GetNetname(),layer=t.GetLayerName(),anchors_nm=[tuple(t.GetStart()),tuple(t.GetEnd())],width_nm=t.GetWidth())
b.Remove(t);folder=root/'runs/vddq-mosi-reserved';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
(root/'vddq-reserved-mosi.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),removed=entry,requires_restoration=True,assembly_ready=False),indent=2)+'\n')
