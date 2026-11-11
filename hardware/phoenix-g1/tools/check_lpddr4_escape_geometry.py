#!/usr/bin/env python3
"""Local arithmetic screen only; not a routing or impedance qualification."""
from pathlib import Path
import json,math
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'migration-rk3562/experiments/lpddr4-1gb'
def main():
    px,py,land,via,drill=.8,.65,.3,.45,.2
    gap=py-land;diag=math.hypot(px/2,py/2)-(land+via)/2
    report={'status':'LOCAL_GEOMETRY_SCREEN_NOT_ROUTING','land_diameter_mm':land,'land_status':'provisional manufacturing review pending','pitch_xy_mm':[px,py],'minimum_pad_gap_mm':gap,'via_land_drill_mm':[via,drill],'cell_center_via_to_ball_clearance_mm':diag,'default_0p2_trace_0p2_clearance':{'required_gap_mm':.2+2*.2,'fits':gap>=.6},'candidate_0p1_trace_0p1_clearance':{'required_gap_mm':.1+2*.1,'margin_mm':gap-.3,'fits':gap>=.3,'cell_center_via_clearance_fits':diag>=.1},'drill_aspect_nominal':1.6/drill,'source':'https://jlcpcb.com/capabilities/pcb-capabilities/','source_checked_date':'2026-11-10','manufacturer_multilayer_minimum_trace_spacing_mm':[.09,.09],'scope':'A single channel and via cell. Does not prove all pads can escape simultaneously, include adjacent traces/vias or return-plane continuity.','holds':['Final NSMD land/mask/stencil review','Local DDR rule and layer stackup definition','CPU FCCSP escape','Complete fanout and routing','Impedance solver and length/skew budget','Thermal and physical tests'],'global_project_rules_changed':False}
    (P/'system/review/escape-geometry.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
