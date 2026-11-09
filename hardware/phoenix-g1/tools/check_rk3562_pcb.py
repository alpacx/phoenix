#!/usr/bin/env python3
"""Read actual PCB for net correspondence and DRC; does not imply release."""
from pathlib import Path
import pcbnew as p,json,xml.etree.ElementTree as ET,hashlib
R=Path(__file__).resolve().parents[1]/'migration-rk3562';path=R/'kicad/pcb/phoenix-g1.kicad_pcb';b=p.LoadBoard(str(path))
x=ET.parse(R/'review/integrated.xml');expected={}
for n in x.findall('.//nets/net'):
 for a in n.findall('node'):expected[a.get('ref'),a.get('pin')]=n.get('name')
seen=set();differences=[];count=0
for f in b.GetFootprints():
 for a in f.Pads():
  key=(f.GetReference(),a.GetNumber());seen.add(key)
  if key not in expected:
   if a.GetNetname():differences.append({'pad':key,'unexpected_net':a.GetNetname()})
  elif a.GetNetname()!=expected[key]:differences.append({'pad':key,'expected':expected[key],'actual':a.GetNetname()})
  else:count+=1
missing=[{'ref':r,'pin':n} for r,n in expected if (r,n) not in seen]
drc=json.loads((R/'review/pcb-drc.json').read_text())
b.BuildConnectivity();b.GetConnectivity().RecalculateRatsnest()
# Traverse KiCad's physical copper connectivity, not just route-generator claims.
usb_names=['USB_CC1','USB_CC2','CC_VBUS_SENSE','CC_VBUS_SERIES_1','CC_VBUS_SERIES_2','AON_READY','USB_CC_ENABLE_N','CC_OUT1_N','CC_OUT2_N','USB_CURRENT_OK','USB_MAIN_ENABLE']
usb_names += ['USB_DVDT','USB_ILIM','USB_POWER_FAULT_N','VBUS_GUARD_DVDT','VBUS_GUARD_ILIM','VBUS_OVP','VBUS_UVLO']
continuity=[]
conn=b.GetConnectivity()
for name in usb_names:
 terminals=[a for f in b.GetFootprints() for a in f.Pads() if a.GetNetname()==name]
 queue=terminals[:1];visited=set()
 while queue:
  item=queue.pop();uid=item.m_Uuid.AsString()
  if uid in visited:continue
  visited.add(uid)
  queue.extend(conn.GetConnectedPads(item));queue.extend(conn.GetConnectedTracks(item))
 disconnected=[a.GetParentFootprint().GetReference()+'.'+a.GetNumber() for a in terminals if a.m_Uuid.AsString() not in visited]
 continuity.append({'net':name,'terminal_count':len(terminals),'connected':bool(terminals) and not disconnected,'unreachable_from_first_pad':disconnected})
report={'status':'PARTIAL PCB CHECK; NOT MANUFACTURING APPROVAL','pcb_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'matched_pads':count,'usb_copper_continuity':continuity,'net_mismatches':differences,'missing_physical_pads':missing,'geometric_drc_violations':drc['violations'],'unconnected_ratsnest_edges':b.GetConnectivity().GetUnconnectedCount(False),'ground_zones':sum(z.GetNetname()=='GND' for z in b.Zones()),'tracks':sum(not isinstance(t,p.PCB_VIA) for t in b.GetTracks()),'vias':sum(isinstance(t,p.PCB_VIA) for t in b.GetTracks()),'production_ready':False}
(R/'review/pcb-connectivity-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='missing_physical_pads'},indent=2));print('Missing pads:',len(missing))
assert not differences
assert all(a['connected'] for a in continuity), 'USB control copper continuity incomplete'
assert not drc['violations']
assert {a['ref'] for a in missing}<={'DS1'},'Unexpected missing physical component'

# Keep the published physical summary tied to the board actually checked.
status_path=R/'review/completion-status.json'
status=json.loads(status_path.read_text())
failed=[]
for filename in ['usb-sense-routing.json','usb-control-routing.json','usb-auxiliary-routing.json']:
 routing=json.loads((R/'review'/filename).read_text())
 failed.extend(routing.get('failed_branches',[]))
status['physical_draft']={'board':'kicad/pcb/phoenix-g1.kicad_pcb','pcb_sha256':report['pcb_sha256'],'footprints':len(list(b.GetFootprints())),'tracks':report['tracks'],'vias':report['vias'],'ground_zones':report['ground_zones'],'unconnected_ratsnest_edges':report['unconnected_ratsnest_edges'],'geometric_drc_violations':len(drc['violations']),'missing_display_footprint':bool(missing),'unrouted_usb_control_branches':failed,'production_ready':False}
status_path.write_text(json.dumps(status,indent=2)+'\n')
