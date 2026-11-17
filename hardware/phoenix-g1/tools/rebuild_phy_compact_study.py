#!/usr/bin/env python3
"""Rebuild only the experimental compact PHY variant from its frozen baseline."""
import os,subprocess,sys
from pathlib import Path
T=Path(__file__).resolve().parent
S=T.parent/'migration-rk3562/experiments/phy-compact-inductor'
env=dict(os.environ,PHOENIX_PHY_FROZEN_BASELINE='1')
steps=[['probe_phy_joint_power_placement.py','--compact-inductor','--bulk-0603','--moves',str(S/'moves.json')],['probe_phy_compact_ground.py','--bulk-0603','--reserve-output'],['probe_phy_compact_output.py'],['save_phy_compact_study.py'],['test_phy_compact_study.py']]
for step in steps:
 result=subprocess.run([sys.executable,str(T/step[0]),*step[1:]],env=env,capture_output=True,text=True)
 if result.returncode:print((result.stdout+result.stderr)[-6000:]);raise SystemExit(result.returncode)
 print(step[0]+': complete',flush=True)
print('Experimental study rebuilt; no authoritative checkpoint or BOM promotion.')
