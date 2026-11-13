#!/usr/bin/env python3
"""Verify exported connectivity, original copper preservation and candidate DRC."""
import json,hashlib,collections,xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew as p
R=Path(__file__).resolve().parents[1];E=R/'migration-rk3562/experiments';O=E/'stacked-expansion';B=E/'lpddr4-1gb'
cp=json.loads((B/'working-board.json').read_text());src=B/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
a=p.LoadBoard(str(src));b=p.LoadBoard(str(O/'pcb/candidate.kicad_pcb'))
def tracks(board):
 return sorted((t.m_Uuid.AsString(),t.GetClass(),t.GetNetname(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth()),t.GetDrillValue() if isinstance(t,p.PCB_VIA) else 0) for t in board.GetTracks())
assert tracks(a)==tracks(b),'Existing copper changed'
fps={f.GetReference():f for f in b.GetFootprints()};assert len(fps)==len(list(b.GetFootprints()))
ids=[]
for f in b.GetFootprints():
 ids.extend(i.m_Uuid.AsString() for i in [f,*f.Pads(),*f.GraphicalItems(),*f.GetFields()])
assert len(ids)==len(set(ids)),'Duplicate board UUID'
root=ET.parse(O/'system/review/netlist.xml').getroot();actual={}
for n in root.findall('./nets/net'):
 for node in n.findall('node'):actual[node.get('ref'),node.get('pin')]=n.get('name').lstrip('/')
rows=[]
for name in ['expansion','expansion-power']:
 rows+=json.loads((O/f'system/review/{name}-expected.json').read_text())
rows += [{'ref':'U1','pin':ball,'net':net} for ball,net in [('AE26','ADDON_USB_DM'),('AE27','ADDON_USB_DP')]]
for r in rows:
 key=r['ref'],r['pin'];want=r['net'];got=actual.get(key)
 assert got==want or (want is None and (got is None or got.startswith('unconnected-'))),(key,want,got)
 pads=[pad for pad in fps[r['ref']].Pads() if pad.GetNumber()==r['pin']];assert len(pads)==1,key
 assert pads[0].GetNetname()==(want or ''),(key,pads[0].GetNetname(),want)
# Ensure USB-C, RAM and all other pad assignments were not silently changed.
changed={('U1','AE26'),('U1','AE27')}
for f in a.GetFootprints():
 if f.GetReference()=='J3':continue
 after={pad.GetNumber():pad.GetNetname() for pad in fps[f.GetReference()].Pads()}
 for pad in f.Pads():
  if (f.GetReference(),pad.GetNumber()) not in changed:assert after[pad.GetNumber()]==pad.GetNetname()
for c in root.findall('./components/comp'):
 ref=c.get('ref')
 if ref=='J3' or ref.startswith(('R810','C810','U810')):
  assert (str(fps[ref].GetFPID().GetLibNickname())+':'+str(fps[ref].GetFPID().GetLibItemName()))==c.findtext('footprint'),(ref,(str(fps[ref].GetFPID().GetLibNickname())+':'+str(fps[ref].GetFPID().GetLibItemName())),c.findtext('footprint'))
d=json.loads((O/'pcb/drc.json').read_text());counts=collections.Counter(v['type'] for v in d['violations'])
base=json.loads((B/'wifi-relocation/io-drc.json').read_text());assert counts==collections.Counter(v['type'] for v in base['violations'])
for category in ['shorting_items','clearance','courtyards_overlap','lib_footprint_issues']:assert not counts[category]
erc=json.loads((O/'system/review/erc.json').read_text());ec=collections.Counter(v['type'] for s in erc['sheets'] for v in s['violations'])
report={'status':'SCHEMATIC_AND_PLACEMENT_AUDITED_NOT_ROUTED','verified_pin_dispositions':len(rows),'old_tracks_and_vias_preserved':len(tracks(a)),'original_pad_nets_preserved_except_dedicated_host':True,'unique_board_item_UUIDs':len(ids),'source_board_unchanged':True,'pcb_sha256':hashlib.sha256((O/'pcb/candidate.kicad_pcb').read_bytes()).hexdigest(),'drc_categories':dict(counts),'unconnected_items_reported':len(d['unconnected_items']),'unconnected_count_may_be_capped':True,'erc_categories':dict(ec),'assembly_ready':False}
(O/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
