#!/usr/bin/env python3
"""Reproducible Wi-Fi relocation subexperiment; fail closed on any generation/check error."""
import subprocess,json,os,hashlib,collections,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];T=R/'tools';P=R/'migration-rk3562/experiments/lpddr4-1gb';D=P/'wifi-relocation';PY='/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9';CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
def run(script,args=(),env=None):
 with (D/(Path(script).stem+'.log')).open('w') as log:subprocess.run([PY,str(T/script),*map(str,args)],check=True,env=env,stdout=log,stderr=log)
def check(stem):
 for ext in ['kicad_pro','kicad_dru']:
  if stem!='candidate':(D/(stem+'.'+ext)).write_text((D/('candidate.'+ext)).read_text())
 if stem=='io':
  with (D/'io.kicad_dru').open('a') as f:f.write("(rule \"PMIC IO neck width\" (condition \"A.NetName == '+3V3_IO'\") (constraint track_width (min 0.127mm)))\n")
 subprocess.run([CLI,'pcb','drc','--format','json','-o',str(D/(stem+'-drc.json')),str(D/(stem+'.kicad_pcb'))],check=True,stdout=subprocess.DEVNULL)
 r=json.loads((D/(stem+'-drc.json')).read_text());bad=[v for v in r['violations'] if v['type'] in ['shorting_items','clearance','hole_clearance','hole_to_hole','tracks_crossing','courtyards_overlap']];assert not bad,(stem,len(bad));print(stem,'geometry passed',flush=True)
def route(script,source,target,*options):
 run(script,[*options,'--input',D/(source+'.kicad_pcb'),'--output',D/(target+'.kicad_pcb'),'--report',D/(target+'-route.json')]);check(target)
def main():
 D.mkdir(exist_ok=True);(D/'verified-checkpoint.json').unlink(missing_ok=True)
 source=P/'system/kicad/pcb/phoenix-lpddr4-placement.kicad_pcb';before=hashlib.sha256(source.read_bytes()).hexdigest()
 run('screen_wifi_relocation.py');sites=json.loads((D/'placement-screen.json').read_text())['top_candidates'];index=next(i for i,r in enumerate(sites) if r['module_xy_mm']==[61.5,20])
 env=dict(os.environ,PHOENIX_WIFI_CHOICE=str(index),PHOENIX_WIFI_REROUTE_LOCAL='1');run('build_wifi_relocation_candidate.py',env=env);check('candidate')
 route('experiments/route_rk3562_wifi_vddio.py','candidate','vddio-first','--auto-bounds')
 route('route_rk3562_wifi_module_buck.py','vddio-first','local-power','--auto-bounds','--allow-output-vias')
 route('route_rk3562_wifi_module_ground.py','local-power','local-complete','--auto-bounds')
 route('route_rk3562_wifi_lpo.py','local-complete','lpo','--auto-bounds','--load-only')
 route('route_rk3562_wifi_module_supply.py','lpo','module-feed','--auto-bounds')
 route('route_rk3562_wifi_output.py','module-feed','feeds')
 route('route_relocated_wifi_io.py','feeds','io')
 run('audit_rk3562_wifi_converter.py',['--board',D/'io.kicad_pcb','--report',D/'io-audit.json','--require-local','--require-module-ground','--require-module-buck','--require-vddio-bypass','--require-module-supply','--require-lpo','--require-lpo-bypass'])
 run('audit_wifi_relocation.py')
 assert hashlib.sha256(source.read_bytes()).hexdigest()==before
 report={'status':'RELOCATION_WIFI_COPPER_VERIFIED_NOT_RELEASE','source_unchanged_sha256':before,'board_sha256':hashlib.sha256((D/'io.kicad_pcb').read_bytes()).hexdigest(),'module_xy_mm':[61.5,20],'CPU_escapes':60,'assembly_ready':False,'remaining':['Five CPU escapes and full DDR route','RF/crystal routes and full-board completion','Power integrity, return paths, timing, thermal and physical validation']};(D/'verified-checkpoint.json').write_text(json.dumps(report,indent=2)+'\n'); (P/'working-board.json').write_text(json.dumps({'status':'ENGINEERING_CANDIDATE_NOT_PRODUCTION','board':'wifi-relocation/io.kicad_pcb','verification':'wifi-relocation/preservation-audit.json','sha256':report['board_sha256'],'assembly_ready':False},indent=2)+'\n');print('Relocation checkpoint saved',flush=True)
if __name__=='__main__':main()
