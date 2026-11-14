#!/usr/bin/env python3
"""Move accessory power feed away from J3 signal fanout; experimental geometry."""
import pcbnew as p,json,math,hashlib,shutil,subprocess,collections
from pathlib import Path
from local_pcb_router import LocalRouter
R=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/stacked-expansion';D=R/'pcb';cp=json.loads((R/'working-candidate.json').read_text());src=R/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));old=[];removed_objects=[];footprints=list(b.GetFootprints())
for t in list(b.GetTracks()):
 if not isinstance(t,p.PCB_VIA) and t.GetNetname()=='+5V_ADDON' and t.GetLayer()==p.In3_Cu:old.append(t.m_Uuid.AsString());removed_objects.append(t);b.Remove(t)
assert old
r=LocalRouter(b,(58,.5,84,15),width=1,grid=.1);r.max_expansions=300000;blocked=r.blocked(p.In2_Cu,'+5V_ADDON')
# Reserve actual signal escape space plus half power-track width and clearance.
for x in range(661,727):
 for y in range(13,38):blocked.add((x,y))
a=(75.3,7.7);z=(62.5,2);path=r.solve(blocked,r.cell(a),r.cell(z))
if not path:
 report={'status':'NO_PATH_WITH_FIXED_ENDPOINTS_NOT_PROMOTED','source_sha256':cp['sha256'],'attempted_layer':'In2.Cu','width_mm':1,'start_blocked':r.cell(a) in blocked,'end_blocked':r.cell(z) in blocked,'board_saved':False,'assembly_ready':False};(D/'power-corridor.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));raise SystemExit(0)
code=b.FindNet('+5V_ADDON').GetNetCode()
for a,z in zip(path,path[1:]):
 t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(p.FromMM(a[0]),p.FromMM(a[1])));t.SetEnd(p.VECTOR2I(p.FromMM(z[0]),p.FromMM(z[1])));t.SetWidth(p.FromMM(1));t.SetLayer(p.In2_Cu);t.SetNetCode(code);b.Add(t)
p.ZONE_FILLER(b).Fill(b.Zones());dest=D/'power-corridor.kicad_pcb';p.SaveBoard(str(dest),b)
for ext in ['kicad_dru','kicad_pro']:shutil.copy2(src.with_suffix('.'+ext),dest.with_suffix('.'+ext))
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'power-corridor-drc.json'),str(dest)],check=True,capture_output=True)
count=lambda path:collections.Counter(v['type'] for v in json.loads(path.read_text())['violations']);new=count(D/'power-corridor-drc.json')-count(D/'aux-io-drc.json');report={'status':'CANDIDATE_REQUIRES_CONTINUITY_AUDIT','source_sha256':cp['sha256'],'removed_addon_feed_segments':len(old),'new_segments':len(path)-1,'new_DRC_counts':dict(new),'power_track_width_mm':1,'feed_length_mm':sum(math.dist(a,z) for a,z in zip(path,path[1:])),'reserved_signal_region_mm':[66.8,2,71.9,3],'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'current_and_thermal_qualified':False,'assembly_ready':False};(D/'power-corridor.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));assert not new
