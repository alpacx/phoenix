#!/usr/bin/env python3
"""Fanless sizing sensitivity; not CFD, not a temperature guarantee."""
import json
from pathlib import Path
from check_passive_thermal import rejected_heat, equilibrium
ROOT=Path(__file__).resolve().parents[1]

def main():
    # Proposed outer envelope for study only, larger than the90x40 PCB.
    l,w,h=.100,.046,.024
    panel=.0135*.02795 # complete display body, conservative exclusion from top metal
    sides=2*h*(l+w)
    areas={'all_faces_minus_display':2*l*w+sides-panel,
           'bottom_blocked_minus_display':l*w+sides-panel}
    cases=[]
    for name,area in areas.items():
        for ambient in [25,40]:
            for convection in [3,8]:
                for epsilon in [.1,.85]:
                    capacity=rejected_heat(area,convection,epsilon,55,ambient)
                    cases.append(dict(exposure=name,ambient_c=ambient,h_w_m2k=convection,
                        emissivity=epsilon,heat_at_55c_w=round(capacity,3),
                        surface_at_5w_c=round(equilibrium(area,convection,epsilon,5,ambient),2),
                        effective_area_required_for_5w_at_55c_m2=round(5/rejected_heat(1,convection,epsilon,55,ambient),5)))
    pads=[]
    # Effective contact areas and final compressed thicknesses are hypotheses.
    # Bulk-only R excludes both contact resistances: this is optimistic, not an upper bound.
    for side_mm in [15,20]:
        for thickness_mm in [.5,1,2]:
            resistance=thickness_mm/1000/(3*(side_mm/1000)**2)
            pads.append(dict(contact_square_mm=side_mm,compressed_thickness_mm=thickness_mm,
                bulk_only_r_k_per_w=round(resistance,3),bulk_only_drop_at_3w_k=round(3*resistance,3)))
    out=dict(status='SIZING SENSITIVITY ONLY; NOT RELEASE QUALIFICATION',fan_allowed=False,
        proposed_outer_envelope_mm=[100,46,24],envelope_final=False,pcb_mm=[90,40],
        display_body_exclusion_mm=[13.5,27.95],surface_screen_c=55,
        power_basis='5W whole-product heat and3W processor heat are hypothetical independent examples; no measured Phoenix power.',
        area_m2=areas,enclosure_cases=cases,tim_cases=pads,
        tim_reference={'source':'https://datasheets.tdx.henkel.com/BERGQUIST-GAP-PAD-TGP-3000-en_GL.pdf',
            'document':'Henkel BERGQUIST GAP PAD TGP3000 April2021',
            'conductivity_w_mk':3,'selection':'REFERENCE MATERIAL ONLY; no procurement MPN or JLC availability confirmed'},
        constraints=[
            'No fan, blower or assumed forced convection.',
            'Metal lid/spreader contacts SoC through insulating compliant TIM; mechanically supported independently of LCD.',
            'Display must not cover SoC contact zone. Flex bend radius and support clearance must be established from panel supplier.',
            'Do not rely on coating color alone to establish emissivity; low-emissivity case included.',
            'No specified TIM compression/force until Rockchip package allowable load and tolerance stack are known.',
            'No ribs/fins area credit without checking airflow spacing, orientation and fin efficiency.',
            'No mechanical dimension or mounting-clearance validation follows from this thermal model.'
        ],
        excluded=['spreading/contact resistance','component-to-case paths','thermal coupling into LCD',
                  'local hot spots','real convection/emissivity','actual power and enclosure measurements'])
    (ROOT/'review/thermal-path-sizing.json').write_text(json.dumps(out,indent=2)+'\n')
    for case in cases:
        if case['exposure']=='bottom_blocked_minus_display' and case['ambient_c']==40 and case['h_w_m2k']==8:print(case)
if __name__=='__main__': main()
