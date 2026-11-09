#!/usr/bin/env python3
"""DC screening of the saved VBUS backbone; not a trace current rating or thermal model."""
from pathlib import Path
import hashlib,json
import pcbnew as p
R=Path(__file__).resolve().parents[1]/'migration-rk3562';V=R/'review';path=R/'kicad/pcb/phoenix-g1.kicad_pcb'
sha=hashlib.sha256(path.read_bytes()).hexdigest()
check=json.loads((V/'pcb-connectivity-check.json').read_text())
returns=json.loads((V/'usb-return-audit.json').read_text())
assert check['pcb_sha256']==returns['pcb_sha256']==sha,'Stale physical verification'
assert not check['geometric_drc_violations'] and returns['usb_vbus_source_to_guard']['connected'] and returns['usb_guard_to_main']['connected'],'Unverified backbone'
b=p.LoadBoard(str(path))
# Sum each wide backbone's branches in series as a deliberately conservative
# screen of selected copper only. This is not a bound on complete path resistance.
rho20=1.724e-8;alpha=.00393;current=3.0;backbones=[]
for name in ['VBUS_RAW','VBUS_PROTECTED']:
 tracks=[t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname()==name and t.GetLayer()==p.In2_Cu and p.ToMM(t.GetWidth())>=1.5]
 assert tracks,'No wide backbone found: '+name
 length=sum(p.ToMM(t.GetLength()) for t in tracks);cases=[]
 for thickness_um in [17.5,35.0]:
  for copper_temperature_c in [20,60]:
   rho=rho20*(1+alpha*(copper_temperature_c-20))
   resistance=sum(rho*(p.ToMM(t.GetLength())/1000)/((p.ToMM(t.GetWidth())/1000)*(thickness_um/1e6)) for t in tracks)
   cases.append({'nominal_copper_um':thickness_um,'imposed_copper_temperature_c':copper_temperature_c,'wide_segments_series_resistance_ohm':round(resistance,6),'drop_v_at_3a':round(current*resistance,5),'loss_w_at_3a':round(current**2*resistance,5)})
 backbones.append({'net':name,'segment_count':len(tracks),'summed_wide_trace_length_mm':round(length,4),'cases':cases})
report={'status':'ANALYTICAL DC SCREEN ONLY; NOT CURRENT OR THERMAL QUALIFICATION','pcb_sha256':sha,'backbones':backbones,'stress_current_a':current,'assumed_copper_resistivity_at_20c_ohm_m':rho20,'assumed_temperature_coefficient_per_c':alpha,'nominal_copper_source':'https://jlcpcb.com/help/article/jlcpcb-copper-weight','limitations':['All wide branches are conservatively summed in series; this is not a solved resistor network.','Copper thicknesses are nominal options, not measured finished thicknesses or guaranteed minimums.','Temperatures are imposed calculation inputs, not predicted temperature rise.','Outer-layer necks, sense feeds, vias, contacts, protection IC resistance and current sharing are excluded.','No IPC-2152 qualification, coupled thermal simulation, prototype measurement or passive-cooling validation.'],'production_ready':False}
(V/'usb-power-dc-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
