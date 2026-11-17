#!/usr/bin/env python3
import hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
import pcbnew as p
from phy_reset_pin_route import add_reset_pin_route
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text());src=D/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));route=add_reset_pin_route(b)
outdir=Path(tempfile.mkdtemp(prefix='phoenix-reset-pin-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
(outdir/'fp-lib-table').write_text((src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent)))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);b.BuildConnectivity()
drc=outdir/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads(drc.read_text()))
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
connected=pads['R515','2'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['U5','12'])}
r={'status':'RESET_PIN_GEOMETRY_PASSED' if not new and connected else 'RESET_PIN_REJECTED','source_sha256':cp['sha256'],'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'temporary_candidate':str(out),'route':route,'new_violations':new,'connected':connected,'preservation':verify_preservation(p.LoadBoard(str(src)),b),'checkpoint_modified':False,'assembly_ready':False}
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
(D/'pcb/phy-reset-pin-probe.json').write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
