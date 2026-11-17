#!/usr/bin/env python3
"""Bounded isolated placement experiment; never promote or overwrite the checkpoint."""
import hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
from isolated_pcb_libraries import copy_libraries
T=Path(__file__).resolve().parent;D=T.parent/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text())
assert hashlib.sha256((D/cp['board']).read_bytes()).hexdigest()==cp['sha256']
results=[]
# Wider capacitor search and crystal rotation are independent of the checkpoint.
with tempfile.TemporaryDirectory(prefix='phoenix-phy-joint-') as work:
 root=Path(work)/'hardware/phoenix-g1'
 shutil.copytree(T,root/'tools',ignore=shutil.ignore_patterns('__pycache__'))
 target=root/'migration-rk3562/experiments/pmic-ldo-inputs/pcb';target.mkdir(parents=True)
 copy_libraries(D,target.parent)
 for source in (D/'pcb').glob('ethernet-bias-grounds*'):shutil.copy2(source,target/source.name)
 script=root/'tools/route_ethernet_clock_placement.py';template=(D/'probe-inputs/clock-placement-before-front.py.in').read_text()
 template=template.replace('L501 moved to back side; switching-loop, via current and power layout not qualified.','L501 on front in this isolated trial; power routing and electrical qualification remain open.')
 template=template.replace("('L501',(64.5,29),0,p.B_Cu)","('L501',(57.5,31),0,p.F_Cu)")
 template=template.replace('(53,26,63,36)','(50,28,63,39)').replace('range(212,253)','range(200,253)').replace('range(104,145)','range(112,157)')
 for xy,angle in [((56,34.5),0),((56,34.5),90),((56,34.5),270),((55,34.5),0),((55,34.5),90),((55,34.5),270),((55,36),90),((55,36),270)]:
  script.write_text(template.replace("('Y501',(57.5,31.9),180,p.F_Cu)",f"('Y501',{xy},{angle},p.F_Cu)"))
  run=subprocess.run([sys.executable,str(script)],capture_output=True,text=True,timeout=90)
  path=target/('ethernet-clock-placement.json' if run.returncode==0 else 'ethernet-clock-joint-trial.json')
  evidence=json.loads(path.read_text()) if path.exists() else {'error':run.stderr[-1000:]}
  results.append({'crystal_center_mm':xy,'crystal_angle_deg':angle,'inductor_front_center_mm':[57.5,31],'exit_code':run.returncode,'evidence':evidence})
  print(xy,angle,evidence.get('status'),flush=True)
report={'status':'ISOLATED_JOINT_PLACEMENT_EXPERIMENT','checkpoint_sha256':cp['sha256'],
 'baseline_sha256':hashlib.sha256((D/'pcb/ethernet-bias-grounds.kicad_pcb').read_bytes()).hexdigest(),
 'variants':results,'checkpoint_modified':False,'assembly_ready':False,
 'limitations':['Only local crystal/capacitor placement is tried; no complete power or clock routing qualification.',
 'A failed bounded search is not proof of impossibility.',
 'Even a successful local result is discarded; inherited bypasses and full cumulative checks would need rebuilding.']}
assert hashlib.sha256((D/cp['board']).read_bytes()).hexdigest()==cp['sha256']
(D/'pcb/phy-clock-inductor-rotated-probe.json').write_text(json.dumps(report,indent=2)+'\n')
