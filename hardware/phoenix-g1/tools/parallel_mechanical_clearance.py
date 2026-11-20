#!/usr/bin/env python3
"""Isolated mounting-body clearance trial; preserves existing copper and netlist."""
import pcbnew as p, json, hashlib, shutil, subprocess, os, sys
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/mechanical-clearance-parallel'
S=D.parent/'pmic-ldo-inputs/pcb/ethernet-dvdd33-bypass.kicad_pcb'
D.mkdir(exist_ok=True); base=D/'baseline';base.mkdir(exist_ok=True)
src=base/'source.kicad_pcb';out=D/'mount-clearance.kicad_pcb'
if not src.exists():
 for ext in ['kicad_pcb','kicad_pro','kicad_dru']:shutil.copy2(S.with_suffix('.'+ext),src.with_suffix('.'+ext))
 shutil.copy2(S.parent/'ethernet-dvdd33-bypass-drc.json',base/'drc.json')
 (base/'checkpoint.json').write_text(json.dumps({'source':str(S),'sha256':hashlib.sha256(src.read_bytes()).hexdigest()},indent=2)+'\n')
assert hashlib.sha256(src.read_bytes()).hexdigest()=='bdeb44f58dea3d0261469c1d3f7eeb5a9e6df03e95648710393c9e09c83f6aeb'
if '--verify' in sys.argv:
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'drc.json'),str(out)],check=True,capture_output=True)
 a=p.LoadBoard(str(src));b=p.LoadBoard(str(out));new=introduced(json.loads((base/'drc.json').read_text()),json.loads((D/'drc.json').read_text()))
 old={(r['reservation'],r['ref']) for r in screen(a)};now={(r['reservation'],r['ref']) for r in screen(b)}
 result={'status':'PLACEMENT_ACCEPTED' if not new and not now-old else 'REJECTED','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'resolved_reservation_matches':sorted(old-now),'introduced_reservation_matches':sorted(now-old),'preservation':verify_preservation(a,b),'assembly_ready':False,'signal_routing_and_timing_qualified':False}
 (D/'checkpoint.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='new_violations'}), 'new violations',len(new),flush=True);os._exit(0)
table=(S.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(S.parent.resolve()))
(D/'fp-lib-table').write_text(table)
b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()}
moves={'R2014':(23,6.125,p.F_Cu),'R521':(67,28.5,p.B_Cu),'R525':(69,28,p.B_Cu),'R526':(71,29,p.B_Cu),'R527':(73,29.5,p.B_Cu)}
for ref,(x,y,layer) in moves.items():
 f=fs[ref]
 for q in f.Pads():assert not list(b.GetConnectivity().GetConnectedTracks(q)),ref
 if f.GetLayer()!=layer:f.Flip(f.GetPosition(),False)
 f.SetOrientationDegrees(0);f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)))
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
(D/'placement-delta.json').write_text(json.dumps({ref:{'center_mm':[x,y],'layer':b.GetLayerName(layer)} for ref,(x,y,layer) in moves.items()},indent=2)+'\n')
os.execv(sys.executable,[sys.executable,__file__,'--verify'])
