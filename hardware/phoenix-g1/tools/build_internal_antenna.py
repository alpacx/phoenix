#!/usr/bin/env python3
"""Standalone RF candidate. Does not mutate the verified routed board."""
import json,copy
from pathlib import Path
import schematic_builder as s
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'migration-rk3562/experiments/internal-antenna'
for name in ('kicad','review','kicad/Phoenix_Antenna.pretty'):(OUT/name).mkdir(parents=True,exist_ok=True)
syms=s.load_symbols([],['R','L','C'])
syms['W3006']=s.sx.loads('''(symbol "W3006" (pin_names (offset 0)) (in_bom yes) (on_board yes)
(property "Reference" "AE" (at 0 5 0) (effects (font (size 1 1))))
(property "Value" "W3006" (at 0 -5 0) (effects (font (size 1 1))))
(symbol "W3006_0_1" (rectangle (start -5 3) (end 5 -3) (stroke (width 0.254) (type default)) (fill (type background))))
(symbol "W3006_1_1"
(pin passive line (at -7.62 0 0) (length 2.62) (name "RF_FEED" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1)))))
(pin no_connect line (at 7.62 0 180) (length 2.62) (name "SUPPORT_FLOATING" (effects (font (size 1 1)))) (number "2" (effects (font (size 1 1)))))))''')
s.ROOT=OUT
(OUT/'kicad/sym-lib-table').write_text('(sym_lib_table)\n')
s.save_library('Phoenix_Antenna',syms)
sh=s.Sheet('internal-antenna','Phoenix - internal/external RF selection candidate','Phoenix_Antenna',syms)
fp='Phoenix_Antenna:W3006_Layout1'
sh.place('W3006','AE2001',210.82,81.28,{'1':'WIFI_INT_ANT','2':None},fp=fp,mpn='W3006')
sh.place('R','R2005',60.96,81.28,{'1':'WIFI_RF','2':'WIFI_INT_MATCH'},'0R INTERNAL FIT','Resistor_SMD:R_0402_1005Metric')
sh.place('R','R2006',121.92,81.28,{'1':'WIFI_INT_MATCH','2':'WIFI_INT_ANT'},'0R SERIES TUNING','Resistor_SMD:R_0402_1005Metric')
sh.place('L','L2002',182.88,132.08,{'1':'WIFI_INT_ANT','2':'GND'},'1.5nH STARTING VALUE - TUNE','Inductor_SMD:L_0402_1005Metric')
sh.place('C','C2010',101.6,132.08,{'1':'WIFI_INT_MATCH','2':'GND'},'DNP SHUNT TUNING','Capacitor_SMD:C_0402_1005Metric')
sh.place('R','R2001',60.96,190.5,{'1':'WIFI_RF','2':'WIFI_ANT'},'0R EXTERNAL DNP','Resistor_SMD:R_0402_1005Metric')
for i,n in enumerate(['CANDIDATE ONLY: replaces existing R2001 branch; not an extra parallel assembled antenna.', 'Default: R2005 fitted / R2001 DNP. External variant: R2005 DNP / R2001 fitted.', 'WIFI_RF = AP6256 pin2; WIFI_ANT = existing U.FL J2001 pin1. Keep selector immediately at branch.', 'W3006 pad2 is mechanical support: solder to floating isolated pad, NOT ground.', 'Layout1 manufacturer p6-7: reserve all-layer clearance; case/heatsink must leave RF window.', '1.5nH is evaluation-board value, not qualified for Phoenix. Measure matching in final case.']):sh.note(n,15,230+i*7)
sh.save()
f=OUT/'kicad/internal-antenna.kicad_sch';tree=s.sx.loads(f.read_text())
for item in s.fields(tree,'symbol'):
 props={p[1]:p[2] for p in s.fields(item,'property')}
 if props.get('Reference') in ('R2001','C2010'):s.fields(item,'dnp')[0][1]=s.sx.Symbol('yes')
f.write_text(s.sx.dumps(tree)+'\n')
# Pad widths and centre spacing transcribed from manufacturer issue2137 p7.
# Local x positive toward feed; y positive toward board interior.
text='''(footprint "W3006_Layout1" (version 20241229) (generator "pcbnew") (layer "F.Cu") (attr smd)
(property "Reference" "AE2001" (at 0 -3) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))
(property "Value" "W3006" (at 0 3) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))
(fp_rect (start -5 -1.6) (end 5 1.6) (stroke (width .05) (type default)) (fill none) (layer "F.Fab"))
(fp_rect (start -5.5 -2.1) (end 5.5 2.1) (stroke (width .05) (type default)) (fill none) (layer "F.CrtYd"))
(pad "1" smd rect (at 4.55 0) (size 1.7 2.8) (layers "F.Cu" "F.Paste" "F.Mask"))
(pad "2" smd rect (at -4.55 0) (size 1.7 2.8) (layers "F.Cu" "F.Paste" "F.Mask"))
)
'''
(OUT/'kicad/Phoenix_Antenna.pretty/W3006_Layout1.kicad_mod').write_text(text)
(OUT/'kicad/fp-lib-table').write_text('(fp_lib_table (lib (name "Phoenix_Antenna")(type "KiCad")(uri "${KIPRJMOD}/Phoenix_Antenna.pretty")(options "")(descr "Candidate - RF qualification pending")))\n')
report={'status':'CIRCUIT_AND_FOOTPRINT_CANDIDATE_NOT_INTEGRATED','part':'W3006','jlc':'C5123155','price_usd_1plus':0.9074,'public_presale':623,'public_overseas':625,'stock_checked':'2026-11-18','source':'https://productfinder.pulseeng.com/doc_type/WEB301/doc_num/W3006/doc_part/W3006.pdf','layout':1,'body_mm':[10,3.2,1.5],'all_layer_reservation_envelope_mm':[14.15,7.4],'notes':['Envelope screening is conservative; final polygon must follow layer-specific drawing p6.','No auto switching: assembly alternatives, never populate both selectors.','JLC presale/overseas do not guarantee immediate assembly allocation.'],'holds':['placement conflict resolution','controlled-impedance feed and branch stub','matching component selection and RF tuning','enclosure/heatsink RF clearance','integration into active schematic/BOM/rebuild pipeline','physical RF qualification']}
(OUT/'checkpoint.json').write_text(json.dumps(report,indent=2)+'\n')

(OUT/'kicad/fp-lib-table').write_text('(fp_lib_table '+ '(lib (name "Phoenix_Antenna")(type "KiCad")(uri "${KIPRJMOD}/Phoenix_Antenna.pretty")(options "")(descr "Candidate"))' + ''.join('(lib (name "'+n+'")(type "KiCad")(uri "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/'+n+'.pretty")(options "")(descr "KiCad standard"))' for n in ['Resistor_SMD','Capacitor_SMD','Inductor_SMD']) + ')\n')
