#!/usr/bin/env python3
"""Audit a bounded bus reroute without relaxing the shared copper invariant."""
import json, hashlib, os
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
ROOT=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments'
D=ROOT/'pmic-buck5/pcb'
source=ROOT/'emmc-system/pcb/emmc-ground.kicad_pcb'
stage=os.environ.get('PHOENIX_BUCK5_AUDIT_STAGE','bus-clearance');target=D/(stage+'.kicad_pcb')
a=p.LoadBoard(str(source));b=p.LoadBoard(str(target))
# Normalize only the two explicitly reviewed endpoint edits in the comparison
# board. Physical connectivity is checked against the untouched source below.
expected={
'a1f5a5ec-cc41-45b8-86e2-782cf1776594':('end',(62.5,4.55),(62.5,2)),
'b6a2a81c-14ba-4bdf-ba31-f95e78785298':('start',(62.5,4.55),(63.7,4.55)),
}
tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
original={t.m_Uuid.AsString():t for t in a.GetTracks()}
for uid,(end,old,new) in expected.items():
 t=tracks[uid];o=original[uid]
 get=lambda x:x.GetEnd() if end=='end' else x.GetStart()
 xy=lambda v:tuple(round(p.ToMM(k),6) for k in (v.x,v.y))
 assert xy(get(o))==old and xy(get(t))==new,(uid,xy(get(o)),xy(get(t)))
 assert t.GetNetname()==o.GetNetname() and t.GetLayer()==o.GetLayer() and t.GetWidth()==o.GetWidth()
 (t.SetEnd if end=='end' else t.SetStart)(get(o))
# The optional SWOUT1 rework has an exact, fixed removal list. No other
# original copper may disappear; all original pad groups are checked below.
removed=[]
if os.environ.get('PHOENIX_BUCK5_IO_REWORK')=='1':
 allowed={'c56f9a86-4ded-4de3-ae32-4a3b6131078e','bc7687d7-f582-4e4a-ad03-c15395e31e54','3821fc34-7a67-4339-a7f4-be5a7eb84bca','4482cdb6-bf26-4b24-966f-71b01a80dc3b'}
 assert not (allowed & tracks.keys()),'Old IO copper unexpectedly still present'
 for t in list(a.GetTracks()):
  if t.m_Uuid.AsString() in allowed:a.Remove(t);removed.append(t)
 assert len(removed)==4
# Strict geometry invariant after restoring precisely those endpoints.
geometry=verify_preservation(a,b)
# Re-load actual board: none of the normalized geometry participates in this check.
a=p.LoadBoard(str(source));b=p.LoadBoard(str(target));a.BuildConnectivity();b.BuildConnectivity()
pads=lambda board:{q.m_Uuid.AsString():q for f in board.GetFootprints() for q in f.Pads()}
oldpads,newpads=pads(a),pads(b);seen=set();groups=0
for uid,pad in oldpads.items():
 if uid in seen:continue
 group=({q.m_Uuid.AsString() for q in a.GetConnectivity().GetConnectedItems(pad)}|{uid}) & oldpads.keys();seen|=group
 if len(group)<2:continue
 connected={q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(newpads[uid])}|{uid}
 assert group<=connected,('Broken original connectivity',uid,sorted(group-connected))
 groups+=1
def reserves(board):
 return {z.GetZoneName():(z.GetBoundingBox().GetX(),z.GetBoundingBox().GetY(),z.GetBoundingBox().GetWidth(),z.GetBoundingBox().GetHeight(),z.GetDoNotAllowTracks(),z.GetDoNotAllowVias()) for z in board.Zones() if z.GetIsRuleArea()}
assert reserves(a)==reserves(b),'Mechanical rule areas changed'
new=introduced(json.loads((ROOT/'emmc-system/pcb/emmc-ground-drc.json').read_text()),json.loads((D/(stage+'-drc.json')).read_text()))
assert not new,new
report={'status':'PRESERVATION_AND_BUS_CONNECTIVITY_CHECKED','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'geometry_after_exact_endpoint_normalization':geometry,'intentional_endpoint_changes':list(expected),'explicitly_replaced_io_primitives':[t.m_Uuid.AsString() for t in removed],'actual_original_connected_groups_preserved':groups,'mechanical_rule_areas_preserved':len(reserves(a)),'new_drc_violations':new,'power_qualification_complete':False,'assembly_ready':False}
(D/(stage+'-preservation-audit.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
