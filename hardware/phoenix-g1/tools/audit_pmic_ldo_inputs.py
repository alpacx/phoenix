#!/usr/bin/env python3
"""Verify inherited and local system-converter copper; no electrical qualification."""
import argparse, hashlib, json
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments'
D=E/'pmic-ldo-inputs'; S=E/'system-3v3'
cp=json.loads((S/'working-candidate.json').read_text()); src=S/cp['board']
def audit_board(board):
 assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
 original=p.LoadBoard(str(src)); board.BuildConnectivity()
 pads={(f.GetReference(),q.GetNumber()):q for f in board.GetFootprints() for q in f.Pads()}
 checks=json.loads((S/cp['verification']).read_text())['checks']
 for stage in ['vcc7','vcc8','vcc6','vcc5','audio-input','rail-links','buck-input-link','upper-cap-grounds','upper-cap-power','rtc-link','vcc4-input','vcc9-link','system-feed','vdc-divider-input','vdc-passives']:
  report=json.loads((D/'pcb'/f'{stage}.json').read_text())
  assert not report['new_violations'],stage
  checks.extend(report['checks'])
 for row in checks:
  a=tuple(row['from'].split('.')); z=tuple(row['to'].split('.'))
  assert pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in board.GetConnectivity().GetConnectedItems(pads[a])},('Required connection missing',a,z)
  row['connected']=True
 before={f.GetReference():f for f in original.GetFootprints()}; after={f.GetReference():f for f in board.GetFootprints()}
 assert before.keys()==after.keys()
 moved={'C480','TP4','R410','R411','C410'}
 for ref,f in before.items():
  g=after[ref]; assert f.GetValue()==g.GetValue(),ref
  if ref not in moved:assert f.GetPosition()==g.GetPosition() and f.GetOrientationDegrees()==g.GetOrientationDegrees() and f.GetLayer()==g.GetLayer(),ref
 return {'checks':checks,'preservation':verify_preservation(original,board,replaced_copper=['2b4c51b6-4089-4afc-adf2-7897ca97383d','22adbd94-d53e-441a-af57-97409ae98b59']),'moved_refs':sorted(moved)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--board',type=Path);args=ap.parse_args()
 out=args.board or D/'pcb/vdc-passives.kicad_pcb';result=audit_board(p.LoadBoard(str(out)))
 if args.board:print('Alternate board audit passed; checkpoint unchanged.');return
 proof=json.loads((D/'pcb/vdc-passives.json').read_text());assert proof['status']=='VDC_PASSIVES_CONNECTED_PIN61_OPEN'
 sha=hashlib.sha256(out.read_bytes()).hexdigest(); assert sha==proof['sha256']
 for ext in ['.kicad_pro','.kicad_dru']:assert src.with_suffix(ext).read_bytes()==out.with_suffix(ext).read_bytes()
 new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'pcb/vdc-passives-drc.json').read_text()));assert not new,new
 result.update(status='SYSTEM_3V3_DISTRIBUTED_VDC_PIN61_OPEN_NOT_POWER_QUALIFIED',sha256=sha,source_sha256=cp['sha256'],new_violations=new,assembly_ready=False)
 (D/'pcb/final-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 (D/'working-candidate.json').write_text(json.dumps({'status':result['status'],'board':'pcb/vdc-passives.kicad_pcb','sha256':sha,'verification':'pcb/final-audit.json','schematic':cp['schematic'],'assembly_ready':False},indent=2)+'\n')
 print(json.dumps({'sha256':sha,'verified_pairs':len(result['checks']),'preservation':result['preservation']},indent=2))
if __name__=='__main__':main()
