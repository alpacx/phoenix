#!/usr/bin/env python3
"""Replace J3 in a separate PCB, preserve old copper, add unrouted power branch."""
import pcbnew as p,json,hashlib,shutil,xml.etree.ElementTree as ET
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R/'migration-rk3562/experiments/lpddr4-1gb';O=R/'migration-rk3562/experiments/stacked-expansion';D=O/'pcb';D.mkdir(exist_ok=True)
cp=json.loads((B/'working-board.json').read_text());src=B/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();conn=b.GetConnectivity();fps={f.GetReference():f for f in b.GetFootprints()};old=fps['J3'];assert not any(conn.GetConnectedTracks(a) for a in old.Pads())
components={c.get('ref'):c for c in ET.parse(O/'system/review/netlist.xml').getroot().findall('./components/comp')}
def schpath(ref):
 c=components[ref];return p.KIID_PATH(c.find('sheetpath').get('tstamps')+c.findtext('tstamps'))
pinout=json.loads((O/'pinout.json').read_text())['pins'];nets=b.GetNetsByName()
def net(name):
 if name not in nets:
  n=p.NETINFO_ITEM(b,name);b.Add(n);nets[name]=n
 return nets[name]
new=p.FootprintLoad(str(O/'system/kicad/Phoenix_Stacked.pretty'),'DF40C_40DP_0.4V');assert new is not None
new.SetReference('J3');new.SetValue('DF40C-40DP-0.4V(51)');new.SetFPID(p.LIB_ID('Phoenix_Stacked','DF40C_40DP_0.4V'));new.SetPath(schpath('J3'));new.SetPosition(p.VECTOR2I(p.FromMM(67.5),p.FromMM(2.5)))
for pad in new.Pads():
 name=pinout.get(pad.GetNumber())
 if name:pad.SetNet(net(name))
b.Remove(old);b.Add(new)
for ball,name in [('AE26','ADDON_USB_DM'),('AE27','ADDON_USB_DP')]:
 pad=next(a for a in fps['U1'].Pads() if a.GetNumber()==ball);assert not conn.GetConnectedTracks(pad);pad.SetNet(net(name))
moved=[]
for ref in ['C423','C431','C435']:
 f=fps[ref];assert not any(conn.GetConnectedTracks(a) for a in f.Pads());f.Flip(f.GetPosition(),False);moved.append({'ref':ref,'change':'same XY, F.Cu to B.Cu','power_integrity_qualified':False})
contracts=json.loads((O/'system/review/expansion-power-expected.json').read_text());groups={}
for r in contracts:groups.setdefault(r['ref'],{})[r['pin']]=r['net']
positions={'U8101':(77,6),'R8101':(74.5,6),'R8102':(74.5,8),'R8103':(74.8,3.5),'C8101':(77,3.7),'C8102':(79.5,6),'C8103':(77,8.3)}
for ref,mapping in groups.items():
 if ref=='U8101':template=fps['U15']
 else:
  ending='R_0402_1005Metric' if ref.startswith('R') else 'C_0402_1005Metric'
  template=next(f for f in b.GetFootprints() if str(f.GetFPID().GetLibItemName())==ending)
 f=p.FOOTPRINT(template)
 f.SetUuid(p.KIID())
 for item in list(f.Pads())+list(f.GraphicalItems())+list(f.GetFields()):item.SetUuid(p.KIID())
 f.SetPath(schpath(ref))
 f.SetReference(ref);f.SetValue({'U8101':'TPS259531DSGR','R8101':'2.1k candidate','R8102':'100k','R8103':'100k','C8103':'22n'}.get(ref,'1u'))
 if f.IsFlipped():f.Flip(f.GetPosition(),False)
 f.SetOrientationDegrees(0);x,y=positions[ref];f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));f.Flip(f.GetPosition(),False)
 for a in f.Pads():
  assert a.GetNumber() in mapping,(ref,a.GetNumber());a.SetNet(net(mapping[a.GetNumber()]))
 b.Add(f)
# Preserve ALL tracks and vias; zone refill reflects changed pad obstacles.
p.ZONE_FILLER(b).Fill(b.Zones());dest=D/'candidate.kicad_pcb';p.SaveBoard(str(dest),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),dest.with_suffix('.'+ext))

with dest.with_suffix('.kicad_dru').open('a') as out:out.write('\n(rule "DF40 internal pad pitch" (condition "A.Type == \'Pad\' && B.Type == \'Pad\' && A.memberOfFootprint(\'J3\') && B.memberOfFootprint(\'J3\')") (constraint clearance (min 0.17mm)))\n')
# Resolve local footprint libraries from the PCB directory.
table=(O/'system/kicad/fp-lib-table').read_text().replace('${KIPRJMOD}/','${KIPRJMOD}/../system/kicad/')
(D/'fp-lib-table').write_text(table)
report={'status':'PLACEMENT_CANDIDATE_NOT_ROUTED','source_sha256':cp['sha256'],'board_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'new_J3_center_mm':[67.5,2.5],'replaced_J3':True,'extra_expansion_connectors':0,'moved_unrouted_caps':moved,'new_power_parts':list(groups),'host_pins':['AE26','AE27'],'outline_mm':[90,40],'target_mm':[85,35],'power_branch_routed':False,'assembly_ready':False}
(D/'placement.json').write_text(json.dumps(report,indent=2)+'\n');assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];print(json.dumps(report))
