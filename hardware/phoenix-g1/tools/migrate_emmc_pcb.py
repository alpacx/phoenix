#!/usr/bin/env python3
"""Isolated eMMC PCB migration; preliminary placement, no timing/boot qualification."""
import hashlib,json,shutil,xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew as p
R=Path(__file__).resolve().parents[1];E=R/'migration-rk3562/experiments';S=E/'stacked-expansion';D=E/'emmc-system/pcb';D.mkdir(exist_ok=True)
cp=json.loads((S/'working-candidate.json').read_text());src=S/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();footprints={f.GetReference():f for f in b.GetFootprints()};retained=[]
changes=json.loads((D.parent/'integration.json').read_text());tree=ET.parse(D.parent/'system/review/integrated.xml');nets={}
for net in tree.findall('.//nets/net'):
 for node in net.findall('node'):nets[node.attrib['ref'],node.attrib['pin']]=net.attrib['name']
for ref in changes['removed_boot_flash_references']:
 f=footprints[ref];assert not any(b.GetConnectivity().GetConnectedTracks(a) for a in f.Pads()),ref
 b.Remove(f);retained.append(f)
def assign(pad,name):
 if not name or name.startswith('unconnected-'):pad.SetNetCode(0);return
 net=b.FindNet(name)
 if net is None:net=p.NETINFO_ITEM(b,name);b.Add(net);retained.append(net)
 pad.SetNet(net)
pads={a.GetNumber():a for a in footprints['U1'].Pads()}
for change in changes['soc_pin_changes']:
 a=pads[change['ball']];assert a.GetNetname()==(change['from'] or '')
 assert not b.GetConnectivity().GetConnectedTracks(a)
 assert nets['U1',change['ball']]==change['to'];assign(a,change['to'])
positions={'U8001':(20,14),'C8001':(13,9),'C8002':(13,11),'C8003':(13,13),'C8004':(13,15),'C8005':(13,17),'C8006':(13,19),'C8007':(27,11),'C8008':(27,13),'C8009':(27,15),'C8010':(49,10),'R8001':(17,22),'R8002':(19,22),'R8003':(21,22),'R8004':(23,22),'R8005':(25,22),'R8006':(29,22),'R8007':(29,24)}
for comp in tree.findall('.//components/comp'):
 ref=comp.attrib['ref']
 if ref not in positions:continue
 lib,name=comp.findtext('footprint').split(':');f=p.FootprintLoad(str(D.parent/'system/kicad'/f'{lib}.pretty'),name);assert f,ref
 f.SetReference(ref);f.SetValue(comp.findtext('value'));f.SetFPID(p.LIB_ID(lib,name));b.Add(f);retained.append(f)
 f.SetPosition(p.VECTOR2I(*(p.FromMM(n) for n in positions[ref])));f.Flip(f.GetPosition(),False);f.Reference().SetVisible(False);f.Value().SetVisible(False)
 for a in f.Pads():assign(a,nets.get((ref,a.GetNumber())))
p.ZONE_FILLER(b).Fill(b.Zones());out=D/'emmc-placement.kicad_pcb';p.SaveBoard(str(out),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
(D/'fp-lib-table').write_text((D.parent/'system/kicad/fp-lib-table').read_text().replace('${KIPRJMOD}/','${KIPRJMOD}/../system/kicad/'))
(D/'migration.json').write_text(json.dumps({'status':'ISOLATED_EMMC_PCB_PRELIMINARY_PLACEMENT','source_board':str(src.relative_to(R)),'source_sha256':cp['sha256'],'schematic_netlist_sha256':hashlib.sha256((D.parent/'system/review/integrated.xml').read_bytes()).hexdigest(),'board_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'removed':changes['removed_boot_flash_references'],'changed_soc_pins':changes['soc_pin_changes'],'new_backside_positions_mm':positions,'routing_complete':False,'decoupling_placement_qualified':False,'assembly_ready':False},indent=2)+'\n')
print('Saved isolated eMMC placement:',out)
