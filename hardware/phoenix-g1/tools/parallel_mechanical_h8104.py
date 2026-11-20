#!/usr/bin/env python3
"""Explore alternate auxiliary mounting point while preserving all routed copper."""
import pcbnew as p,json,hashlib,shutil,subprocess,sys,os
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/mechanical-clearance-parallel/h8104';D.mkdir(exist_ok=True)
S=D.parents[1]/'pmic-ldo-inputs/pcb/parallel-local-copper.kicad_pcb';src=D/'source.kicad_pcb';out=D/'candidate.kicad_pcb'
if not src.exists():
 for ext in ['kicad_pcb','kicad_pro','kicad_dru']:shutil.copy2(S.with_suffix('.'+ext),src.with_suffix('.'+ext))
 shutil.copy2(S.parent/'parallel-local-copper-drc.json',D/'source-drc.json');(D/'fp-lib-table').write_text((S.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(S.parent.resolve())))
if '--verify' in sys.argv:
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'drc.json'),str(out)],check=True,capture_output=True)
 a=p.LoadBoard(str(src));b=p.LoadBoard(str(out));new=introduced(json.loads((D/'source-drc.json').read_text()),json.loads((D/'drc.json').read_text()))
 rows=screen(b);blockers=[r for r in rows if r['reservation']=='H8104 mechanical reservation']
 result={'status':'CANDIDATE_CLEAR' if not new and not blockers else 'REJECTED','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'h8104_blockers':blockers,'preservation':verify_preservation(a,b),'assembly_ready':False,'power_integrity_and_thermal_bracket_qualified':False}
 (D/'checkpoint.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],len(new),blockers,flush=True);os._exit(0)
b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()}
for ref,xy in {'C1661':(22.5,12),'C1674':(25,3),'C2301':(24.5,9.5)}.items():
 f=fs[ref];assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()),ref;f.SetPosition(p.VECTOR2I(*(p.FromMM(v) for v in xy)))
fs['C2301'].SetOrientationDegrees(90)
fs['C2308'].Reference().SetLayer(p.B_Fab)
z=next(z for z in b.Zones() if z.GetZoneName()=='H8104 mechanical reservation');z.Move(p.VECTOR2I(p.FromMM(20.25-37),p.FromMM(9-31)))
assert not any(r['reservation']=='H8104 mechanical reservation' for r in screen(b))
f=p.FootprintLoad('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/MountingHole.pretty','MountingHole_2.2mm_M2');assert f
f.SetReference('H8104');f.SetAttributes(f.GetAttributes()|p.FP_BOARD_ONLY|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES);f.Reference().SetLayer(p.F_Fab);f.SetPosition(p.VECTOR2I(p.FromMM(20.25),p.FromMM(9)));b.Add(f)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);os.execv(sys.executable,[sys.executable,__file__,'--verify'])
