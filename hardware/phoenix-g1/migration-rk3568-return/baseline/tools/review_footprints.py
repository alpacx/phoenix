#!/usr/bin/env python3
"""Narrow, documented repairs to imported footprints. Originals are preserved.
This is NOT a complete dimensional/DFM qualification.
"""
from schematic_builder import *
def main():
 out=ROOT/'kicad/Phoenix_Reviewed.pretty';out.mkdir(exist_ok=True);mapping={};audit=[]
 cases=[('Phoenix_Candidates','WQFN-30_L4.5-W2.5-P0.4-BL-EP','mux'),('Phoenix_Candidates','QFN-68_L7.0-W7.0-P0.35-BL-EP5.5','pmic'),('Import_C97522','WSON-8_L8.0-W6.1-P1.27-BL-EP','flash'),('Phoenix_Candidates','RJ45-TH_HR911130A','jack'),('Phoenix_Candidates','USB-C-SMD_TYPE-C-24P-QT','usb')]
 for lib,name,kind in cases:
  src=ROOT/f'kicad/{lib}.pretty/{name}.kicad_mod'
  if not src.exists():
   if kind=='flash':src=next((ROOT/f'kicad/{lib}.pretty').glob('*.kicad_mod'));name=src.stem
   else:raise FileNotFoundError(src)
  fp=sx.loads(src.read_text());changed=[]
  if kind=='usb':
   for pad in fields(fp,'pad'):
    num=str(pad[1])
    if num.startswith(('A','B')) and num[1:].isdigit():
     index=int(num[1:])-1
     fields(pad,'at')[0][1]=round(-2.625+.5*index if num[0]=='A' else 2.625-.5*index,3)
     fields(pad,'size')[0][1:]=[.25,.95]
   changed.append('Restored manufacturer page6 contact lands: 0.25x0.95mm, exact0.5mm pitch and0.25mm row stagger. L-shaped shield holes and peg clearances remain unresolved.')
  if kind=='mux':
   for pad in fields(fp,'pad'):
    if str(pad[3])=='custom':
     for poly in walk(pad,'gr_poly'):
      fields(poly,'width')[0][1]=0
      for point in walk(poly,'xy'):point[1:]=[round(float(v),3) for v in point[1:]]
     changed.append('Removed erroneous 0.1mm stroke inflation from corner copper polygons; rounded coordinates to exact TI 0.2x0.5mm/chamfer geometry.')
    if str(pad[1])=='31':fields(pad,'layers')[0][:]=[sx.Symbol('layers'),'F.Cu','F.Mask']
   for cx in [-.8,.8]:
    fp.append(sx.loads(f'(pad "" smd roundrect (at {cx} 0) (size 1.39 1.13) (layers "F.Paste") (roundrect_rratio 0.0442478))'))
   changed.append('Split EP paste into two 1.39x1.13mm windows per TI stencil example, approximately82% coverage.')
  for pad in list(fields(fp,'pad')):
   if str(pad[1])!='' or str(pad[2])!='thru_hole':continue
   if kind=='pmic':
    pad[1]='69';layers=fields(pad,'layers')[0];layers[:]=[sx.Symbol('layers'),'*.Cu']
    changed.append('Anonymous thermal via assigned EP69/GND; no paste/mask opening on via primitive. Filled/capped process required.')
   elif kind=='flash':fp.remove(pad);changed.append('Removed exposed central via per Winbond FAQ; EP9 retained and grounded.')
   else:pad[2]=sx.Symbol('np_thru_hole');changed.append('Plastic locating peg hole changed from plated to non-plated; original diameter/position retained.')
  (out/(name+'.kicad_mod')).write_text(sx.dumps(fp)+'\n');mapping[lib+':'+name]='Phoenix_Reviewed:'+name
  audit.append({'source':lib+':'+name,'output':mapping[lib+':'+name],'changes':changed,'not_qualified':'Dimensions, copper/stencil geometry, assembly and all remaining DRC need review.'})
 (ROOT/'review/footprint-overrides.json').write_text(json.dumps(mapping,indent=2)+'\n');(ROOT/'review/footprint-repairs.json').write_text(json.dumps(audit,indent=2)+'\n')
 p=ROOT/'kicad/fp-lib-table';s=p.read_text()
 if '(name "Phoenix_Reviewed")' not in s:p.write_text(s.rstrip()[:-1]+' (lib (name "Phoenix_Reviewed")(type "KiCad")(uri "${KIPRJMOD}/Phoenix_Reviewed.pretty")(options "")(descr "Limited reviewed repairs; not fully qualified"))\n)\n')
 print([(a['source'],len(a['changes'])) for a in audit])
if __name__=='__main__':main()
