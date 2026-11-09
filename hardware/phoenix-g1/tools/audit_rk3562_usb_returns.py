#!/usr/bin/env python3
"""Physical screening of USB bypass placement and ground returns; not PI signoff."""
from pathlib import Path
import json,math,hashlib,sys
import pcbnew as p
R=Path(__file__).resolve().parents[1]/'migration-rk3562'
path=R/'kicad/pcb/phoenix-g1.kicad_pcb';b=p.LoadBoard(str(path));b.BuildConnectivity();c=b.GetConnectivity()
fps={f.GetReference():f for f in b.GetFootprints()}
def xy(a):return (p.ToMM(a.GetPosition().x),p.ToMM(a.GetPosition().y))
def connected_pads(start):
 todo=[start];seen=set();found=set()
 while todo:
  a=todo.pop();key=a.m_Uuid.AsString()
  if key in seen:continue
  seen.add(key)
  if isinstance(a,p.PAD):found.add(a.GetParentFootprint().GetReference()+'.'+a.GetNumber())
  todo.extend(c.GetConnectedPads(a));todo.extend(c.GetConnectedTracks(a))
 return found
caps=[]
for ref,target in [('C605','U6'),('C1103','U12'),('C1104','U13'),('C1105','U14'),('C1106','U16'),('C1107','U19'),('C606','U6'),('C1101','U11'),('C1102','U11'),('C1201','U15'),('C1203','U15'),('C1901','U24'),('C1902','U24')]:
 for pad in fps[ref].Pads():
  if pad.GetNetname()=='GND':continue
  loads=[a for a in fps[target].Pads() if a.GetNetname()==pad.GetNetname()]
  caps.append({'capacitor':ref,'target':target,'rail':pad.GetNetname(),'minimum_pad_distance_mm':round(min(math.dist(xy(pad),xy(a)) for a in loads),3),'same_copper_layer':any(pad.IsOnLayer(layer) and a.IsOnLayer(layer) for a in loads for layer in [p.F_Cu,p.B_Cu]),'physically_connected_to_target':any(target+'.'+a.GetNumber() in connected_pads(pad) for a in loads),'target_pins':[a.GetNumber() for a in loads],'all_target_pins_connected':all(target+'.'+a.GetNumber() in connected_pads(pad) for a in loads)})
  caps[-1]['direct_cap_to_ic_tracks']=[{'length_mm':round(p.ToMM(t.GetLength()),4),'width_mm':p.ToMM(t.GetWidth()),'layer':t.GetLayerName()} for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetCode()==pad.GetNetCode() and any((t.GetStart()==pad.GetPosition() and t.GetEnd()==a.GetPosition()) or (t.GetEnd()==pad.GetPosition() and t.GetStart()==a.GetPosition()) for a in loads)]
power_chain=[]
for name in ['VBUS_RAW','VBUS_PROTECTED']:
 endpoints=sorted([a for f in fps.values() for a in f.Pads() if a.GetNetname()==name],key=lambda a:(a.GetParentFootprint().GetReference(),a.GetNumber()))
 reached={i.GetParentFootprint().GetReference()+'.'+i.GetNumber() for i in c.GetConnectedItems(endpoints[0]) if isinstance(i,p.PAD)}
 labels=sorted(a.GetParentFootprint().GetReference()+'.'+a.GetNumber() for a in endpoints)
 missing=sorted(set(labels)-reached)
 power_chain.append({'net':name,'endpoints':labels,'unreachable_from_first_endpoint':missing,'connected':not missing})
source_pads=sorted([a for ref in ['J1','U24','C1901'] for a in fps[ref].Pads() if a.GetNetname()=='VBUS_RAW'],key=lambda a:(a.GetParentFootprint().GetReference(),a.GetNumber()))
source_cluster={i.GetParentFootprint().GetReference()+'.'+i.GetNumber() for i in c.GetConnectedItems(source_pads[0]) if isinstance(i,p.PAD)}
source_labels=[a.GetParentFootprint().GetReference()+'.'+a.GetNumber() for a in source_pads]
source_to_guard={'endpoints':source_labels,'unreachable_from_first_endpoint':sorted(set(source_labels)-source_cluster),'connected':all(a in source_cluster for a in source_labels)}
guard_pads=sorted([a for ref in ['U24','U15','C1902','C1201'] for a in fps[ref].Pads() if a.GetNetname()=='VBUS_PROTECTED'],key=lambda a:(a.GetParentFootprint().GetReference(),a.GetNumber()))
guard_cluster={i.GetParentFootprint().GetReference()+'.'+i.GetNumber() for i in c.GetConnectedItems(guard_pads[0]) if isinstance(i,p.PAD)}
guard_labels=[a.GetParentFootprint().GetReference()+'.'+a.GetNumber() for a in guard_pads]
guard_to_main={'endpoints':guard_labels,'unreachable_from_first_endpoint':sorted(set(guard_labels)-guard_cluster),'connected':all(a in guard_cluster for a in guard_labels)}
aon_pads=sorted([a for f in fps.values() for a in f.Pads() if a.GetNetname()=='+3V3_AON'],key=lambda a:(a.GetParentFootprint().GetReference(),a.GetNumber()))
aon_start=next(a for a in aon_pads if a.GetParentFootprint().GetReference()=='U11')
aon_cluster={i.GetParentFootprint().GetReference()+'.'+i.GetNumber() for i in c.GetConnectedItems(aon_start) if isinstance(i,p.PAD)}
aon_labels=[a.GetParentFootprint().GetReference()+'.'+a.GetNumber() for a in aon_pads]
aon_supply={'endpoints':aon_labels,'unreachable_from_regulator':sorted(set(aon_labels)-aon_cluster),'connected':all(a in aon_cluster for a in aon_labels)}
returns=[]
for ref in ['J1','U6','U7','U8','R1102','R1103','U9','U11','U12','U13','U14','U15','U19','U24','C1103','C1104','C1105','C1106','C1107','C606','U16','C605','C1101','C1102','C1201','C1202','C1203','C1901','C1902','C1903','R1201','R1902','R1904','R1905']:
 for a in fps[ref].Pads():
  if a.GetNetname()=='GND':
   reached=connected_pads(a)
   cluster={i.GetParentFootprint().GetReference()+'.'+i.GetNumber() for i in c.GetConnectedItems(a) if isinstance(i,p.PAD)}
   source=sorted(cluster & {'J1.A1','J1.A12','J1.B1','J1.B12'})
   returns.append({'pin':ref+'.'+a.GetNumber(),'connected_ground_pads':sorted(reached),'has_copper_escape':bool(c.GetConnectedTracks(a)), 'usb_source_ground_pads_in_copper_cluster':source, 'connected_to_usb_source_ground':len(source)==4})
expected_ground=set()
for sheet in ['usb-c-frontend','usb-power-control','usb-input-protection','usb-vbus-guard']:
 expected_ground.update(a['ref']+'.'+a['pin'] for a in json.loads((R/('review/'+sheet+'-expected.json')).read_text()) if a['net']=='GND')
assert expected_ground <= {a['pin'] for a in returns}, 'USB ground audit coverage incomplete'
report={'status':'USB POWER/RETURN LAYOUT INCOMPLETE','pcb_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bypass_placement':caps,'usb_input_power_chain':power_chain,'usb_vbus_source_to_guard':source_to_guard,'usb_guard_to_main':guard_to_main,'usb_aon_supply':aon_supply,'ground_returns':returns,'expected_ground_dispositions':sorted(expected_ground),'ground_zones':sum(z.GetNetname()=='GND' for z in b.Zones()),'limitations':['Pad distances are geometric screening, not loop length or inductance.','Source-ground connectivity uses KiCad GetConnectedItems including filled-zone connectivity; this is geometric continuity, not impedance or current-capacity qualification. Supply copper is still required before any circuit functionality claim.','No PI, ESD, thermal or physical validation has been performed.'],'production_ready':False}
(R/'review/usb-return-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'bypass_placement':caps,'usb_vbus_source_to_guard':source_to_guard,'ground_pads_checked':len(returns),'ground_pads_with_escape':sum(a['has_copper_escape'] for a in returns),'ground_zones':report['ground_zones'],'pads_connected_to_usb_source':sum(a['connected_to_usb_source_ground'] for a in returns)},indent=2))

if '--require-ground' in sys.argv:
 assert all(a['has_copper_escape'] and a['connected_to_usb_source_ground'] for a in returns), 'USB ground continuity regression; reject this layout'

if '--require-source' in sys.argv:
 assert source_to_guard['connected'], 'USB source-to-guard power continuity regression; reject this layout'

if '--require-raw' in sys.argv:
 assert next(a for a in power_chain if a['net']=='VBUS_RAW')['connected'], 'VBUS_RAW feed continuity regression'
if '--require-guard' in sys.argv:
 assert guard_to_main['connected'], 'USB guard-to-main power continuity regression'

if '--require-input' in sys.argv:
 assert all(a['connected'] for a in power_chain), 'USB input power continuity regression'
if '--require-bypass' in sys.argv:
 assert all(a['all_target_pins_connected'] for a in caps), 'USB bypass continuity regression'

if '--require-aon' in sys.argv:
 assert aon_supply['connected'], 'Auxiliary 3.3 V supply continuity regression'
