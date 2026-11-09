import pcbnew,json,math
from pathlib import Path
r=Path(__file__).resolve().parents[1]/'migration-rk3562'
p=r/'kicad/Phoenix_RK3562_Candidates.pretty'
name='RK3562_FCCSP478_13.9mm_MIXED_PITCH_CANDIDATE'
f=pcbnew.FootprintLoad(str(p),name)
assert f is not None
pads={p.GetNumber():(pcbnew.ToMM(p.GetPosition().x),pcbnew.ToMM(p.GetPosition().y)) for p in f.Pads()}
expected=json.loads((r/'review/package-candidate.json').read_text())['pads']
assert set(pads)=={p['ball'] for p in expected}
assert max(math.dist(pads[p['ball']],(p['x_mm'],p['y_mm'])) for p in expected)<.00001
b=pcbnew.BOARD();b.Add(f);pcbnew.SaveBoard('/tmp/phoenix-rk3562-footprint-roundtrip.kicad_pcb',b)
b2=pcbnew.LoadBoard('/tmp/phoenix-rk3562-footprint-roundtrip.kicad_pcb')
assert sum(len(list(fp.Pads())) for fp in b2.GetFootprints())==478
report={'status':'PASS KICAD LOAD/SAVE AND GENERATOR TRANSCRIPTION ONLY','pads':478,'independent_package_coordinate_audit':False,'manufacturing_qualified':False,'geometry_screen':{'outer_pitch_mm':.5,'candidate_land_mm':.25,'candidate_via_land_drill_mm':[.25,.15],'center_via_clearance_mm':round(.5/math.sqrt(2)-.25,6),'required_bga_clearance_mm':.09,'trace_between_adjacent_lands_margin_mm':round(.5-.25-.0762-2*.09,6),'finding':'Cell-center small via clears nominal geometry. A 3mil trace between adjacent 0.25mm lands does NOT meet 0.09mm pad-to-trace clearance. No completed escape or routing implied.'},'production_ready':False}
(r/'review/footprint-cad-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
