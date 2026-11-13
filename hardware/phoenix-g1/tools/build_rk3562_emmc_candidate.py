#!/usr/bin/env python3
"""Reproducible isolated eMMC draft; never edits the verified PCB or system."""
import csv, hashlib, json, sys
from pathlib import Path
import sexpdata as sx
import schematic_builder as sb
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'migration-rk3562/experiments/emmc-8gb'
BASE=ROOT/'migration-rk3562/experiments/lpddr4-1gb'
ROWS='ABCDEFGHJKLMNP'

def main():
 for d in ['kicad','review','kicad/Phoenix_eMMC_Draft.pretty']:(OUT/d).mkdir(parents=True,exist_ok=True)
 checkpoint=json.loads((BASE/'working-board.json').read_text());source=BASE/checkpoint['board']
 assert hashlib.sha256(source.read_bytes()).hexdigest()==checkpoint['sha256']
 cols={r:list(range(1,15)) for r in ROWS}
 cols['D']=[1,2,3,4,12,13,14]
 for r in 'EK':cols[r]=[1,2,3,5,6,7,8,9,10,12,13,14]
 for r in 'FGHJ':cols[r]=[1,2,3,5,10,12,13,14]
 cols['L']=[1,2,3,12,13,14]
 balls={r+str(c):'NC' for r in ROWS for c in cols[r]}
 for b in 'A7 E5 E8 E9 E10 F10 G3 G10 K6 K7 K10 P7 P10'.split():balls[b]='RFU'
 for i,b in enumerate('A3 A4 A5 B2 B3 B4 B5 B6'.split()):balls[b]='DAT'+str(i)
 for name,bs in {'RSTN':'K5','CMD':'M5','CLK':'M6','STRB':'H5','VDDI':'C2','VCCQ':'C6 M4 N4 P3 P5','VCC':'E6 F5 J10 K9','VSS':'J5 A6 C4 E7 G5 H10 K8 N2 N5 P4 P6'}.items():
  for b in bs.split():balls[b]=name
 assert len(balls)==153
 rows=[{'ball':b,'function':n,'x_mm':(int(b[1:])-7.5)*.5,'y_mm':(ROWS.index(b[0])-6.5)*.5} for b,n in balls.items()]
 with (OUT/'ball-disposition.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
 pins={}
 for r in csv.DictReader((ROOT/'migration-rk3562/review/manufacturer-pins.csv').open()):
  for n in r['name'].split('/'):
   if n.startswith('EMMC_'):pins[n]=r['ball']
 contracts=[]
 for f in (BASE/'system/review').glob('*expected.json'):
  contracts += json.loads(f.read_text())
 old={r['pin']:r for r in contracts if r.get('ref')=='U1'}
 mapping=[]
 for b,n in balls.items():
  signal='EMMC_D'+n[3:] if n.startswith('DAT') else 'EMMC_'+n
  if signal in pins:
   soc=pins[signal];mapping.append({'signal':signal,'soc_ball':soc,'emmc_ball':b,'previous_net':old[soc]['net']})
 assert len(mapping)==11
 assert old['1F14']['net']=='+3V3_IO'
 (OUT/'signal-map.json').write_text(json.dumps(mapping,indent=2)+'\n')
 name='KLM8G1GETF_B041_DRAFT';fp='Phoenix_eMMC_Draft:Samsung_FBGA153_11.5x13_P0.5_DRAFT'
 signals=[(b,n) for b,n in balls.items() if n.startswith('DAT') or n in ('RSTN','CMD','CLK','STRB')]
 power=[(b,n) for b,n in balls.items() if n in ('VDDI','VCCQ','VCC','VSS')]
 unused=[(b,n) for b,n in balls.items() if n in ('NC','RFU')]
 groups=[signals,power]+[unused[i:i+40] for i in range(0,len(unused),40)]
 symbol=f'(symbol "{name}" (pin_names (offset 0.5)) (in_bom yes) (on_board yes) (property "Reference" "U" (at 0 0 0) (effects (font (size 1 1)))) (property "Value" "KLM8G1GETF-B041" (at 0 0 0) (effects (font (size 1 1)))) (property "Footprint" "{fp}" (at 0 0 0) (effects (font (size 1 1)) hide))'
 for u,group in enumerate(groups,1):
  h=(len(group)+1)*2.54
  symbol+=f'(symbol "{name}_{u}_1" (rectangle (start -12.7 2.54) (end 12.7 {-h}) (stroke (width 0.254)(type default))(fill(type background)))'
  for i,(b,n) in enumerate(group):
   typ='no_connect' if n in ('NC','RFU') else 'power_in' if n in ('VCC','VCCQ','VSS') else 'passive' if n=='VDDI' else 'input' if n in ('CLK','RSTN') else 'output' if n=='STRB' else 'bidirectional'
   symbol+=f'(pin {typ} line (at -15.24 {-i*2.54} 0)(length 2.54)(name "{n}" (effects(font(size 1 1))))(number "{b}" (effects(font(size 1 1)))))'
  symbol+=')'
 symbol+=')'
 lib=f'(kicad_symbol_lib (version 20250114)(generator "kicad_symbol_editor"){symbol})'
 (OUT/'kicad/Phoenix_eMMC_Draft.kicad_sym').write_text(lib+'\n')
 sb.ROOT=OUT
 standard=sx.loads((sb.STANDARD/'Device.kicad_sym').read_text())
 symbols={name:sx.loads(symbol)}
 for entry in sb.fields(standard,'symbol'):
  if entry[1] in ('R','C'):symbols[entry[1]]=entry
 sheet=sb.Sheet('emmc-storage-candidate','eMMC 8GB - ISOLATED ENGINEERING DRAFT','Phoenix_eMMC_Draft',symbols)
 original_place=sheet.place
 def place(name,ref,x,y,nets,**kwargs):
  return original_place(name,ref,round(x/1.27)*1.27,round(y/1.27)*1.27,nets,**kwargs)
 sheet.place=place
 def net(n):
  if n in ('NC','RFU'):return None
  if n.startswith('DAT'):return 'EMMC_D'+n[3:]
  return {'VCC':'EMMC_3V3','VCCQ':'EMMC_IO_1V8','VSS':'GND','VDDI':'EMMC_VDDI','RSTN':'EMMC_RESET_N','CMD':'EMMC_CMD','CLK':'EMMC_CLK','STRB':'EMMC_STRB'}[n]
 for u,g in enumerate(groups,1):
  x,y=[(70,50),(150,50),(230,50),(310,50),(390,50)][u-1]
  sheet.place(name,'U8001',x,y,{b:net(n) for b,n in g},unit=u)
 # Reference-derived support values, not yet sourcing/power-integrity qualified.
 sheet.place('R','R8001',40,200,{'1':'EMMC_IO_1V8','2':'EMMC_D0'},value='10k candidate')
 sheet.place('R','R8002',100,200,{'1':'EMMC_IO_1V8','2':'EMMC_CMD'},value='10k candidate')
 sheet.place('R','R8003',160,200,{'1':'EMMC_IO_1V8','2':'EMMC_RESET_N'},value='10k candidate')
 sheet.place('R','R8004',220,200,{'1':'SOC_EMMC_CLK','2':'EMMC_CLK'},value='22R candidate')
 # Samsung rev1.21 table37: data-strobe pull-down 10..100 kohm for HS400.
 sheet.place('R','R8005',280,200,{'1':'EMMC_STRB','2':'GND'},value='47k candidate')
 caps=[('EMMC_VDDI','2.2u candidate')]+[('EMMC_IO_1V8','100n candidate')]*4+[('EMMC_IO_1V8','4.7u candidate')]+[('EMMC_3V3','100n candidate')]*2+[('EMMC_3V3','4.7u candidate')]
 for i,(rail,val) in enumerate(caps):sheet.place('C',f'C{8001+i}',35+i*40,230,{'1':rail,'2':'GND'},value=val)
 sheet.place('C','C8010',35,255,{'1':'EMMC_IO_1V8','2':'GND'},value='100n VCCIO2 at SoC candidate')
 sheet.note('C8010 belongs beside SoC VCCIO2 U1.1F14; memory bypass capacitors remain beside eMMC.',25,270)
 sheet.note('NO PRODUCTION RELEASE. Isolated ports; supplies/reset/boot and support MPNs require qualification.',25,280)
 sheet.save()
 (OUT/'kicad/sym-lib-table').write_text('(sym_lib_table (version 7)(lib(name "Phoenix_eMMC_Draft")(type "KiCad")(uri "${KIPRJMOD}/Phoenix_eMMC_Draft.kicad_sym")(options "")(descr "Draft")))\n')
 for table in ('sym-lib-table','fp-lib-table'):
  target=OUT/'kicad'/table
  if target.exists():target.write_text(sx.dumps(sx.loads(target.read_text()))+'\n')
 # Include support symbols in local library to preserve library consistency.
 (OUT/'kicad/Phoenix_eMMC_Draft.kicad_sym').write_text('(kicad_symbol_lib(version 20250114)(generator "kicad_symbol_editor")'+''.join(sx.dumps(s) for s in symbols.values())+')\n')
 (OUT/'kicad/fp-lib-table').write_text('(fp_lib_table(version 7)(lib(name "Phoenix_eMMC_Draft")(type "KiCad")(uri "${KIPRJMOD}/Phoenix_eMMC_Draft.pretty")(options "")(descr "Unqualified land pattern")))\n')
 target=OUT/'kicad/fp-lib-table';target.write_text(sx.dumps(sx.loads(target.read_text()))+'\n')
 foot='(footprint "Samsung_FBGA153_11.5x13_P0.5_DRAFT" (version 20241229)(generator "pcbnew")(layer "F.Cu")(attr smd)'
 foot+='(fp_rect(start -5.75 -6.5)(end 5.75 6.5)(stroke(width 0.1)(type default))(fill none)(layer "F.Fab"))'
 foot+='(fp_rect(start -6.05 -6.8)(end 6.05 6.8)(stroke(width 0.05)(type default))(fill none)(layer "F.CrtYd"))'
 foot+='(fp_line(start -5.75 -5.5)(end -4.75 -6.5)(stroke(width 0.15)(type default))(layer "F.Fab"))'
 for r in rows:foot+=f'(pad "{r["ball"]}" smd circle(at {r["x_mm"]} {r["y_mm"]})(size 0.25 0.25)(layers "F.Cu" "F.Paste" "F.Mask"))'
 foot+=')\n';(OUT/'kicad/Phoenix_eMMC_Draft.pretty/Samsung_FBGA153_11.5x13_P0.5_DRAFT.kicad_mod').write_text(foot)
 report={'status':'ISOLATED_DRAFT_NOT_INTEGRATED','part':'KLM8G1GETF-B041','jlc':'C499918','ball_count':len(balls),'signal_connections':len(mapping),'NC_count':len([v for v in balls.values() if v=='NC']),'RFU_count':len([v for v in balls.values() if v=='RFU']),'body_mm':[11.5,13,0.8],'pitch_mm':.5,'draft_land_mm':.25,'source_pcb_sha256':checkpoint['sha256'],'datasheet_sha256':hashlib.sha256((ROOT/'reference/samsung-klm8g1getf-b041.pdf').read_bytes()).hexdigest(),'source_pages':[4,5,6],'reference_pages':[8,14],'required_changes':['Replace conflicting FSPI boot circuit, not parallel connection','VCCIO2 U1.1F14 from +3V3_IO to qualified 1.8V eMMC IO rail; keep unrelated VCCIO domains unchanged','Qualify reset pull-up and boot strap/USB recovery before integration','Qualify VDDI capacitor against exact Samsung application requirements','Use a suitably sized Linux image; do not assume the ROCK microSD image fits','Integrate qualified support MPNs, complete power sequencing/current review','Full PCB placement/escape/routing and signal integrity review'],'assembly_ready':False}
 assert hashlib.sha256(source.read_bytes()).hexdigest()==checkpoint['sha256']
 (OUT/'candidate.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
