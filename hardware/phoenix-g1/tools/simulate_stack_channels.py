"""Contrast exterior and interior quasi-TEM channels on two six-layer 1.6-mm stackups."""
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.constants import c
from simulate_outer_pair_impedance import capacitance,check_parallel_plates,partition,solve_pair,triangles

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
inventory=json.loads((root/'highspeed-copper-inventory.json').read_text())
stacks={
    'JLC06161H-3313':dict(outer_h=.0994,outer_er=4.1,core_h=.55,core_er=4.6,middle_h=.1088,middle_er=4.16),
    'JLC06161H-7628':dict(outer_h=.2104,outer_er=4.4,core_h=.4,core_er=4.6,middle_h=.2028,middle_er=4.4),
}
close_reference="--close-reference" in sys.argv
if close_reference:
    stacks={
        "JLC06161H-2116A":dict(outer_h=.1164,outer_er=4.16,core_h=.13,core_er=4.6,middle_h=.9328,middle_er=4.16,center_core=.7),
        "JLC06161H-3313E":dict(outer_h=.0994,outer_er=4.1,core_h=.10,core_er=4.6,middle_h=1.1208,middle_er=4.4,center_core=.7),
    }
thickness=.0152


def stripline(width,gap,stack,step=.012,extent=1.6,neighbor=False,single=False):
    # L3 and L4 are routed signal layers. L2/L5 are the reference planes.
    # The model is invariant to reflection through the stack midplane.
    core=stack['core_h'];pp=stack['middle_h'];height=2*core+pp+2*thickness
    lower=core;upper=lower+thickness+pp
    left=0 if single else gap/2;right=width/2 if single else left+width
    xs=partition(([0,right,extent] if single else [0,left,right,extent]),step)
    central=stack.get("center_core",0)
    central_low=lower+thickness+(pp-central)/2
    central_high=central_low+central
    boundaries=[0,lower,lower+thickness,upper,upper+thickness,height]
    if central:boundaries.extend([central_low,central_high])
    ys=partition(sorted(boundaries),step)
    x,y=np.meshgrid(xs,ys);xy=np.stack((x.ravel(),y.ravel()),axis=1);tri=triangles(len(xs),len(ys))
    strip=(x>=left-1e-12)&(x<=right+1e-12)
    signal=strip&(y>=lower-1e-12)&(y<=lower+thickness+1e-12)
    ground=(y==0)|(y==height)|(x==extent)|((x==0)&(not single))
    if neighbor:ground|=strip&(y>=upper-1e-12)&(y<=upper+thickness+1e-12)
    cy=xy[tri].mean(axis=1)[:,1]
    dielectric=np.where((cy>lower)&(cy<upper+thickness),stack['middle_er'],stack['core_er'])
    if central:dielectric=np.where((cy>central_low)&(cy<central_high),stack['core_er'],dielectric)
    cd=capacitance(xy,tri,dielectric,ground.ravel(),signal.ravel())
    c0=capacitance(xy,tri,np.ones(len(tri)),ground.ravel(),signal.ravel())
    ohms=(.5 if single else 2)/(c*math.sqrt(cd*c0))
    return dict(mode='single' if single else 'odd differential',width_mm=width,gap_mm=None if single else gap,
                mesh_max_mm=step,wall_mm=extent,opposite_layer_aligned_grounded_track=neighbor,
                effective_er=cd/c0,ohms=ohms)


def exterior(s,w,g,single):
    v=solve_pair(w,g,substrate_mm=s['outer_h'],substrate_er=s['outer_er'],single=single)
    return dict(width_mm=w,gap_mm=None if single else g,mode='single' if single else 'odd differential',
                effective_er=v['effective_er'],ohms=v['single_ended_ohms' if single else 'differential_ohms'])


result={}
for name,s in stacks.items():
    outside=[];inside=[]
    for w in (.0762,.1,.2,.24,.3):
        outside.append(exterior(s,w,.25,True));inside.append(stripline(w,.25,s,single=True))
    for w,g in [( .0762,.0762),(.1,.1),(.2,.20),(.2,.25),(.24,.25),(.30,.25),(.34,.25)]:
        outside.append(exterior(s,w,g,False));inside.append(stripline(w,g,s))
    opposite=[stripline(.2,.25,s,neighbor=True),stripline(.2,.25,s,neighbor=True,single=True)]
    mre=stripline(.2,.25,s,step=.006,extent=2.0)
    cm=next(v for v in inside if v['width_mm']==.2 and v['gap_mm']==.25)
    assert abs(mre['ohms']-cm['ohms'])<2.0
    result[name]=dict(assumptions=s,outside=outside,inner=inside,aligned_opposite_track=opposite,inner_refinement=mre)
homogeneous=stripline(.2,.25,dict(next(iter(stacks.values())),core_er=3.5,middle_er=3.5))
assert abs(homogeneous['effective_er']-3.5)<1e-8
report=dict(source_sha256=inventory['source_sha256'],stacks=result,parallel_plates=check_parallel_plates(),
            homogeneous_internal_er=homogeneous['effective_er'],applied_to_board=False,
            sources=['https://jlcpcb.com/impedance','https://jlcpcb.com/help/article/user-guide-to-the-jlcpcb-impedance-calculator'],
            interpretation=[
              'Outer signal L1/L6 above nearest reference L2/L5; continuous plane, external solder mask and trapezoid.',
              'Inner signal L3/L4 between reference L2 and L5. L3/L4 adjacent signal layers, not reference planes. Absent intervening copper modeled as prepreg. Internal copper nominal rectangular 15.2 um.',
              'Aligned opposite track case holds a trace of equal width at zero potential on the adjacent signal layer. It screens sensitivity; it is neither a switching aggressor model nor worst-case crosstalk.',
              '7628 substrate Dk 4.4 assumed; 3313 candidate materials per project. No RK3562-specific LPDDR4 impedance or timing limits supplied. Existing package escape widths are reported as geometric sensitivity, not routed as controlled lines in the model.',
              'USB target used for screening only: 90 ohms differential. Every PCB data lane in inventory is still open. Pads, vias, antipads, copper fill near connector, loss and three-dimensional discontinuities omitted.'])
if close_reference:
    report['source_sha256']=json.loads((root/'layout-command-ca1.json').read_text())['sha256']
    report['interpretation'][1]='L3/L4 reference L2/L5 respectively. The central 0.70 mm dielectric core is modeled between two prepreg plies. PCB thickness class 1.6 mm, copper according to the JLCPCB public stack diagram.'
    report['interpretation'][3]='Dk assumptions: core 4.6, 2116 4.16, 3313 4.1 and 7628 4.4. Supplier-specific frequency, resin-content and lot tolerances remain open. The published construction does not qualify Phoenix impedances.'
(root/('jlc-close-reference-stack-simulation.json' if close_reference else 'usb-ddr-stack-simulation.json')).write_text(json.dumps(report,indent=2)+'\n')
for name,r in result.items():
    print(name,[(v['width_mm'],v['gap_mm'],round(v['ohms'],1)) for v in r['inner']])
