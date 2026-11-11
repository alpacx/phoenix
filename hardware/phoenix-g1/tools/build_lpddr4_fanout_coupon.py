#!/usr/bin/env python3
"""Isolated 65-signal BGA fanout geometry coupon. Not an impedance/routing release."""
import csv,json
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'migration-rk3562/experiments/lpddr4-1gb';OUT=P/'fanout-coupon'
def point(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
def main():
    OUT.mkdir(exist_ok=True);b=pcbnew.BOARD();b.SetCopperLayerCount(6)
    fp=pcbnew.FootprintLoad(str(P/'Phoenix_LPDDR4_Draft.pretty'),'H9HCNNN8KUMLHR_FBGA200_10x15_P0.8x0.65_DRAFT');fp.SetReference('U2');fp.SetPosition(point(10,12));b.Add(fp)
    data=list(csv.DictReader((P/'ball-disposition.csv').open()));signals={r['ram_ball'] for r in csv.DictReader((P/'signal-map.csv').open()) if 'ODT0_CA' not in r['signal']}
    nets={}
    for r in data:
        name=r['net']
        if name and name not in nets:n=pcbnew.NETINFO_ITEM(b,name);b.Add(n);nets[name]=n
    pads={p.GetNumber():p for p in fp.Pads()}
    for r in data:
        if r['net']:pads[r['ball']].SetNet(nets[r['net']])
    # Cell centres form a rectangular 0.8 x 0.65 mm lattice. Matching avoids shared vias.
    choices={}
    for ball in sorted(signals):
        p=pads[ball].GetPosition();x,y=pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)
        options=[(round(x+dx,4),round(y+dy,4)) for dx in [-.4,.4] for dy in [-.325,.325]]
        choices[ball]=sorted(options,key=lambda c:(abs(c[0]-10),abs(c[1]-12)))
    owner={}
    def match(ball,seen):
        for cell in choices[ball]:
            if cell in seen:continue
            seen.add(cell)
            if cell not in owner or match(owner[cell],seen):owner[cell]=ball;return True
        return False
    for ball in sorted(signals):assert match(ball,set()),ball
    for cell,ball in owner.items():
        p=pads[ball];v=pcbnew.PCB_VIA(b);v.SetPosition(point(*cell));v.SetWidth(pcbnew.FromMM(.45));v.SetDrill(pcbnew.FromMM(.2));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(p.GetNet());b.Add(v)
        t=pcbnew.PCB_TRACK(b);t.SetStart(p.GetPosition());t.SetEnd(v.GetPosition());t.SetLayer(pcbnew.F_Cu);t.SetWidth(pcbnew.FromMM(.1));t.SetNet(p.GetNet());b.Add(t)
    for a,z in [((0,0),(20,0)),((20,0),(20,25)),((20,25),(0,25)),((0,25),(0,0))]:
        line=pcbnew.PCB_SHAPE();line.SetShape(pcbnew.SHAPE_T_SEGMENT);line.SetStart(point(*a));line.SetEnd(point(*z));line.SetLayer(pcbnew.Edge_Cuts);line.SetWidth(pcbnew.FromMM(.05));b.Add(line)
    pcbnew.SaveBoard(str(OUT/'fanout.kicad_pcb'),b)
    baseline=json.loads((P/'system/kicad/pcb/phoenix-lpddr4-placement.kicad_pro').read_text())
    rules=baseline['board']['design_settings']['rules'];rules['min_track_width']=.1
    base=baseline['net_settings']['classes'][0];base['clearance']=.1;base['track_width']=.1;base['via_diameter']=.45;base['via_drill']=.2
    (OUT/'fanout.kicad_pro').write_text(json.dumps(baseline,indent=2)+'\n')
    (OUT/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "Phoenix_LPDDR4_Draft") (type "KiCad") (uri "${KIPRJMOD}/../Phoenix_LPDDR4_Draft.pretty") (options "") (descr "Draft")))\n')
    (OUT/'assignment.json').write_text(json.dumps({'status':'ISOLATED_GEOMETRY_EXPERIMENT','signal_count':len(owner),'trace_mm':.1,'clearance_mm':.1,'via_land_drill_mm':[.45,.2],'assignments':[{'ball':ball,'via_xy':cell} for cell,ball in owner.items()],'main_rules_modified':False,'limits':['No CPU fanout','No power/ground fanout or reference planes','No length or impedance qualification','Not integrated PCB copper']},indent=2)+'\n')
    print('65 signal dogbones generated in isolated coupon')
if __name__=='__main__':main()
