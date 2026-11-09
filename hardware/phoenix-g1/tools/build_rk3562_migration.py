#!/usr/bin/env python3
"""Separate migration schematic. Pending pins remain explicitly named, never NC."""
import csv,json,math
from pathlib import Path
import sexpdata as sx
import schematic_builder as sb
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'migration-rk3562';sb.ROOT=OUT
rows=list(csv.DictReader((OUT/'review/manufacturer-pins.csv').open()))
allocation=json.loads((OUT/'review/initial-function-allocation.json').read_text())
mapping={s['soc_ball']:s['net'] for s in allocation['signals']}
power=json.loads((OUT/'review/candidate-power-map.json').read_text())['pins']
for p in power:
 assert p['ball'] not in mapping
 mapping[p['ball']]=p['net']
signal_types={p['ball']:p['erc_type'] for p in json.loads((OUT/'review/signal-electrical-types.json').read_text())['pins']}
unused_by_design={p['ball'] for p in json.loads((OUT/'review/pending-pin-audit.json').read_text())['pins'] if p['schematic_disposition']=='NC_BY_DESIGN'}
grounded_inputs={p['ball'] for p in json.loads((OUT/'review/pending-pin-audit.json').read_text())['pins'] if p['schematic_disposition']=='GND_BY_DESIGN'}
assert not (unused_by_design|grounded_inputs).intersection(mapping)
mapping.update({b:'GND' for b in grounded_inputs})
signal_types.update({b:'input' for b in grounded_inputs})
q=sb.q
name='RK3562_MIGRATION'
symbol=sx.loads(f'(symbol {q(name)} (pin_names (offset 1.016)) (in_bom yes) (on_board yes) (property "Reference" "U" (at 0 0 0) (effects (font (size 1 1)))) (property "Value" "RK3562" (at 0 0 0) (effects (font (size 1 1)))))')
units=[rows[i:i+40] for i in range(0,len(rows),40)]
for n,unitrows in enumerate(units,1):
 unit=sx.loads(f'(symbol {q(name+"_"+str(n)+"_1")} (rectangle (start -43.18 27.94) (end 43.18 -27.94) (stroke (width 0) (type default)) (fill (type background))))')
 for i,r in enumerate(unitrows):
  right=i>=20;x=45.72 if right else -45.72;y=25.4-2.54*(i%20);a=180 if right else 0
  # Model selected active functions; unresolved pins remain passive and PENDING.
  label=mapping.get(r['ball'],r['name'].split('/')[0])
  kind='power_in' if r['ball'] in {p['ball'] for p in power} else signal_types.get(r['ball'],('input' if r['name']=='USB30_OTG0_ID' else 'output' if 'DDR3_' in r['name'] else 'bidirectional') if r['ball'] in unused_by_design else 'passive')
  unit.append(sx.loads(f'(pin {kind} line (at {x} {y} {a}) (length 2.54) (name {q(label)} (effects (font (size .8 .8)))) (number {q(r["ball"])} (effects (font (size 1 1)))))'))
 symbol.append(unit)
(OUT/'kicad/sym-lib-table').write_text('(sym_lib_table\n)\n')
sb.save_library('Phoenix_RK3562',{name:symbol})
all_contract=[]
for n,unitrows in enumerate(units,1):
 sh=sb.Sheet(f'rk3562-pins-{n:02d}','Phoenix - RK3562 MIGRATION, incomplete','Phoenix_RK3562',{name:symbol})
 sh.place(name,'U1',190.5,111.76,{r['ball']:mapping.get(r['ball'],None if r['ball'] in unused_by_design else 'PENDING_'+r['ball']) for r in unitrows},value='RK3562',mpn='RK3562',fp='',unit=n)
 sh.note('MIGRATION ONLY. No qualified footprint. Active signal directions modelled; unresolved types remain unreviewed.',20,185)
 sh.note('PENDING labels are unresolved connections, not permission to leave balls floating.',20,195)
 sh.note('DDR, USB and clock mappings require independent audit before integration.',20,205)
 sh.save();all_contract+=sh.contract
(OUT/'review/schematic-status.json').write_text(json.dumps({'status':'PARTIAL MIGRATION; NOT COMPLETE BOARD','total_pins':len(all_contract),'mapped_signals':len(allocation['signals']),'mapped_ground_supply_pins':len(power),'mapped_pins_total':len(mapping),'pending_pins':len(rows)-len(mapping)-len(unused_by_design),'pins_nc_by_design':len(unused_by_design),'electrical_types_reviewed':False,'active_signal_directions_modelled':len(signal_types)-len(grounded_inputs),'unused_analog_inputs_grounded':len(grounded_inputs),'footprint_qualified':False,'assembly_ready':False},indent=2)+'\n')
print('Created12 migration pin sheets; active legacy schematic untouched')
