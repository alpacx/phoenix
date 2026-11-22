#!/usr/bin/env python3
"""Carry the already documented 16V capacitor candidate into latest PHY geometry."""
import pcbnew as p,json,hashlib,shutil,os,sys
from pathlib import Path
H=Path(__file__).resolve().parents[1];D=H/'migration-rk3562/experiments/phy-power-parallel';cp=json.loads((D/'load-c513-checkpoint.json').read_text());src=D/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));f=next(f for f in b.GetFootprints() if f.GetReference()=='C515');assert 'CL10A475KP8NNNC' in f.GetValue()
f.SetValue('4.7uF CL10A475KO8NNNC CANDIDATE 16V')
r=D/'runs/load-c513-16v';r.mkdir(exist_ok=True);out=r/'phy-joint.kicad_pcb'
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',r/'fp-lib-table');p.SaveBoard(str(out),b)
m={'source':str(src),'source_sha256':cp['sha256'],'candidate':str(out),'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'removed':[],'required_pairs':[[['C511','1'],['C512','1']],[['C511','1'],['C514','1']],[['C511','1'],['C513','1']],[['U5','8'],['C513','1']],[['C513','2'],['C515','2']]],'component_change':{'reference':'C515','from':'CL10A475KP8NNNC','to':'CL10A475KO8NNNC','jlc':'C19666','status':'CANDIDATE_NOT_MAIN_BOM','typical_capacitance_at_3v3_uF':3.2694,'guaranteed_minimum':None},'power_layout_accepted':False,'assembly_ready':False,'limitations':['Typical DC-bias curve is not a guaranteed minimum or stability verification.','All previous neck, via and remaining power distribution holds remain.']}
inherited=json.loads((src.parent/'report.json').read_text())
for key in ['routes','via_array','current_via_PI_qualified','via_pad_overlap_manufacturing_qualified','additional_pin_fanout_qualified','additional_pin_fanout_uuids']:m[key]=inherited[key]
mp=r/'input.json';mp.write_text(json.dumps(m,indent=2)+'\n');os.execv(sys.executable,[sys.executable,str(H/'tools/parallel_phy_sw_joint.py'),'--audit',str(mp)])
