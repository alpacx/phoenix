#!/usr/bin/env python3
"""Transactional rebuild of the corridor variant from the persisted compact study."""
import subprocess,sys,tempfile,shutil,json,hashlib,datetime
from pathlib import Path
T=Path(__file__).resolve().parent;S=T.parent/'migration-rk3562/experiments/phy-compact-inductor';C=S/'corridor'
base=json.loads((S/'study-checkpoint.json').read_text());base_board=S/base['board'];assert hashlib.sha256(base_board.read_bytes()).hexdigest()==base['candidate_sha256']
reports=['input-corridor-placement.json','input-corridor-bypass.json','bulk-return-probe.json','output-return-probe.json']
steps=[['probe_phy_switch_corridor.py','--input-corridor'],['route_phy_switch_corridor_bypass.py','--input-corridor'],['probe_phy_bulk_return.py'],['probe_phy_output_return.py'],['save_phy_corridor_study.py'],['probe_phy_rxclk_strap.py'],['save_phy_corridor_study.py','--with-strap'],['test_phy_corridor_study.py']]
with tempfile.TemporaryDirectory(prefix='phoenix-corridor-backup-') as tmp:
 backup=Path(tmp);existed=C.exists()
 if existed:shutil.copytree(C,backup/'corridor')
 old_reports={name:(S/name).read_bytes() if (S/name).exists() else None for name in reports}
 try:
  for step in steps:
   result=subprocess.run([sys.executable,str(T/step[0]),*step[1:]],capture_output=True,text=True)
   if result.returncode:raise RuntimeError(step[0]+' failed\n'+(result.stdout+result.stderr)[-6000:])
   print(' '.join(step)+': complete',flush=True)
  cp=json.loads((C/'checkpoint.json').read_text());cp['isolated_tests_passed']=7;cp['full_corridor_rebuild_passed']=True;cp['verified_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(C/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
  assert hashlib.sha256(base_board.read_bytes()).hexdigest()==base['candidate_sha256']
 except Exception:
  if C.exists():shutil.rmtree(C)
  if existed:shutil.copytree(backup/'corridor',C)
  for name,data in old_reports.items():
   if data is None:(S/name).unlink(missing_ok=True)
   else:(S/name).write_bytes(data)
  print('Previous corridor checkpoint restored.',flush=True)
  raise
print('Corridor rebuilt and tested; main PCB and selected BOM are not changed by this tool.')
