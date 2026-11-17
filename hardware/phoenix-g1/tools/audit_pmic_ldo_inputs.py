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
 for stage in ['vcc7','vcc8','vcc6','vcc5','audio-input','rail-links','buck-input-link','upper-cap-grounds','upper-cap-power','rtc-link','vcc4-input','vcc9-link','system-feed','vdc-divider-input','vdc-passives','cpu-input-feed','five-volt-testpoint','display-led-feed','display-enable','display-buffer-bypass','display-buffer-feed','display-input-pulls','display-input-returns','display-reservoir','display-io-bleed','display-backlight-control','ethernet-reset-passives','ethernet-strap-grounds','ethernet-center-tap','ethernet-bias-grounds','ethernet-clock-placement','ethernet-clock-grounds','ethernet-clock-pins','ethernet-cap-grounds','ethernet-bypass-local','ethernet-avdd33-bypass','ethernet-io-power-link','ethernet-avdd10-escape','ethernet-io-bypass-escape','ethernet-dvdd33-bypass']:
  report=json.loads((D/'pcb'/f'{stage}.json').read_text())
  assert not report['new_violations'],stage
  checks.extend(report['checks'])
 for row in checks:
  a=tuple(row['from'].split('.')); z=tuple(row['to'].split('.'))
  assert pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in board.GetConnectivity().GetConnectedItems(pads[a])},('Required connection missing',a,z)
  row['connected']=True
 before={f.GetReference():f for f in original.GetFootprints()}; after={f.GetReference():f for f in board.GetFootprints()}
 assert before.keys()==after.keys()
 assert after['L501'].GetLayer()==p.F_Cu,'PHY inductor must remain on front'
 moved={'C480','TP4','R410','R411','C410','C1811','R1811','R1812','R1813','R1814','R1815','C1812','R1804','L501','Y501','C520','C521','C514','C516','C512','C517','C519','C1014','U23','R512','R522'}
 for ref,f in before.items():
  g=after[ref]; assert f.GetValue()==g.GetValue(),ref
  if ref not in moved:assert f.GetPosition()==g.GetPosition() and f.GetOrientationDegrees()==g.GetOrientationDegrees() and f.GetLayer()==g.GetLayer(),ref
 return {'checks':checks,'preservation':verify_preservation(original,board,replaced_copper=['2b4c51b6-4089-4afc-adf2-7897ca97383d','22adbd94-d53e-441a-af57-97409ae98b59']),'moved_refs':sorted(moved)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--board',type=Path);args=ap.parse_args()
 out=args.board or D/'pcb/ethernet-dvdd33-bypass.kicad_pcb';result=audit_board(p.LoadBoard(str(out)))
 if args.board:print('Alternate board audit passed; checkpoint unchanged.');return
 proof=json.loads((D/'pcb/ethernet-dvdd33-bypass.json').read_text());assert proof['status']=='ETHERNET_DVDD33_BYPASS_CONNECTED'
 sha=hashlib.sha256(out.read_bytes()).hexdigest(); assert sha==proof['sha256']
 assert src.with_suffix('.kicad_pro').read_bytes()==out.with_suffix('.kicad_pro').read_bytes()
 from phy_clock_rules import PHY_CLOCK_NECK_RULE
 assert out.with_suffix('.kicad_dru').read_text()==src.with_suffix('.kicad_dru').read_text()+PHY_CLOCK_NECK_RULE
 new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'pcb/ethernet-dvdd33-bypass-drc.json').read_text()));assert not new,new
 result.update(status='DISPLAY_AND_ETHERNET_PASSIVES_ROUTED_VDC_PIN61_OPEN_NOT_POWER_QUALIFIED',sha256=sha,source_sha256=cp['sha256'],new_violations=new,assembly_ready=False)
 (D/'pcb/final-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 (D/'working-candidate.json').write_text(json.dumps({'status':result['status'],'board':'pcb/ethernet-dvdd33-bypass.kicad_pcb','sha256':sha,'verification':'pcb/final-audit.json','schematic':cp['schematic'],'assembly_ready':False},indent=2)+'\n')
 print(json.dumps({'sha256':sha,'verified_pairs':len(result['checks']),'preservation':result['preservation']},indent=2))
if __name__=='__main__':main()
