#!/usr/bin/env python3
"""Audit exported schematic and KiCad-loaded footprint; run with KiCad Python."""
import csv,json,hashlib,collections,xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew as p
R=Path(__file__).resolve().parents[1];O=R/'migration-rk3562/experiments/emmc-8gb'
rows=list(csv.DictReader((O/'ball-disposition.csv').open()))
fp=p.FootprintLoad(str(O/'kicad/Phoenix_eMMC_Draft.pretty'),'Samsung_FBGA153_11.5x13_P0.5_DRAFT')
assert fp is not None
pads={x.GetNumber():x for x in fp.Pads()};assert len(pads)==153
for r in rows:
 pad=pads[r['ball']];pos=pad.GetPosition()
 assert abs(p.ToMM(pos.x)-float(r['x_mm']))<1e-6
 assert abs(p.ToMM(pos.y)-float(r['y_mm']))<1e-6
root=ET.parse(O/'review/netlist.xml').getroot();actual={}
for n in root.findall('./nets/net'):
 for v in n.findall('node'):actual[(v.get('ref'),v.get('pin'))]=n.get('name').lstrip('/')
contract=json.loads((O/'review/emmc-storage-candidate-expected.json').read_text());verified=0
for r in contract:
 key=(r['ref'],r['pin']);got=actual.get(key)
 if r['net'] is None:
  assert got is None or got.startswith('unconnected-'),(key,got)
 else:assert got==r['net'],(key,got,r['net'])
 verified+=1
# Independent datasheet anchors, to detect generator regression.
for ball,net in {'A3':'EMMC_D0','B6':'EMMC_D7','C2':'EMMC_VDDI','M6':'EMMC_CLK','M5':'EMMC_CMD','H5':'EMMC_STRB','K5':'EMMC_RESET_N','E6':'EMMC_3V3','C6':'EMMC_IO_1V8','P6':'GND'}.items():assert actual['U8001',ball]==net
assert actual['C8001','1']=='EMMC_VDDI' and actual['C8001','2']=='GND'
assert actual['R8004','1']=='SOC_EMMC_CLK' and actual['R8004','2']=='EMMC_CLK'
base=R/'migration-rk3562/experiments/lpddr4-1gb';cp=json.loads((base/'working-board.json').read_text());src=base/cp['board'];sha=hashlib.sha256(src.read_bytes()).hexdigest();assert sha==cp['sha256']
d=json.loads((O/'review/erc.json').read_text());counts=collections.Counter(v['type'] for s in d['sheets'] for v in s['violations'])
assert not counts.get('endpoint_off_grid')
report={'status':'ISOLATED_NETLIST_AND_FOOTPRINT_AUDITED_NOT_RELEASE','verified_pin_dispositions':verified,'footprint_pads':len(pads),'source_board_unchanged':True,'erc_categories':dict(counts),'footprint_land_and_paste_qualified':False,'integrated_into_system':False,'assembly_ready':False}
(O/'review/audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
