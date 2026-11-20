#!/usr/bin/env python3
"""Molex 2012670005 top-view lands, reviewed drawing dimensions; KiCad Python.
Origin: midpoint of rear shield holes. +Y points toward mating edge.
"""
from pathlib import Path
import json
import pcbnew as p
ROOT=Path(__file__).resolve().parents[1]
def xy(x,y): return p.VECTOR2I(p.FromMM(x),p.FromMM(y))

def main():
    fp=p.FOOTPRINT(None)
    name='USB_C_Molex_2012670005'
    fp.SetValue('2012670005');fp.SetReference('J?')
    fp.SetAttributes(p.FP_SMD)
    fp.SetLibDescription('Molex 2012670005 drawing sheet2; 1.60mm PCB; engineering draft')
    fp.SetLocalClearance(p.FromMM(.15))
    lands=[]
    def pad(number,x,y,w,h,drill=None,offset=0):
        a=p.PAD(fp);a.SetNumber(number);a.SetPosition(xy(x,y));a.SetSize(xy(w,h))
        if drill:
            a.SetAttribute(p.PAD_ATTRIB_PTH);a.SetShape(p.PAD_SHAPE_OVAL)
            a.SetDrillShape(p.PAD_DRILL_SHAPE_OBLONG);a.SetDrillSize(xy(*drill))
            a.SetLayerSet(p.PAD.PTHMask());a.SetOffset(xy(0,offset))
        else:
            a.SetAttribute(p.PAD_ATTRIB_SMD);a.SetShape(p.PAD_SHAPE_RECT);a.SetLayerSet(p.PAD.SMDMask())
        fp.Add(a);lands.append({'pad':number,'xy_mm':[x,y],'size_mm':[w,h],'drill_mm':drill,'copper_offset_y_mm':offset})
    for i in range(12):
        pad('A'+str(i+1),-3+.5*i+(.5 if i>=6 else 0),-.81,.3,.7)
        x=3.05 if i==0 else -3.05 if i==11 else 2.75-.5*i
        pad('B'+str(i+1),x,.89,.9 if i in (0,11) else .3,.7)
    for x in (-4.32,4.32):pad('SH',x,0,1.1,2.1,(.6,1.6))
    for x in (-4.62,4.62):pad('SH',x,5.36,1.1,3.6,(.6,2.1),-.5)
    def rect(x1,y1,x2,y2,layer,width):
        a=p.PCB_SHAPE(fp);a.SetShape(p.SHAPE_T_RECT);a.SetStart(xy(x1,y1));a.SetEnd(xy(x2,y2));a.SetLayer(layer);a.SetWidth(p.FromMM(width));fp.Add(a)
    rect(-4.695,-1.17,4.695,7.13,p.F_Fab,.1)
    rect(-5.5,-1.5,5.5,7.5,p.F_CrtYd,.05)
    fp.Reference().SetPosition(xy(0,-2.5));fp.Value().SetPosition(xy(0,8.5));fp.Value().SetLayer(p.F_Fab)
    # Conservative placement restriction under connector body; not a vendor SI model.
    z=p.ZONE(fp);z.SetLayer(p.F_Cu);z.SetIsRuleArea(True);z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True);z.SetDoNotAllowPads(True);z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowFootprints(True)
    o=z.Outline();o.NewOutline()
    for x,y in [(-3.7,1.5),(3.7,1.5),(3.7,7.13),(-3.7,7.13)]:o.Append(p.FromMM(x),p.FromMM(y))
    fp.Add(z)
    fp.SetFPID(p.LIB_ID('Phoenix_Reviewed',name))
    p.FootprintSave(str(ROOT/'kicad/Phoenix_Reviewed.pretty'),fp)
    report={'part':'2012670005','jlc':'C565324','footprint':'Phoenix_Reviewed:'+name,
      'drawing_local':'reference/usb-C565324-sales-drawing-mirror.pdf',
      'drawing_local_revision':'C, 2018-10-17, sheet2 visually inspected',
      'current_manufacturer_drawing':'https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/201/201267/2012670005_sd.pdf',
      'current_revision_text_observed':'C4, 2026-09-07; change adds2012670006; downloaded current PDF unavailable, dimensional text compared',
      'board_edge_local_y_mm':7.13,'recommended_board_thickness_mm':1.6,
      'lands':lands,'npth_holes':0,
      'status':'DIMENSIONAL CANDIDATE; ASSEMBLY AND SIGNAL INTEGRITY NOT QUALIFIED',
      'limits':['Current revision graphical comparison still required before release.','1.6mm total thickness does not establish actual dielectric stackup or impedance.','Pad-to-copper nominal0.25mm annulus must include fabrication tolerances.','Conservative body keepout is an engineering addition; routing launch requires SI review.']}
    (ROOT/'review/usb-201267-footprint.json').write_text(json.dumps(report,indent=2)+'\n')
    print(name,len(lands),'lands')
if __name__=='__main__':main()
