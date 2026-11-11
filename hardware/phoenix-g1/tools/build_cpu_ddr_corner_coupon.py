#!/usr/bin/env python3
"""Five constrained CPU DDR escapes, isolated KiCad geometry experiment."""
import json,math
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'migration-rk3562';P=BASE/'experiments/lpddr4-1gb';OUT=P/'cpu-corner-coupon'
def point(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
def main():
    OUT.mkdir(exist_ok=True);b=pcbnew.BOARD();b.SetCopperLayerCount(6)
    f=pcbnew.FootprintLoad(str(BASE/'kicad/Phoenix_RK3562_Candidates.pretty'),'RK3562_FCCSP478_13.9mm_MIXED_PITCH_CANDIDATE');f.SetReference('U1');f.SetPosition(point(10,10));b.Add(f)
    contract={r['pin']:r['net'] for r in json.loads((P/'system/review/integrated-contract.json').read_text()) if r['ref']=='U1'};nets={}
    for name in sorted({n for n in contract.values() if n}):n=pcbnew.NETINFO_ITEM(b,name);b.Add(n);nets[name]=n
    pads={p.GetNumber():p for p in f.Pads()}
    for ball,pad in pads.items():
        if contract[ball]:pad.SetNet(nets[contract[ball]])
    entries=[r for r in json.loads((P/'system/review/cpu-escape-bends.json').read_text())['results'] if r['found']]
    for r in entries:
        path=r['path_mm'];ball=r['ball']
        # Separate adjacent via lands by moving the outer endpoint, not by reducing via clearance.
        if ball in ['B2','C2']:path=path+[(path[-1][0]-(.45 if ball=='C2' else .1),path[-1][1])]
        else:path=path+[(path[-1][0],path[-1][1]-(.45 if ball=='B25' else .1))]
        for a,z in zip(path,path[1:]):
            t=pcbnew.PCB_TRACK(b);t.SetStart(point(a[0]+10,a[1]+10));t.SetEnd(point(z[0]+10,z[1]+10));t.SetLayer(pcbnew.F_Cu);t.SetWidth(pcbnew.FromMM(.0762));t.SetNet(pads[ball].GetNet());b.Add(t)
        x,y=path[-1];v=pcbnew.PCB_VIA(b);v.SetPosition(point(x+10,y+10));v.SetWidth(pcbnew.FromMM(.45));v.SetDrill(pcbnew.FromMM(.2));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(pads[ball].GetNet());b.Add(v)
    for a,z in [((0,0),(20,0)),((20,0),(20,20)),((20,20),(0,20)),((0,20),(0,0))]:
        line=pcbnew.PCB_SHAPE();line.SetShape(pcbnew.SHAPE_T_SEGMENT);line.SetStart(point(*a));line.SetEnd(point(*z));line.SetLayer(pcbnew.Edge_Cuts);line.SetWidth(pcbnew.FromMM(.05));b.Add(line)
    pcbnew.SaveBoard(str(OUT/'cpu-corners.kicad_pcb'),b)
    pro=json.loads((P/'fanout-coupon/fanout.kicad_pro').read_text());pro['board']['design_settings']['rules']['min_track_width']=.0762;pro['net_settings']['classes'][0]['clearance']=.0762
    (OUT/'cpu-corners.kicad_pro').write_text(json.dumps(pro,indent=2)+'\n')
    (OUT/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "Phoenix_RK3562_Candidates") (type "KiCad") (uri "${KIPRJMOD}/../../../kicad/Phoenix_RK3562_Candidates.pretty") (options "") (descr "Draft")))\n')
    (OUT/'manifest.json').write_text(json.dumps({'status':'FIVE_PIN_GEOMETRY_EXPERIMENT','balls':[r['ball'] for r in entries],'width_clearance_mm':[.0762,.0762],'via_mm':[.45,.2],'fabrication_approval':False,'not_validated':['remaining 60 signals simultaneously','neighbor components','return planes','impedance','skew','land/paste pattern']},indent=2)+'\n');print('5 CPU escapes generated')
if __name__=='__main__':main()
