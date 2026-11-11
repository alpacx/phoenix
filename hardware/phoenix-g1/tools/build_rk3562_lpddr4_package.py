#!/usr/bin/env python3
"""Generate candidate 200-ball disposition and draft footprint; not production land pattern."""
import csv,json,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'migration-rk3562/experiments/lpddr4-1gb'
# Independent full-row transcription from Hynix Rev1.1 p6, top view.
TABLE='''A DNU DNU VSS VDD2 ZQ0 NC VDD2 VSS DNU DNU
B DNU DQ0_A VDDQ DQ7_A VDDQ VDDQ DQ15_A VDDQ DQ8_A DNU
C VSS DQ1_A DMI0_A DQ6_A VSS VSS DQ14_A DMI1_A DQ9_A VSS
D VDDQ VSS DQS0P_A VSS VDDQ VDDQ VSS DQS1P_A VSS VDDQ
E VSS DQ2_A DQS0N_A DQ5_A VSS VSS DQ13_A DQS1N_A DQ10_A VSS
F VDD1 DQ3_A VDDQ DQ4_A VDD2 VDD2 DQ12_A VDDQ DQ11_A VDD1
G VSS ODT0_CA_A VSS VDD1 VSS VSS VDD1 VSS NC VSS
H VDD2 A0_A NC CS0N_A VDD2 VDD2 A2_A A3_A A4_A VDD2
J VSS A1_A VSS CKE0_A NC CLKP_A CLKN_A VSS A5_A VSS
K VDD2 VSS VDD2 VSS NC NC VSS VDD2 VSS VDD2
N VDD2 VSS VDD2 VSS NC NC VSS VDD2 VSS VDD2
P VSS A1_B VSS CKE0_B NC CLKP_B CLKN_B VSS A5_B VSS
R VDD2 A0_B NC CS0N_B VDD2 VDD2 A2_B A3_B A4_B VDD2
T VSS ODT0_CA_B VSS VDD1 VSS VSS VDD1 VSS RESETN VSS
U VDD1 DQ3_B VDDQ DQ4_B VDD2 VDD2 DQ12_B VDDQ DQ11_B VDD1
V VSS DQ2_B DQS0N_B DQ5_B VSS VSS DQ13_B DQS1N_B DQ10_B VSS
W VDDQ VSS DQS0P_B VSS VDDQ VDDQ VSS DQS1P_B VSS VDDQ
Y VSS DQ1_B DMI0_B DQ6_B VSS VSS DQ14_B DMI1_B DQ9_B VSS
AA DNU DQ0_B VDDQ DQ7_B VDDQ VDDQ DQ15_B VDDQ DQ8_B DNU
AB DNU DNU VSS VDD2 VSS VSS VDD2 VSS DNU DNU'''
def main():
    rows='A B C D E F G H J K L M N P R T U V W Y AA AB'.split()
    cols=[1,2,3,4,5,8,9,10,11,12]
    nets={'VSS':'GND','VDD1':'+1V8_LPDDR4','VDD2':'+1V1_LPDDR4','VDDQ':'+1V1_LPDDR4','ZQ0':'LPDDR4_ZQ_240R','NC':None,'DNU':None}
    balls=[]
    for line in TABLE.splitlines():
        row,*names=line.split();assert len(names)==10
        for col,name in zip(cols,names):
            signal='LPDDR4_'+name.replace('DMI','DM')
            balls.append(dict(ball=row+str(col),name=name,net=nets[name] if name in nets else signal,x_mm=round((col-6.5)*.8,4),y_mm=round((rows.index(row)-10.5)*.65,4)))
    assert len(balls)==200 and len({b['ball'] for b in balls})==200
    byball={b['ball']:b for b in balls}
    mapped=list(csv.DictReader((OUT/'signal-map.csv').open()))
    for m in mapped:assert byball[m['ram_ball']]['net']==m['signal'],m
    with (OUT/'ball-disposition.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(balls[0]));w.writeheader();w.writerows(balls)
    name='H9HCNNN8KUMLHR_FBGA200_10x15_P0.8x0.65_DRAFT'
    fp=[f'(footprint "{name}" (version 20241229) (generator "pcbnew") (layer "F.Cu") (attr smd)', '(descr "DRAFT: Hynix Rev1.1 p6/7. Pad diameter 0.30 mm is provisional; assembly approval pending.")', '(fp_text reference "REF**" (at 0 -8.5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))','(fp_text value "H9HCNNN8KUMLHR-NME" (at 0 8.5) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))', '(fp_rect (start -5 -7.5) (end 5 7.5) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))', '(fp_rect (start -5.3 -7.8) (end 5.3 7.8) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))','(fp_line (start -5 -6.5) (end -4 -7.5) (stroke (width 0.15) (type default)) (layer "F.Fab"))']
    for b in balls:fp.append(f'(pad "{b["ball"]}" smd circle (at {b["x_mm"]} {b["y_mm"]}) (size 0.3 0.3) (layers "F.Cu" "F.Paste" "F.Mask"))')
    fp.append(')');folder=OUT/'Phoenix_LPDDR4_Draft.pretty';folder.mkdir(exist_ok=True)
    (folder/(name+'.kicad_mod')).write_text('\n'.join(fp)+'\n')
    report={'status':'DRAFT_GEOMETRY_NOT_ASSEMBLY_QUALIFIED','ball_count':len(balls),'signal_crosscheck':len(mapped),'groups':dict(collections.Counter(b['name'] for b in balls if b['name'] in nets)),'visual_source_review':'p6 rendered top-view inspected; p7 dimensions extracted','pad_diameter_mm':.3,'pad_diameter_status':'provisional, not manufacturer recommended PCB land','physical_tests':False}
    (OUT/'package-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
