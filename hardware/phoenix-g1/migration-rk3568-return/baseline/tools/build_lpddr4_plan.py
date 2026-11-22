#!/usr/bin/env python3
"""SoC-side LPDDR4 migration plan; does not silently replace the DDR3 schematic."""
import csv,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    rows=list(csv.DictReader((ROOT/'review/rk3568-manufacturer-pins.csv').open()))
    signals=[]
    for row in rows:
        matches=[f for f in row['functions'].split(' | ') if f.startswith('LPDDR4_')]
        assert len(matches)<=1
        if matches:signals.append({'soc_ball':row['ball'],'function':matches[0],'ram_ball':None})
    names={r['function'] for r in signals}
    required={f'LPDDR4_DQ{i}_{ch}' for ch in 'AB' for i in range(16)}
    required|={f'LPDDR4_A{i}_{ch}' for ch in 'AB' for i in range(6)}
    required|={f'LPDDR4_{s}_{ch}' for ch in 'AB' for s in ['CLKP','CLKN','CKE0','CS0N','DM0','DM1','DQS0P','DQS0N','DQS1P','DQS1N']}
    required.add('LPDDR4_RESETN')
    assert required<=names,required-names
    assert len({r['soc_ball'] for r in signals})==len(signals)
    candidates=[]
    for code in ['C2803257','C2920231','C21177800','C27300677','C5330500','C2980378','C31863237','C46681827','C2840158','C20452602','C2920216','C20553875','C2920229']:
        d=json.loads((ROOT/f'sourcing/public/{code}.json').read_text())
        candidates.append({k:d.get(k) for k in ['componentCode','componentModelEn','canPresaleNumber','initialPrice','retrieved_utc','source_url']})
    report={'status':'MIGRATION PREPARATION - RAM MPN/ballout not selected; active schematic still DDR3',
      'target':'512MiB minimum, 1GiB optional; prefer one package with 32bit aggregate across two 16bit channels; exact ranks and loader support pending part selection',
      'selection_status':'No affordable stocked 512MiB candidate identified in checked JLC records; stocked 1GiB Samsung candidate exceeds memory budget expectations and is not selected',
      'capacity_policy':{'minimum_MiB':512,'optional_MiB':1024,'capacity_is_not_throughput_guarantee':True,'x16_requires_separate_controller_and_loader_validation':True},
      'signals':signals,'single_rank_required_signal_check':'PASS',
      'references':{'soc':'RK3568 vendor PinOut V1.1','rock3a':'https://dl.radxa.com/rock3/docs/hw/3a/radxa_rock_3a_v1310_schematic.pdf','zero3e':'https://dl.radxa.com/zero3/docs/hw/3e/radxa_zero_3e_v1200_schematic.pdf'},
      'important_differences':['ROCK3A sheet15 is LPDDR4X: VDDQ0.6V; do not copy that rail into LPDDR4 requiring1.1V.','ZERO3E uses RK3566; do not transfer its processor ball numbers to RK3568.','Radxa drawings use generic memory symbols; they do not establish the exact stocked chip/loader combination.'],
      'candidates':candidates,
      'required_changes':['Replace two DDR3 packages with selected200-ball package after checking actual datasheet.','Change PMIC DDR1.5V rail to required1.1V; add/qualify1.8V VDD1 and correct VDDQ.','Rebuild byte lanes, channel CA/CK/CS/CKE, reset and ZQ networks from actual ballout.','Replace DDR3 VREF/termination and bypass according to LPDDR4 requirements.','Revalidate loader geometry/training and power sequencing.','Regenerate schematic, BOM, placement and independent pin checks only after complete mapping.']}
    (ROOT/'review/lpddr4-migration.json').write_text(json.dumps(report,indent=2)+'\n')
    print(len(signals),'unique RK3568 LPDDR4 signals mapped; RAM-side mapping pending')
if __name__=='__main__':main()
