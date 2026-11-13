#!/usr/bin/env python3
"""Continuity/preservation audit, not electrical or thermal qualification."""
import pcbnew as p,json,collections,hashlib,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'migration-rk3562/experiments/stacked-expansion/pcb';stage=sys.argv[1] if len(sys.argv)>1 else 'local-power';a=p.LoadBoard(str(D/'candidate.kicad_pcb'));b=p.LoadBoard(str(D/(stage+'.kicad_pcb')));b.BuildConnectivity()
def tracks(board):
 return {t.m_Uuid.AsString():(t.GetNetname(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth()) for t in board.GetTracks()}
x,y=tracks(a),tracks(b);assert all(y.get(k)==v for k,v in x.items());pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def connected(s,t):return pads[t].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[s])}
original_pads={(f.GetReference(),q.GetNumber()):q.GetNetname() for f in a.GetFootprints() for q in f.Pads()}
assert all(pads[k].GetNetname()==net for k,net in original_pads.items()),'Pad net changed'
reserve_names={z.GetZoneName() for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.GetDoNotAllowVias() and z.GetDoNotAllowZoneFills()}
expected_reserves={f'H{n} mechanical reservation' for n in range(8101,8106)}
if stage=='logic-reference' or stage.startswith('aux-io'):assert expected_reserves<=reserve_names,'Missing mechanical routing reservations'
checks=[]
for pin,ref in [('7','R8101'),('1','C8103'),('2','R8103'),('6','R8102'),('3','C8101'),('4','C8101'),('5','C8102')]:
 assert connected(('U8101',pin),(ref,'1'));checks.append(['U8101.'+pin,ref+'.1'])
ground=[k for k,v in pads.items() if k[0].startswith(('U810','C810','R810')) and v.GetNetname()=='GND']
for k in ground:
 if k!=('U8101','9'):assert connected(('U8101','9'),k),('ground disconnected',k)
main=('U4','69');assert connected(('U8101','9'),main),'Local ground not joined to existing PMIC ground'
counts=lambda d:collections.Counter(v['type'] for v in d['violations']);d=json.loads((D/(stage+'-drc.json')).read_text());assert counts(d)==counts(json.loads((D/'drc.json').read_text()))
aux_connections={}
if stage.startswith('aux-io'):
 for n in [25,26,29,30,23,24,31,32,33,34,35]:
  net=pads['J3',str(n)].GetNetname();src=next(k for k,v in pads.items() if k[0]=='U1' and v.GetNetname()==net);aux_connections[net]=connected(src,('J3',str(n)))
report={'auxiliary_signal_continuity':aux_connections,'status':'LOCAL_BLOCK_CONTINUITY_AND_GEOMETRY_CHECKED','sha256':hashlib.sha256((D/(stage+'.kicad_pcb')).read_bytes()).hexdigest(),'verified_connections':checks,'ground_reference':'U4.69 exposed pad','other_PMIC_ground_pins_remain_unrouted':True,'ground_pads_verified':len(ground),'connected_to_existing_PMIC_ground':True,'mechanical_copper_reservations_enforced':sorted(expected_reserves & reserve_names),'original_pad_nets_preserved':True,'original_tracks_vias_preserved':len(x),'new_tracks_vias':len(y)-len(x),'drc_categories':dict(counts(d)),'input_feed_connected':connected(('U8101','3'),('U26','13')),'output_J3_connected':all(connected(('U8101','5'),('J3',str(n))) for n in range(1,9)),'GPIO_to_SoC_connected':connected(('U1','K2'),('U8101','2')) and connected(('U1','L3'),('U8101','6')),'fault_pullup_supply_connected':connected(('R8102','2'),('U4','55')),'J3_ground_connected':all(connected(('U4','69'),('J3',str(n))) for n in [*range(9,19),20,22,37,38]),'J3_logic_reference_connected':connected(('U4','55'),('J3','36')),'USB_routed':False,'current_and_thermal_qualified':False,'assembly_ready':False}
(D/(stage+'-audit.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
