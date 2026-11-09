#!/usr/bin/env python3
"""Create a new RK3562 physical draft, leaving the RK3568 board untouched.
Use KiCad Python. Candidate footprint override is deliberately explicit.
"""
from pathlib import Path
import json
import build_floorplan as f
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'migration-rk3562'
# Reuse only net topology for source-termination placement. Numerical RK3568
# constraints are excluded so they cannot be mistaken for RK3562 signoff rules.
p=json.loads((ROOT/'review/highspeed-routing-plan.json').read_text())
(OUT/'review/highspeed-routing-plan.json').write_text(json.dumps({'status':'SOURCE TERMINATION PLACEMENT TOPOLOGY ONLY; NO RK3562 TIMING OR IMPEDANCE QUALIFICATION','rgmii_paths':p['rgmii_paths'],'provenance':'Baseline topology, same Ethernet net names; ball positions come from new RK3562 footprint.'},indent=2)+'\n')
f.ROOT=OUT;f.K=OUT/'kicad';f.OUT=f.K/'floorplan';f.OUT.mkdir(exist_ok=True)
seed=json.loads((OUT/'review/placement-seed.json').read_text())['placement']
# Preserve verified divider placement as well as unrelated component groups.
f.main({'U1':'Phoenix_RK3562_Candidates:RK3562_FCCSP478_13.9mm_MIXED_PITCH_CANDIDATE'}, {'R1901':(6,3.5,0),'R1902':(9,3.5,0),'C1903':(4,7,1),'C1101':(22.5,17,0),'C1102':(24,19,0),'U13':(19,25,0),'U14':(17,15,0),'U19':(21,15,0),'U9':(11,20,0),'U7':(10.5,17,0),'U8':(10.5,26,0),'R606':(14,23,0),'R605':(14,24.5,0),'R601':(14,26,0)}, {'U9':-90}, {'U6':(17,20,0),'U9':(11,17,-90)}, [{'side':1,'rect_mm':[5.8,6.8,9.2,9.2],'reason':'U24 thermal via assembly clearance'}, {'side':1,'rect_mm':[15.3,19.1,18.7,20.9],'reason':'U6 thermal via assembly clearance'}], seed)
