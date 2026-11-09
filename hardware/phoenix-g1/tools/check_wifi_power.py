#!/usr/bin/env python3
"""Netlist-derived static screen of dedicated Wi-Fi VBAT; not a transient model."""
import json,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
x=ET.parse(ROOT/'review/integrated.xml');nets={}
for n in x.findall('.//nets/net'):
 for p in n.findall('node'):nets[p.get('ref'),p.get('pin')]=n.get('name')
for ref,pin,net in [('FB2001','1','+3V58_WIFI'),('FB2001','2','WIFI_VBAT'),('U25','9','WIFI_VBAT'),('U26','5','WIFI_VBAT_FB'),('U26','14','+3V58_WIFI'),('U26','4','WIFI_VBAT_PG'),('U17','13','WIFI_VBAT_PG'),('R2201','2','+3V58_WIFI'),('R2202','1','+3V58_WIFI'),('R2202','2','WIFI_VBAT_FB'),('R2203','1','WIFI_VBAT_FB'),('R2203','2','GND')]:assert nets[ref,pin]==net,(ref,pin)
comps={c.get('ref'):c for c in x.findall('.//components/comp')}
def kohm(ref):return float(comps[ref].findtext('value').split()[0].replace('k',''))*1000
rt,rb=kohm('R2202'),kohm('R2203');tol=.01;tcr=100e-6;delta_t=100;effective_tol=(1+tol)*(1+tcr*delta_t)-1;nom=.8*(1+rt/rb);cases=[]
for mode,low,high in [('PWM full temperature',.7856,.8144),('PFM accuracy bound',.7816,.8224)]:
 # Independent resistor extrema; FB leakage worst sign adds/subtracts I*Rtop.
 lo=low*(1+rt*(1-effective_tol)/(rb*(1+effective_tol)))-100e-9*rt*(1+effective_tol)
 hi=high*(1+rt*(1+effective_tol)/(rb*(1-effective_tol)))+100e-9*rt*(1+effective_tol)
 cases.append({'mode':mode,'regulator_lower_bound_v':round(lo,6),'regulator_upper_bound_v':round(hi,6),'screen_vbat_after_20mohm_at_1a_v':round(lo-.02,6),'margin_above_3v2_v':round(lo-.02-3.2,6),'margin_below_4v8_v':round(4.8-hi,6)})
r={'status':'HOLD: dedicated rail improves static margin; layout, input headroom and transients unqualified','sources':['reference/tps62130.pdf sections7.5,8.3.3,9.2; same TPS62130 family pinout as fixed variant','reference/wifi-ap6256.pdf section2.2.3','sourcing/public/C43590.json'],'nominal_output_v':nom,'resistor_tolerance_assumed':tol,'resistor_tcr_abs_ppm_k':100,'temperature_screen_delta_from_25c_k':delta_t,'combined_conservative_resistor_bound':effective_tol,'fb_leakage_abs_max_a':100e-9,'module_peak_basis':'Datasheet gives1A at3.3V. Reusing1A at3.584V is a design screen, not a guaranteed operating current at the new voltage.','cases':cases,'startup':'U26 PG pulled to its own output enables system U17; nominal PG threshold92-98% of setpoint. PG is high impedance in shutdown/UVLO/thermal fault, so retained charge and fault sequencing remain open.','remaining_holds':['PWM accuracy condition VIN>=VOUT+1V may not hold at low USB input after two eFuses. Characterize dropout/headroom; no guaranteed USB compatibility claimed.','Feedback resistor initial tolerance and independent 100ppm/K drift over100K included. Aging, line/load regulation, hot ferrite DCR, PCB IR drop and ripple excluded; this is not a product operating-temperature rating.','PFM bound is not a guaranteed1A operating point; transition/load-step behavior must be measured.','L2201 saturation rating vs fault current, effective MLCC capacitance and ferrite/dual-cap resonance need qualification.','AP6256 requires VBAT before/coincident with VDDIO; verify cold start, rapid cycling, thermal shutdown and power removal.','Full simultaneous USB load and expansion power allocation remain open.']}
(ROOT/'review/wifi-power-check.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'status':r['status'],'nominal_output_v':nom,'cases':cases},indent=2))
