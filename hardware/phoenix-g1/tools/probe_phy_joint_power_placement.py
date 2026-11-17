#!/usr/bin/env python3
"""Isolated joint PHY placement; disconnects are reported, never promoted."""
import argparse,hashlib,json,subprocess,shutil,tempfile
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
parser=argparse.ArgumentParser();parser.add_argument('--moves',type=Path);parser.add_argument('--compact-inductor',action='store_true');parser.add_argument('--bulk-0603',action='store_true');args=parser.parse_args()
moves=json.loads(args.moves.read_text()) if args.moves else {'L501':[57.4,29.8,90,'F'],'C511':[57.5,32.5,0,'F'],'C517':[61.5,27,90,'F'],'R511':[60.5,27,0,'B'],'R522':[55.5,27.5,0,'B']}
from phy_study_source import load_source
cp,src=load_source(D);assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));old=p.LoadBoard(str(src));fs={f.GetReference():f for f in b.GetFootprints()}
if args.compact_inductor:
 library=D.parent/'phy-compact-inductor/Phoenix_Compact.pretty'
 old_l=fs['L501'];new_l=p.FootprintLoad(str(library),'L_AFE252012')
 oldpads={q.GetNumber():q for q in old_l.Pads()}
 new_l.SetReference('L501');new_l.SetValue('2.2uH DCR65m max CANDIDATE');new_l.SetFPID(p.LIB_ID('Phoenix_Compact','L_AFE252012'));new_l.SetUuid(old_l.m_Uuid)
 for q in new_l.Pads():q.SetUuid(oldpads[q.GetNumber()].m_Uuid);q.SetNet(oldpads[q.GetNumber()].GetNet())
 b.Remove(old_l);b.Add(new_l);fs['L501']=new_l
if args.bulk_0603:
 caplib=Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Capacitor_SMD.pretty')
 for ref in ['C511','C515']:
  old_c=fs[ref];oldpads={q.GetNumber():q for q in old_c.Pads()}
  cap_io=p.PCB_IO_KICAD_SEXPR();new_c=cap_io.FootprintLoad(str(caplib),'C_0603_1608Metric',False)
  new_c.SetReference(ref);new_c.SetValue('4.7uF CL10A475KP8NNNC CANDIDATE');new_c.SetFPID(p.LIB_ID('Capacitor_SMD','C_0603_1608Metric'));new_c.SetUuid(old_c.m_Uuid)
  for q in new_c.Pads():q.SetUuid(oldpads[q.GetNumber()].m_Uuid);q.SetNet(oldpads[q.GetNumber()].GetNet())
  b.Remove(old_c);b.Add(new_c);fs[ref]=new_c;new_c.Reference().SetVisible(False)
for ref,(x,y,angle,side) in moves.items():
 f=fs[ref];target=p.F_Cu if side=='F' else p.B_Cu
 if f.GetLayer()!=target:f.Flip(f.GetPosition(),False)
 f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));f.SetOrientationDegrees(angle)
outdir=Path(tempfile.mkdtemp(prefix='phoenix-joint-power-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
table=(src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent))
if args.compact_inductor:table=table.rstrip()[:-1]+'(lib (name \"Phoenix_Compact\") (type \"KiCad\") (uri \"'+str(library)+'\") (options \"\") (descr \"Candidate\")))'
if args.bulk_0603:table=table.rstrip()[:-1]+'(lib (name \"Capacitor_SMD\") (type \"KiCad\") (uri \"'+str(caplib)+'\") (options \"\") (descr \"KiCad standard library\")))'
(outdir/'fp-lib-table').write_text(table)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
drc=outdir/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
raw=json.loads(drc.read_text());new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),raw)
ids={i for v in new for i in v['items']}
details=[v for v in raw['violations'] if any(i['uuid'] in ids for i in v['items'])]
key=lambda r:(r['reservation'],r['ref'])
result={'status':'JOINT_PLACEMENT_ONLY_NOT_ROUTED','source_sha256':cp['sha256'],'moves':moves,'new_violations':new,'details':details,'mechanical_conflicts':sorted({key(r) for r in screen(b)}-{key(r) for r in screen(old)}),'temporary_candidate':str(out),'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'checkpoint_modified':False,'assembly_ready':False,'limitations':['Moved pads are not rerouted. Ground and signal continuity must be restored before acceptance.','No power-current or oscillator qualification; original checkpoint untouched.']}
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
(D/'pcb'/('phy-compact-0603-placement-probe.json' if args.bulk_0603 else 'phy-compact-power-placement-probe.json' if args.compact_inductor else 'phy-joint-power-placement-probe.json')).write_text(json.dumps(result,indent=2)+'\n')
from collections import Counter
print(dict(Counter(v['type'] for v in new)))
