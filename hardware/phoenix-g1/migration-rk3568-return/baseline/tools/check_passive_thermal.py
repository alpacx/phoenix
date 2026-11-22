#!/usr/bin/env python3
"""Lumped enclosure sensitivity study, NOT CFD or measured board dissipation.

Convection coefficient and emissivity are explicit hypothetical parameters.
The model cannot establish a product temperature, thermal certification or
SoC junction temperature. Radiation is to surroundings at ambient temperature.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIGMA = 5.670374419e-8

def rejected_heat(area, h, emissivity, surface_c, ambient_c):
    return area * (h*(surface_c-ambient_c) + emissivity*SIGMA*
                   ((surface_c+273.15)**4-(ambient_c+273.15)**4))

def equilibrium(area, h, emissivity, power, ambient):
    lo, hi = ambient, 250.0
    assert rejected_heat(area,h,emissivity,hi,ambient) >= power
    for _ in range(80):
        mid=(lo+hi)/2
        if rejected_heat(area,h,emissivity,mid,ambient) < power: lo=mid
        else: hi=mid
    return (lo+hi)/2

def main():
    # Reference envelope only; real enclosure must exceed the PCB outline.
    length, width, height = .090, .040, .020
    full_area = 2*(length*width+length*height+width*height)
    metal_area = full_area-length*width
    cases=[]
    for area_name, area in [('base_and_sides_only',metal_area),('all_faces_isothermal',full_area)]:
        for ambient in (25,40):
            for h in (3,8,15):
                for watts in (2,3,5,8):
                    t=equilibrium(area,h,.85,watts,ambient)
                    cases.append({'area_case':area_name,'ambient_c':ambient,
                                  'h_assumed_w_m2k':h,'assumed_dissipation_w':watts,
                                  'surface_equilibrium_c':round(t,2),
                                  'heat_at_55c_surface_w':round(rejected_heat(area,h,.85,55,ambient),3)})
    report={
        'status':'HYPOTHETICAL STEADY-STATE SENSITIVITY; NOT A THERMAL VALIDATION',
        'reference_envelope_mm':[90,40,20],
        'actual_enclosure_dimensions_final':False,
        'base_sides_area_m2':metal_area,'all_faces_area_m2':full_area,
        'assumed_emissivity':.85,
        'surface_screen_c':55,
        'surface_screen_note':'Internal design screening value, not a regulatory or safe-touch limit.',
        'equation':'Q=A*[h*(Ts-Ta)+epsilon*sigma*((Ts+273.15)^4-(Ta+273.15)^4)]',
        'power_note':'2/3/5/8W are hypothetical scenarios, not measured or specified Phoenix consumption.',
        'cases':cases,
        'conclusions':[
            'No fanless near-gigabit VPN performance guarantee is justified by current evidence.',
            'Heat spreading to a small metal enclosure does not by itself ensure an acceptable surface temperature.',
            'Including a display must not interrupt the SoC-to-base thermal path.',
            'If measured losses exceed enclosure capability: revise area/fins, clock/power policy or operating ambient; do not silently reduce throughput requirement.'
        ],
        'not_modelled':['Component junction-to-case paths and local hotspots','Pad pressure, thickness, conductivity and contact resistance',
                       'Enclosure spreading resistance and nonuniform temperature','Desk contact, blocked faces, orientation and nearby objects',
                       'Actual natural-convection coefficient and finish emissivity','Cable/connector heat flow','Transient warmup'],
        'prototype_protocol':[
            'Measure input voltage/current at device for idle, Ethernet forwarding, VPN throughput, Wi-Fi plus VPN and display maximum backlight.',
            'Repeat with closed enclosure at intended maximum ambient and worst supported orientation until thermal equilibrium.',
            'Log SoC thermal sensors, clocks, throttling, packet loss and throughput; measure case/display/PMIC/PHY/Wi-Fi temperatures.',
            'Require component ratings and chosen surface-temperature criterion to be met without loss of required sustained throughput.'
        ]
    }
    (ROOT/'review/passive-thermal-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    for c in cases:
        if c['area_case']=='base_and_sides_only' and c['ambient_c']==40 and c['h_assumed_w_m2k']==8:
            print(c)

if __name__=='__main__': main()
