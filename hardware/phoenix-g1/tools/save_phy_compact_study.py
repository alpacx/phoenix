#!/usr/bin/env python3
"""Persist a verified experimental PCB separately from the working checkpoint."""
import hashlib,json,shutil,subprocess
from pathlib import Path
from drc_regression import introduced
H=Path(__file__).resolve().parents[1]
D=H/'migration-rk3562/experiments/pmic-ldo-inputs'
S=D.parent/'phy-compact-inductor';dest=S/'pcb';dest.mkdir(exist_ok=True)
from phy_study_source import load_source
cp,root=load_source(D)
proof=json.loads((D/'pcb/phy-compact-output-probe.json').read_text())
assert proof['status']=='COMPACT_OUTPUT_GEOMETRY_PASSED' and not proof['new_violations']
src=Path(proof['temporary_candidate']);assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['candidate_sha256']
assert hashlib.sha256(root.read_bytes()).hexdigest()==cp['sha256']==proof['source_sha256']
out=dest/'phy-compact-output.kicad_pcb';shutil.copy2(src,out)
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
table=(root.parent/'fp-lib-table').read_text().rstrip()[:-1]
table+='(lib (name "Phoenix_Compact") (type "KiCad") (uri "${KIPRJMOD}/../Phoenix_Compact.pretty") (options "") (descr "Experimental compact inductor"))'
table+='(lib (name "Capacitor_SMD") (type "KiCad") (uri "${KICAD10_FOOTPRINT_DIR}/Capacitor_SMD.pretty") (options "") (descr "KiCad 10 standard capacitor footprint")))'
(dest/'fp-lib-table').write_text(table+'\n')
drc=dest/'phy-compact-output-drc.json'
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
new=introduced(json.loads(root.with_name(root.stem+'-drc.json').read_text()),json.loads(drc.read_text()));assert not new,new
record={k:v for k,v in proof.items() if k!='temporary_candidate'}
record.update({'status':'EXPERIMENTAL_GEOMETRY_CHECKPOINT_NOT_SELECTED_BOM','board':str(out.relative_to(S)),'authoritative_checkpoint_modified':False,'new_violations_against_original_checkpoint':new,'requires_kicad_major':10,'production_ready':False})
(S/'study-checkpoint.json').write_text(json.dumps(record,indent=2)+'\n')
assert hashlib.sha256(root.read_bytes()).hexdigest()==cp['sha256']
print('Experimental board saved; root checkpoint unchanged; no new DRC violations.')
