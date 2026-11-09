#!/usr/bin/env python3
"""Independent screening of drill geometry against public JLC standard capabilities.
Run using KiCad Python. Not a complete DFM or a manufacturer approval.
"""
import json, math
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[1]

def main():
    board=p.LoadBoard(str(ROOT/'kicad/floorplan/phoenix-g1-floorplan.kicad_pcb'))
    findings=[];checked=0;annular=[]
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            d=pad.GetDrillSize(); w,h=p.ToMM(d.x),p.ToMM(d.y)
            if not w or not h:continue
            checked+=1
            npth=pad.GetAttribute()==p.PAD_ATTRIB_NPTH
            slot=pad.GetDrillShape()==p.PAD_DRILL_SHAPE_OBLONG and abs(w-h)>1e-6
            reasons=[]
            if npth and slot and min(w,h)<1.0-1e-6:
                reasons.append('NPTH slot width below published 1.0 mm standard minimum; alternate connector or explicit fabrication process required')
            if npth and not slot and min(w,h)<.5-1e-6:
                reasons.append('NPTH round hole below 0.50 mm minimum')
            if not npth and slot:
                if min(w,h)<.5-1e-6:reasons.append('PTH slot below conservative 0.50 mm minimum (capability table and description differ)')
                if max(w,h)<2*min(w,h)-1e-6:reasons.append('PTH slot length below twice width')
            if not npth:
                size=pad.GetSize()
                # Nominal centred round/oval pads only: custom shapes and offsets
                # require a polygon-distance calculation, not a bounding-box claim.
                offset=pad.GetOffset()
                if pad.GetShape()==p.PAD_SHAPE_OVAL and slot and h>=w and p.ToMM(size.y)>=p.ToMM(size.x):
                    # Parallel vertical capsules: distance of inner centreline
                    # endpoints from the outer centreline, subtracted from
                    # radius difference. Handles the Molex offset copper lands.
                    outer_half=(p.ToMM(size.y)-p.ToMM(size.x))/2
                    inner_half=(h-w)/2
                    excess=max(0,abs(p.ToMM(offset.y))+inner_half-outer_half)
                    ring=(p.ToMM(size.x)-w)/2-math.hypot(p.ToMM(offset.x),excess)
                    annular.append({'ref':fp.GetReference(),'pad':pad.GetNumber(),'nominal_min_ring_mm':round(ring,4),'method':'parallel capsule containment including copper offset'})
                    if ring<.15-1e-6:reasons.append('Nominal offset oval PTH annular ring below0.15mm')
                elif pad.GetShape() in (p.PAD_SHAPE_CIRCLE,p.PAD_SHAPE_OVAL,p.PAD_SHAPE_RECT,p.PAD_SHAPE_ROUNDRECT) and not offset.x and not offset.y:
                    ring=min((p.ToMM(size.x)-w)/2,(p.ToMM(size.y)-h)/2)
                    annular.append({'ref':fp.GetReference(),'pad':pad.GetNumber(),'nominal_min_ring_mm':round(ring,4)})
                    if ring<.15-1e-6:reasons.append('Nominal PTH annular ring below published 0.15 mm multilayer minimum')
                else:
                    reasons.append('PTH annular ring not evaluated for offset/custom pad; manual geometry review required')
            if reasons:findings.append({'ref':fp.GetReference(),'pad':pad.GetNumber() or 'mechanical','drill_mm':[w,h],'npth':npth,'reasons':reasons})
    report={'status':'HOLD' if findings else 'PASS LIMITED DRILL SCREEN','checked_drilled_pads':checked,
            'source':'https://jlcpcb.com/capabilities/pcb-capabilities','source_checked_date':'2026-11-07',
            'copper_edge_rule_mm':.25,'copper_edge_rule_basis':'0.20 mm published minimum plus 0.05 mm design margin; applies also to NPTH edges in KiCad',
            'annular_ring_screen':annular,'minimum_pth_ring_mm':.15,
            'findings':findings,'limitations':['Nominal pad/drill geometry only: does not assess drill registration, positional tolerances, hole-to-hole spacing, impedance, mask webs, assembly, via filling or mechanical fit.','Rectangular/rounded pads use an axis-based screen, not a complete minimum polygon-distance proof.','Does not screen routing vias; use full DRC and fabrication review after routing.','No DRC exclusions or manufacturer exceptions are inferred.']}
    (ROOT/'review/fabrication-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
