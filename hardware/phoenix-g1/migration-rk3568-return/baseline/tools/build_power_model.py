#!/usr/bin/env python3
"""KiCad ERC source declarations, only after a checked netlist proves each DC path.
These annotations do not imply current capability, enabled state or power integrity.
"""
from schematic_builder import *
def main():
 report=json.loads((ROOT/'review/integrated-connectivity.json').read_text());assert report['status']=='PASS'
 paths=report['power_paths'];assert all('source' in p for p in paths.values())
 lib=sx.loads((STANDARD/'power.kicad_sym').read_text());s=next(s for s in fields(lib,'symbol') if s[1]=='PWR_FLAG');syms={'PWR_FLAG':s};save_library('Phoenix_PowerModel',syms)
 sh=Sheet('power-source-model','Phoenix G1 - explicit ERC power-source model','Phoenix_PowerModel',syms)
 for i,(net,path) in enumerate(paths.items()):
  x=35.56+(i%4)*96.52;y=45.72+(i//4)*50.8
  sh.place('PWR_FLAG',f'#FLG{i+1:03d}',x,y,{'1':net},mpn='ERC annotation only',fp='')
  sh.note(path['source']+' via '+(','.join(path['passive_path']) or 'external USB cable'),x-20,y+15)
 sh.note('Flags describe sources through passive R/L paths that KiCad does not propagate. No ERC exclusions are used.',15,253)
 sh.note('Evidence: review/integrated-connectivity.json. Not a guarantee of source state, sequencing, current or stability.',15,261)
 sh.save();p=ROOT/'kicad/power-source-model.kicad_sch';sch=sx.loads(p.read_text())
 for symbol in fields(sch,'symbol'):
  fields(symbol,'in_bom')[0][1]=sx.Symbol('no');fields(symbol,'on_board')[0][1]=sx.Symbol('no')
 p.write_text(sx.dumps(sch)+'\n')
if __name__=='__main__':main()
