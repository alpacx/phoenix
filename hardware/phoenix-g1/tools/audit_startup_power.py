#!/usr/bin/env python3
"""Audit saved copper, not converter stability, current capacity or boot readiness."""
import argparse,hashlib,json
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';D=E/'startup-power'
S=E/'aux-mount-clear';cp=json.loads((S/'working-candidate.json').read_text());src=S/cp['board']
STAGES=['cpu-switch','cpu-caps','cpu-output-bank','cpu-feedback','cpu-enable']
def audit_board(board):
 assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
 original=p.LoadBoard(str(src));board.BuildConnectivity()
 pads={(f.GetReference(),q.GetNumber()):q for f in board.GetFootprints() for q in f.Pads()}
 checks=[]
 for stage in STAGES:
  report=json.loads((D/'pcb'/f'{stage}.json').read_text())
  assert not report['new_violations'],stage
  checks.extend(report['checks'])
 checks.extend(json.loads((E/'pmic-inputs/pcb/input-audit.json').read_text())['checks'])
 checks.extend(json.loads((S/'pcb/final-audit.json').read_text())['lcd_checks'])
 checks.extend([{'from':'U4.24','to':'C423.1'},{'from':'C423.2','to':'C435.2'}])
 for row in checks:
  a=tuple(row['from'].split('.'));z=tuple(row['to'].split('.'))
  assert pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in board.GetConnectivity().GetConnectedItems(pads[a])},('Required connection missing',a,z)
  row['connected']=True
 original_fps={f.GetReference():f for f in original.GetFootprints()}
 fps={f.GetReference():f for f in board.GetFootprints()};assert fps.keys()==original_fps.keys()
 moved={'C423','L1001','U10','C1013','L402','C1002','C1012','C1011','L403','R1001','C1020','R1002'}
 for ref,f in original_fps.items():
  g=fps[ref];assert f.GetValue()==g.GetValue(),ref
  if ref not in moved:
   assert f.GetPosition()==g.GetPosition() and f.GetOrientationDegrees()==g.GetOrientationDegrees() and f.GetLayer()==g.GetLayer(),ref
 preservation=verify_preservation(original,board,replaced_copper=['72eba6e0-487a-4876-a998-3bc0edbe0318'])
 return {'checks':checks,'preservation':preservation,'moved_refs':sorted(moved)}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--board',type=Path);args=parser.parse_args()
 out=args.board or D/'pcb/cpu-enable.kicad_pcb'
 result=audit_board(p.LoadBoard(str(out)))
 if args.board:
  print('Alternate board connectivity audit passed; checkpoint not changed.');return
 proof=json.loads((D/'pcb/cpu-enable.json').read_text());assert proof['status']=='CPU_ENABLE_LOCAL_CONNECTED'
 sha=hashlib.sha256(out.read_bytes()).hexdigest();assert sha==proof['sha256']
 for ext in ['.kicad_pro','.kicad_dru']:assert src.with_suffix(ext).read_bytes()==out.with_suffix(ext).read_bytes()
 new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'pcb/cpu-enable-drc.json').read_text()));assert not new,new
 result.update(status='LOCAL_CPU_CONVERTER_AND_VCC3_ROUTED_NOT_POWER_QUALIFIED',source_sha256=cp['sha256'],sha256=sha,new_violations=new,assembly_ready=False)
 (D/'pcb/final-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 (D/'working-candidate.json').write_text(json.dumps({'status':result['status'],'board':'pcb/cpu-enable.kicad_pcb','sha256':sha,'verification':'pcb/final-audit.json','schematic':cp['schematic'],'assembly_ready':False},indent=2)+'\n')
 print(json.dumps({'sha256':sha,'verified_pairs':len(result['checks']),'preservation':result['preservation']},indent=2))
if __name__=='__main__':main()
