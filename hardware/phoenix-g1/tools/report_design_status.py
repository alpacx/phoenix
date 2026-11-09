#!/usr/bin/env python3
"""Machine-readable release gate and selected main-parts estimate, not an assembly BOM."""
from pathlib import Path
import json,re,collections,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
def main():
 old=json.loads((ROOT/'sourcing/availability.json').read_text());prior={p['jlc']:p for group in old.values() if isinstance(group,list) for p in group if isinstance(p,dict) and 'jlc' in p}
 selected={code:len(refs.split()) for code,refs in json.loads((ROOT/'sourcing/selected-references.json').read_text()).items()}
 parts=[]
 for code,qty in selected.items():
  public=ROOT/f'sourcing/public/{code}.json'
  if public.exists():
   v=json.loads(public.read_text());p={'jlc':code,'qty':qty,'mpn':v.get('componentModelEn'),'unit_usd':v.get('initialPrice'),'available_order_qty':v.get('canPresaleNumber'),'displayed_stock':v.get('overseasStockCount'),'checked_utc':v.get('retrieved_utc'),'source':v['source_url']}
  elif code in prior:
   v=prior[code];p={'jlc':code,'qty':qty,'mpn':v['mpn'],'unit_usd':v['unit_price'],'observed_stock':v['stock'],'checked_date':v.get('checked_date',old['checked_date']),'source':v.get('url',v.get('source'))}
  else:raise RuntimeError('No sourcing evidence '+code)
  p['extended_usd']=round(float(p['unit_usd'])*qty,4);parts.append(p)
 total=round(sum(p['extended_usd'] for p in parts),4)
 (ROOT/'sourcing/selected-main-parts.json').write_text(json.dumps({'status':'PROVISIONAL SELECTION - NOT PCBA BOM','currency':'USD','price_basis':'1+ unit prices, observed on dates per line; not a quote','subtotal':total,'excluded':['Any circuit additions required by qualification','Additional EMI/ESD protection still to design','PCB, assembly, tooling, attrition, freight, taxes','Heatsink, housing, display attachment process'],'parts':parts},indent=2)+'\n')
 x=ET.parse(ROOT/'review/integrated.xml');parts_xml=x.findall('.//components/comp');unqualified=[];no_fp=[]
 for c in parts_xml:
  ref=c.get('ref');mpn=c.findtext("fields/field[@name='MPN']",'')
  if ref.startswith('TP'):continue
  if not mpn or mpn=='UNQUALIFIED':unqualified.append({'ref':ref,'value':c.findtext('value')})
  if not c.findtext('footprint'):no_fp.append(ref)
 drc=(ROOT/'review/floorplan-drc.txt').read_text();counts=dict(collections.Counter(re.findall(r'^\[([^]]+)\]',drc,re.M)))
 erc=(ROOT/'review/integrated-erc.txt').read_text()
 erc_items=re.findall(r'^\[([^]]+)\]',erc,re.M)
 floorplan=json.loads((ROOT/'review/floorplan.json').read_text())
 gates={
 'schematic_erc':('PASS: no reported violations in current KiCad model; does not prove circuit completeness' if not erc_items and re.search(r'(?i)(violations|violazioni|messages|messaggi)',erc) else 'REVIEW: inspect ERC report'),
 'pin_transcription':json.loads((ROOT/'review/integrated-connectivity.json').read_text())['status'],
 'pcb_routing':f"FAIL: {floorplan['tracks']} tracks; {floorplan.get('unconnected_ratsnest_edges','unknown')} unconnected ratsnest edges; DRC displays {counts.get('unconnected_items',0)} items (can be capped)",
 'pcb_drc':('HOLD: no geometric violations with current rules; board remains unrouted and unqualified' if not any(n for k,n in counts.items() if k!='unconnected_items') else 'FAIL: see categorized counts'),
 'usb_connector':'HOLD: Molex2012670005/1.6mm selected; thickness conflict resolved; current drawing reconciliation, assembly and launch SI remain open',
 'fabrication_drills':json.loads((ROOT/'review/fabrication-screen.json').read_text())['status']+': see fabrication-screen.json',
 'bom':('HOLD: all present positions have candidates; electrical, footprint and assembly qualification incomplete' if not unqualified else 'FAIL: positions without selected MPN remain'),
 'display':'FAIL: FPC footprint/attachment and internal VDDIO relationship unresolved',
 'magnetics':'FAIL: shared-center-tap configuration for exact RTL8211F/BSP not qualified',
 'protection':'FAIL: PHY-side ESD clamps added; chassis bonding, VBUS transient/discharge and system surge review incomplete',
 'power_integrity':'FAIL: effective MLCC capacitance, load budget, startup/brownout and thermal behavior unqualified',
 'signal_integrity':'FAIL: exact dielectric stackup, impedance, BGA escape and DDR/USB/RGMII routing not designed',
 'software_boot':'HOLD: DDR loader documentation checked in boot-software-check.json; binary configuration, boot ROM compatibility, 32MiB image budget and recovery untested',
 'wifi':'HOLD: connectivity checked; dedicated3.584V VBAT static screen includes feedback leakage and resistor temperature drift, before other losses; RF, oscillator, firmware and AP mode unqualified; see wifi-power-check.json',
 'cost':'FAIL: 50 EUR assembled target not established; selected subtotal includes assigned Wi-Fi parts but excludes qualification-driven additions, PCB, assembly and enclosure',
 'thermal':'HOLD: fanless is mandatory; passive-thermal-screen.json is hypothetical sensitivity, not measured board power or qualified enclosure',
 'prototype':'NOT RUN: no custom hardware manufactured'}
 report={'release_ready':False,'gerbers_generated':False,'parts_estimate_usd':total,'physical_components_in_netlist':len(parts_xml),'unqualified_or_unannotated_mpn_count':len(unqualified),'unqualified_or_unannotated_mpns':unqualified,'missing_footprints':no_fp,'drc_categories':counts,'gates':gates}
 (ROOT/'review/release-gate.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Main parts subtotal USD',total,'; unqualified/unannotated MPNs',len(unqualified),'; DRC',counts)
if __name__=='__main__':main()
