#!/usr/bin/env python3
"""Verify inherited and local system-converter copper; no electrical qualification."""
import argparse, hashlib, json
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments'
D=E/'system-3v3'; S=E/'startup-power'
cp=json.loads((S/'working-candidate.json').read_text()); src=S/cp['board']
def audit_board(board):
 assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
 original=p.LoadBoard(str(src)); board.BuildConnectivity()
 pads={(f.GetReference(),q.GetNumber()):q for f in board.GetFootprints() for q in f.Pads()}
 checks=json.loads((S/cp['verification']).read_text())['checks']
 for stage in ['local-power','control','input-feed']:
  report=json.loads((D/'pcb'/f'{stage}.json').read_text())
  assert not report['new_violations'],stage
  checks.extend(report['checks'])
 for row in checks:
  a=tuple(row['from'].split('.')); z=tuple(row['to'].split('.'))
  assert pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in board.GetConnectivity().GetConnectedItems(pads[a])},('Required connection missing',a,z)
  row['connected']=True
 before={f.GetReference():f for f in original.GetFootprints()}; after={f.GetReference():f for f in board.GetFootprints()}
 assert before.keys()==after.keys()
 moved={'L1301','R1301','C1301','C1302','C1303'}
 for ref,f in before.items():
  g=after[ref]; assert f.GetValue()==g.GetValue(),ref
  if ref not in moved:assert f.GetPosition()==g.GetPosition() and f.GetOrientationDegrees()==g.GetOrientationDegrees() and f.GetLayer()==g.GetLayer(),ref
 return {'checks':checks,'preservation':verify_preservation(original,board,replaced_copper=['52e0331e-9733-468d-aa1a-f5c192bc9fcd']),'moved_refs':sorted(moved)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--board',type=Path);args=ap.parse_args()
 out=args.board or D/'pcb/input-feed.kicad_pcb';result=audit_board(p.LoadBoard(str(out)))
 if args.board:print('Alternate board audit passed; checkpoint unchanged.');return
 proof=json.loads((D/'pcb/input-feed.json').read_text());assert proof['status']=='SYSTEM_INPUT_FEED_CONNECTED'
 sha=hashlib.sha256(out.read_bytes()).hexdigest(); assert sha==proof['sha256']
 for ext in ['.kicad_pro','.kicad_dru']:assert src.with_suffix(ext).read_bytes()==out.with_suffix(ext).read_bytes()
 new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'pcb/input-feed-drc.json').read_text()));assert not new,new
 result.update(status='LOCAL_SYSTEM_CONVERTER_ROUTED_NOT_POWER_QUALIFIED',sha256=sha,source_sha256=cp['sha256'],new_violations=new,assembly_ready=False)
 (D/'pcb/final-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 (D/'working-candidate.json').write_text(json.dumps({'status':result['status'],'board':'pcb/input-feed.kicad_pcb','sha256':sha,'verification':'pcb/final-audit.json','schematic':cp['schematic'],'assembly_ready':False},indent=2)+'\n')
 print(json.dumps({'sha256':sha,'verified_pairs':len(result['checks']),'preservation':result['preservation']},indent=2))
if __name__=='__main__':main()
