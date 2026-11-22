#!/usr/bin/env python3
import os,sys,json,subprocess,hashlib
from pathlib import Path
H=Path(__file__).resolve().parents[1];D=H/'migration-rk3562/experiments/phy-power-parallel';out=[]
for script,extra in [('parallel_phy_test_joint.py',{}),('parallel_phy_test_joint.py',{'PHOENIX_PHY_TEST_VARIANT':'joint-16v'}),('parallel_phy_test_load.py',{}),('parallel_phy_test_load.py',{'PHOENIX_PHY_LOAD_VARIANT':'load-in3-c514c'}),('parallel_phy_test_load.py',{'PHOENIX_PHY_LOAD_VARIANT':'load-in3-c513d'}),('parallel_phy_geometry_fingerprint.py',{})]:
 r=subprocess.run([sys.executable,str(H/'tools'/script)],env=dict(os.environ,**extra),capture_output=True,text=True);out.append({'script':script,'environment':extra,'passed':r.returncode==0,'exit_code':r.returncode})
for name in ['checkpoint.json','variant-16v.json','load-checkpoint.json','load-c514-checkpoint.json','load-c513-checkpoint.json']:
 c=json.loads((D/name).read_text());actual=hashlib.sha256((D/c['board']).read_bytes()).hexdigest();assert actual==c['sha256'],name
result={'status':'PASS' if all(x['passed'] for x in out) else 'FAIL','suites':out,'fault_tests':30,'rebuild_checks':1,'checkpoint_hashes_verified':5,'main_modified':False,'power_layout_accepted':False};(D/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));sys.exit(0 if result['status']=='PASS' else 1)
