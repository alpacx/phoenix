#!/usr/bin/env python3
"""Integrate validated ground additions and mounting clearance, excluding PHY BOM trials."""
import pcbnew as p,json,hashlib,shutil,subprocess,sys,os,math
from pathlib import Path
from parallel_control_apply_delta import apply
from parallel_control_apply_lcd_delta import apply as apply_lcd
from parallel_control_apply_ground_vias_delta import apply as apply_ground_vias
from parallel_control_apply_ram_ground_vias_delta import apply as apply_ram_ground_vias
from parallel_control_apply_middle_ground_vias_delta import apply as apply_middle_ground_vias
from parallel_control_apply_right_ground_vias_delta import apply as apply_right_ground_vias
from parallel_mechanical_apply_h8104 import apply as apply_h8104
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb';src=D/'ethernet-dvdd33-bypass.kicad_pcb';out=D/'parallel-local-copper.kicad_pcb'
MOVES={'R2014':(23,6.125,p.F_Cu),'R521':(67,28.5,p.B_Cu),'R525':(69,28,p.B_Cu),'R526':(71,29,p.B_Cu),'R527':(73,29.5,p.B_Cu)}
if '--verify' in sys.argv:
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'parallel-local-copper-drc.json'),str(out)],check=True,capture_output=True)
 a=p.LoadBoard(str(src));b=p.LoadBoard(str(out));b.BuildConnectivity();pads={f.GetReference()+'.'+q.GetNumber():q for f in b.GetFootprints() for q in f.Pads()}
 meta=json.loads((D/'parallel-local-copper-delta.json').read_text());checks=meta['verified_pairs']
 for row in checks:row['connected']=pads[row['to']].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[row['from']])}
 new=introduced(json.loads((D/'ethernet-dvdd33-bypass-drc.json').read_text()),json.loads((D/'parallel-local-copper-drc.json').read_text()))
 key=lambda r:(r['reservation'],r['ref']);before={key(r) for r in screen(a)};after={key(r) for r in screen(b)}
 from parallel_local_copper_checks import validate
 validate(b)
 result={'status':'PARALLEL_LOCAL_COPPER_CONNECTED' if not new and not after-before and all(r['connected'] for r in checks) else 'REJECTED','checks':checks,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'introduced_mechanical_conflicts':sorted(after-before),'resolved_mechanical_conflicts':sorted(before-after),'preservation':verify_preservation(a,b),'moved_refs':list(MOVES)+['C1661','C1674','C2301'],'new_holes':['H8104','H8105'],'assembly_ready':False,'limitations':['GND continuity is not decoupling-loop or power-integrity qualification.','H8105 is an M2 NPTH with 5.4mm body reserve, screw length/enclosure/thermal stack not qualified.','PHY alternative inductor/capacitor trials are excluded.']}
 (D/'parallel-local-copper.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);os._exit(0 if result['status']=='PARALLEL_LOCAL_COPPER_CONNECTED' else 1)
proof=json.loads((D/'ethernet-dvdd33-bypass.json').read_text());assert proof['status']=='ETHERNET_DVDD33_BYPASS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()}
for ref,(x,y,layer) in MOVES.items():
 f=fs[ref];assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()),ref
 if f.GetLayer()!=layer:f.Flip(f.GetPosition(),False)
 f.SetOrientationDegrees(0);f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)))
assert not any(r['reservation'].startswith(('H8103 ','H8105 ')) and r['ref']!=r['reservation'].split()[0] for r in screen(b))
f=p.FootprintLoad('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/MountingHole.pretty','MountingHole_2.2mm_M2');assert f
f.SetReference('H8105');f.SetAttributes(f.GetAttributes()|p.FP_BOARD_ONLY|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES);f.Reference().SetLayer(p.F_Fab);f.SetPosition(p.VECTOR2I(p.FromMM(70),p.FromMM(34)));b.Add(f)
meta=apply(b)
lcd=apply_lcd(b);meta['verified_pairs']+=lcd['verified_pairs'];meta['lcd_added_copper']=lcd['added_copper']
for name,fn in [('ground_vias',apply_ground_vias),('ram_ground_vias',apply_ram_ground_vias),('middle_ground_vias',apply_middle_ground_vias)]:
 extra=fn(b);meta['verified_pairs']+=extra['verified_pairs'];meta[name]=extra
extra=apply_right_ground_vias(b,Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel/right-ground-safe-delta.json')
meta['verified_pairs']+=extra['verified_pairs'];meta['right_ground_safe']=extra
meta['auxiliary_mount']=apply_h8104(b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);(D/'parallel-local-copper-delta.json').write_text(json.dumps(meta,indent=2)+'\n');os.execv(sys.executable,[sys.executable,__file__,'--verify'])
