#!/usr/bin/env python3
"""Validate complete VBUS sense chain, including initial tolerance and TCR."""
from pathlib import Path
import json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
x=ET.parse(ROOT/'review/integrated.xml');comps={c.get('ref'):c for c in x.findall('.//components/comp')};pins={}
for n in x.findall('.//nets/net'):
 for v in n.findall('node'):pins[v.get('ref'),v.get('pin')]=n.get('name')
expected=[('R601','VBUS_PROTECTED','CC_VBUS_SERIES_1'),('R605','CC_VBUS_SERIES_1','CC_VBUS_SERIES_2'),('R606','CC_VBUS_SERIES_2','CC_VBUS_SENSE')]
for ref,a,b in expected:
 assert pins[ref,'1']==a and pins[ref,'2']==b
 assert comps[ref].findtext('value')=='300k 0.1% 25ppm'
assert pins['U6','5']=='CC_VBUS_SENSE'
nom=900000;initial=.001;drift=25e-6*100
lo=nom*(1-initial)*(1-drift);hi=nom*(1+initial)*(1+drift)
assert lo>=880000 and hi<=910000,(lo,hi)
r={'status':'PASS TOPOLOGY AND RESISTANCE SCREEN ONLY','source':'reference/hd3ss3220.pdf recommended external R(VBUS)880..910kohm','series_references':[v[0] for v in expected],'nominal_ohm':nom,'initial_tolerance_fraction':initial,'tcr_ppm_per_k':25,'temperature_interval_c':[-40,125],'max_delta_from_25c_k':100,'computed_resistance_bounds_ohm':[lo,hi],'permitted_resistance_bounds_ohm':[880000,910000],'limits':['Temperature range screens resistors, not system operating range.','Board contamination/leakage, solder shifts, lifetime drift and transients excluded.','No protection against arbitrary high voltage is implied by the sense-resistor network.']}
(ROOT/'review/usb-sense-resistance.json').write_text(json.dumps(r,indent=2)+'\n');print(r['status'],r['computed_resistance_bounds_ohm'])
