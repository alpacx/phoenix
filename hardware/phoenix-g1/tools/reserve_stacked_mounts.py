#!/usr/bin/env python3
"""Mechanical overlay: explicit M2 reservations, never fabrication drill data."""
import json,hashlib,math
from pathlib import Path
import pcbnew as p
R=Path(__file__).resolve().parents[1];O=R/'migration-rk3562/experiments/stacked-expansion';D=O/'mechanical';D.mkdir(exist_ok=True)
src=O/'pcb/candidate.kicad_pcb';b=p.LoadBoard(str(src));sites=[('H8101',53,4),('H8102',83,3),('H8103',21,3),('H8104',37,31),('H8105',70,34)]
def vec(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def intersects(box,x,y):return math.hypot(max(p.ToMM(box.GetX())-x,0,x-p.ToMM(box.GetRight())),max(p.ToMM(box.GetY())-y,0,y-p.ToMM(box.GetBottom())))<2.7
rows=[]
for ref,x,y in sites:
 blockers=[]
 for f in b.GetFootprints():
  shapes=list(f.Pads())+[s for s in f.GraphicalItems() if s.GetLayer() in [p.F_CrtYd,p.B_CrtYd]]
  if any(intersects(s.GetBoundingBox(),x,y) for s in shapes):blockers.append(f.GetReference())
 tracks=[t for t in b.GetTracks() if intersects(t.GetBoundingBox(),x,y)]
 for radius in [1.1,2.7]:
  s=p.PCB_SHAPE();s.SetShape(p.SHAPE_T_CIRCLE);s.SetCenter(vec(x,y));s.SetEnd(vec(x+radius,y));s.SetWidth(p.FromMM(.15));s.SetLayer(p.Dwgs_User);b.Add(s)
 t=p.PCB_TEXT(b);t.SetText(ref+' M2 RESERVE');t.SetPosition(vec(x, y+4));t.SetTextSize(vec(.8,.8));t.SetTextThickness(p.FromMM(.12));t.SetLayer(p.Dwgs_User);b.Add(t)
 rows.append({'ref':ref,'center_mm':[x,y],'proposed_NPTH_diameter_mm':2.2,'reserved_diameter_mm':5.4,'sides':'both, including screw head and spacer','role':'daughterboard' if ref in ['H8101','H8102'] else 'auxiliary bracket or enclosure','position_provisional':True,'blocking_components':sorted(blockers),'existing_track_or_via_conflicts':len(tracks),'actual_drill_created':False})
p.SaveBoard(str(D/'mounting-reservations.kicad_pcb'),b)
report={'status':'MANDATORY_MECHANICAL_RESERVATION_NOT_CLEARED','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'pcb_outline_mm':[90,40],'target_mm':[85,35],'mounts':rows[:2],'auxiliary_mounts':rows[2:],'cooling_strategy':'Passive preferred; auxiliary mounts do not imply fan or fan power circuitry','auxiliary_usage':'Custom brackets for enclosure/heatsink/optional fan; no standard fan hole pattern claimed','fastener':'M2 candidate, insulating spacer preferred','board_gap_mm':3.5,'board_gap_applies_only_to':'H8101/H8102 daughterboard mounts','spacer_tolerance_and_screw_length_qualified':False,'orientation_key':'Hole pattern offset from J3; verify mating and enclosure prevents wrong orientation','release_blockers':['Relocate listed components before creating NPTHs','Enforce both-side component and all-layer copper clearance','Qualify spacer OD, height tolerance and screw length against actual DF40 mating height','Mirror common mounting coordinates on daughterboard and qualify outline above RJ45 and passive cooling','Revalidate positions after 85x35 compaction'],'assembly_ready':False}
(D/'mounting-interface.json').write_text(json.dumps(report,indent=2)+'\n');assert all(r['existing_track_or_via_conflicts']==0 for r in rows);print(json.dumps(report))
