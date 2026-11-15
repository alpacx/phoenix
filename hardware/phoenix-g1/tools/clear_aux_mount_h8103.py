#!/usr/bin/env python3
"""Move unrouted LCD bypasses next to U20; free H8103 mechanical reserve."""
import json,hashlib,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments'
S=E/'pmic-inputs';cp=json.loads((S/'working-candidate.json').read_text());src=S/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
D=E/'aux-mount-clear/pcb';D.mkdir(parents=True,exist_ok=True);out=D/'lcd-bypass-placement.kicad_pcb'
b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()}
placements={'C1801':(29.25,34.25),'C1802':(24.5,34.25),'R1815':(20,6.5)}
for ref,xy in placements.items():
 f=fs[ref];assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()),ref
 f.SetPosition(p.VECTOR2I(*(p.FromMM(v) for v in xy)))
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
shutil.copy2(src.parent/'fp-lib-table',D/'fp-lib-table')
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'lcd-bypass-placement-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'lcd-bypass-placement-drc.json').read_text()))
r={'status':'PLACEMENT_ACCEPTED' if not new else 'REJECTED_PLACEMENT','source_sha256':cp['sha256'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'positions_mm':placements,'new_violations':new,'assembly_ready':False}
if not new:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'lcd-bypass-placement.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
