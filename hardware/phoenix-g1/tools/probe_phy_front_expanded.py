#!/usr/bin/env python3
"""Bounded isolated placement experiment; never promote or overwrite the checkpoint."""
import hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
from isolated_pcb_libraries import copy_libraries
T=Path(__file__).resolve().parent;D=T.parent/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text())
assert hashlib.sha256((D/cp['board']).read_bytes()).hexdigest()==cp['sha256']
results=[]
with tempfile.TemporaryDirectory(prefix='phoenix-phy-joint-') as work:
 root=Path(work)/'hardware/phoenix-g1'
 shutil.copytree(T,root/'tools',ignore=shutil.ignore_patterns('__pycache__'))
 target=root/'migration-rk3562/experiments/pmic-ldo-inputs/pcb';target.mkdir(parents=True)
 copy_libraries(D,target.parent)
 for source in (D/'pcb').glob('ethernet-bias-grounds*'):shutil.copy2(source,target/source.name)
 script=root/'tools/route_ethernet_clock_placement.py';template=(D/'probe-inputs/clock-placement-before-front.py.in').read_text()
 template=template.replace('L501 moved to back side; switching-loop, via current and power layout not qualified.','L501 on front in this isolated trial; power routing and electrical qualification remain open.')
 template=template.replace("('L501',(64.5,29),0,p.B_Cu)","('L501',(57.4,30.8),180,p.F_Cu)")
 template=template.replace("for ref,xy,angle,layer in [","for ref,xy,angle,layer in [('C1014',(62,36),0,p.B_Cu),('U23',(74.5,32),0,p.F_Cu),")
 template=template.replace('for pin,ref',"\nf=next(f for f in b.GetFootprints() if f.GetReference()=='U23')\nf.Flip(f.GetPosition(),False)\nr=LocalRouter(b,(72,22,86,39),width=.2,grid=.05)\nr.pads=[q for q in r.pads if q.GetParentFootprint().GetReference()!='U23']\nobstacles=[g.GetCourtyard(p.B_Cu).BBox() for g in b.GetFootprints() if g.GetReference()!='U23' and g.GetLayer()==p.B_Cu]\nblocked={q.GetNumber():r.blocked(p.B_Cu,q.GetNetname(),math.hypot(p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y))) for q in f.Pads()}\nfrom audit_mount_component_reservations import screen\npositions=sorted([(x/4,y/4) for x in range(288,345) for y in range(88,157)],key=lambda xy:math.dist(xy,(76,27)))\nfound=False\nfor xy in positions:\n for angle in [0,90,180,270]:\n  f.SetPosition(vec(xy));f.SetOrientationDegrees(angle);box=f.GetCourtyard(p.B_Cu).BBox()\n  if any(box.Intersects(other) for other in obstacles):continue\n  if any(r.cell(r.xy(q)) in blocked[q.GetNumber()] for q in f.Pads()):continue\n  if any(row['ref']=='U23' for row in screen(b)):continue\n  moves['U23']=xy;found=True;break\n if found:break\nassert found,'No U23 placement found in bounded back search'\n"+'\nfor pin,ref')
 template=template.replace('(53,26,63,36)','(52,30,65,39)').replace('range(212,253)','range(208,261)').replace('range(104,145)','range(120,157)')
 for xy in [(57.75,34.8),(57.75,34.85),(57.65,34.8)]:
  script.write_text(template.replace("('Y501',(57.5,31.9),180,p.F_Cu)",f"('Y501',{xy},180,p.F_Cu)"))
  run=subprocess.run([sys.executable,str(script)],capture_output=True,text=True,timeout=90)
  path=target/('ethernet-clock-placement.json' if run.returncode==0 else 'ethernet-clock-joint-trial.json')
  evidence=json.loads(path.read_text()) if path.exists() else {'error':run.stderr[-1000:]}
  results.append({'crystal_center_mm':xy,'inductor_front_center_mm':[57.4,30.8],'exit_code':run.returncode,'evidence':evidence})
  print(xy,evidence.get('status'),flush=True)
  if evidence.get('status')=='ETHERNET_CLOCK_PLACEMENT_CONNECTED':
   shutil.copytree(root,Path('/tmp/phoenix-front-expanded-candidate'),dirs_exist_ok=True)
   break
report={'status':'ISOLATED_JOINT_PLACEMENT_EXPERIMENT','checkpoint_sha256':cp['sha256'],
 'baseline_sha256':hashlib.sha256((D/'pcb/ethernet-bias-grounds.kicad_pcb').read_bytes()).hexdigest(),
 'variants':results,'checkpoint_modified':False,'assembly_ready':False,
 'limitations':['Only local crystal/capacitor placement is tried; no complete power or clock routing qualification.',
 'A failed bounded search is not proof of impossibility.',
 'A successful local result is retained only in a temporary candidate directory; the authoritative checkpoint is not modified.']}
assert hashlib.sha256((D/cp['board']).read_bytes()).hexdigest()==cp['sha256']
(D/'pcb/phy-front-expanded-probe.json').write_text(json.dumps(report,indent=2)+'\n')
