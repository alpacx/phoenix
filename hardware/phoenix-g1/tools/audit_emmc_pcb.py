#!/usr/bin/env python3
"""Independent eMMC PCB/netlist and copper preservation audit; no SI/PI claim."""
import pcbnew as p,json,hashlib,sys,xml.etree.ElementTree as ET
from pathlib import Path
from drc_regression import introduced
from pcb_preservation import verify_preservation
R=Path(__file__).resolve().parents[1];E=R/'migration-rk3562/experiments';D=E/'emmc-system/pcb';stage=sys.argv[1] if len(sys.argv)>1 else 'emmc-repacked';m=json.loads((D/'migration.json').read_text());src=R/m['source_board'];path=D/(stage+'.kicad_pcb')
assert hashlib.sha256(src.read_bytes()).hexdigest()==m['source_sha256']
a=p.LoadBoard(str(src));b=p.LoadBoard(str(path));af={f.GetReference():f for f in a.GetFootprints()};bf={f.GetReference():f for f in b.GetFootprints()}
removed=set(m['removed']);added=set(m['new_backside_positions_mm']);assert set(bf)==set(af)-removed|added
changes={('U1',c['ball']):c['to'] for c in m['changed_soc_pins']};checked=0
for ref,f in af.items():
 if ref in removed:continue
 for pad in f.Pads():
  other=next(q for q in bf[ref].Pads() if q.GetNumber()==pad.GetNumber());assert other.GetNetname()==changes.get((ref,pad.GetNumber()),pad.GetNetname()),(ref,pad.GetNumber());checked+=1
preservation=verify_preservation(a,b,removed,changes);groups_checked=preservation['existing_connected_pad_groups_preserved']
b.BuildConnectivity()
if stage.startswith('emmc-ground'):
 pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
 for key in [(f'C{n}','2') for n in range(8001,8011)]+[('R8005','2')]:
  assert pads['U4','69'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[key])},('Storage ground not connected',key)
reserve_names={z.GetZoneName() for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.GetDoNotAllowVias() and z.GetDoNotAllowZoneFills()};expected_reserves={f'H{n} mechanical reservation' for n in range(8101,8106)};assert expected_reserves<=reserve_names
netlist=E/'emmc-system/system/review/integrated.xml';assert hashlib.sha256(netlist.read_bytes()).hexdigest()==m['schematic_netlist_sha256'];nets={}
for net in ET.parse(netlist).findall('.//nets/net'):
 for node in net.findall('node'):nets[node.attrib['ref'],node.attrib['pin']]=net.attrib['name']
newpins=0
for ref in added:
 for pad in bf[ref].Pads():
  expected=nets.get((ref,pad.GetNumber()),'');expected='' if expected.startswith('unconnected-') else expected
  assert pad.GetNetname()==expected,(ref,pad.GetNumber(),pad.GetNetname(),expected);newpins+=1
assert len(list(bf['U8001'].Pads()))==153

def tracks(board):
 return {t.m_Uuid.AsString():(t.GetNetname(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,p.PCB_VIA) else None) for t in board.GetTracks()}
old_tracks,new_tracks=tracks(a),tracks(b)
assert all(new_tracks.get(k)==v for k,v in old_tracks.items()),'Existing copper changed'
baseline=json.loads((src.with_name(src.stem+'-drc.json')).read_text());drc=json.loads((D/(stage+'-drc.json')).read_text());new= introduced(baseline,drc)
report={'status':'PCB_NETLIST_MATCHED_PLACEMENT_DRC_OPEN' if new else 'PCB_NETLIST_AND_PLACEMENT_GEOMETRY_CHECKED_ROUTING_OPEN','board_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'existing_pad_assignments_checked':checked,'new_pad_assignments_checked':newpins,'existing_tracks_vias_preserved':len(tracks(a)),'added_tracks_vias':len(tracks(b))-len(tracks(a)),'existing_connected_pad_groups_preserved':groups_checked,'mechanical_reservations_preserved':sorted(expected_reserves),'removed_NOR_references':sorted(removed),'added_storage_references':sorted(added),'new_individual_drc_violations':new,'placement_geometry_passed':not new,'decoupling_and_power_qualified':False,'routing_complete':False,'boot_tested':False,'assembly_ready':False}
(D/(stage+'-audit.json')).write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='new_individual_drc_violations'});print('New DRC violations:',len(new))
