#!/usr/bin/env python3
"""Move dense bypass reference labels to assembly layers; retain all routing warnings."""
import pcbnew as p,json,shutil,subprocess,hashlib,collections
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5/pcb';src=D/'io-bypass.kicad_pcb';out=D/'layout-reviewed.kicad_pcb';b=p.LoadBoard(str(src));records=[]
for f in b.GetFootprints():
 if f.GetReference() in ['C2301','C2303','C2304','C2305','C2306']:
  f.Reference().SetLayer(p.B_Fab if f.GetLayer()==p.B_Cu else p.F_Fab);records.append({'ref':f.GetReference(),'change':'reference_to_assembly_layer'})
 if f.GetReference()=='U2':
  f.Reference().SetPosition(p.VECTOR2I(p.FromMM(30),p.FromMM(1.2)));f.Reference().SetTextSize(p.VECTOR2I(p.FromMM(1.0),p.FromMM(1.0)));f.Reference().SetTextThickness(p.FromMM(.15));records.append({'ref':'U2','change':'reference_inside_board'})
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'layout-reviewed-drc.json'),str(out)],check=True,capture_output=True)
a=json.loads((D/'io-bypass-drc.json').read_text());z=json.loads((D/'layout-reviewed-drc.json').read_text());new=introduced(a,z);assert not new,new
assert all(v['type']=='via_dangling' for v in z['violations']),collections.Counter(v['type'] for v in z['violations'])
assert sum(v['type']=='via_dangling' for v in a['violations'])==sum(v['type']=='via_dangling' for v in z['violations'])
report={'status':'REFERENCE_SILK_CLEARANCE_FIXED_ROUTING_WARNINGS_RETAINED','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'changes':records,'preservation':verify_preservation(p.LoadBoard(str(src)),b),'remaining_violations':dict(collections.Counter(v['type'] for v in z['violations'])),'new_violations':new,'assembly_ready':False};(D/'layout-reviewed.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
