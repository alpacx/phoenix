#!/usr/bin/env python3
"""Explicit 1.55 mm, no-via PHY output branch on the isolated compact variant."""
import hashlib,json,math,shutil,subprocess,tempfile
from pathlib import Path
import pcbnew as p
from pcb_route_guards import require_constant_width_branch
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
from phy_study_source import load_source
cp,root=load_source(D)
proof=json.loads((D/'pcb/phy-compact-0603-ground-probe.json').read_text())
assert proof['status']=='COMPACT_GROUNDS_GEOMETRY_PASSED' and proof['reserved_output_corridor']
src=Path(proof['temporary_candidate']);assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['candidate_sha256']
assert hashlib.sha256(root.read_bytes()).hexdigest()==proof['source_sha256']==cp['sha256']
b=p.LoadBoard(str(src));old=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
xy=lambda q:(p.ToMM(q.GetPosition().x),p.ToMM(q.GetPosition().y))
start,end=xy(pads['L501','2']),xy(pads['C511','1']);assert pads['L501','2'].GetNetname()==pads['C511','1'].GetNetname()=='+1V0_PHY'
path=[start,(end[0],start[1]+abs(start[0]-end[0])),end];tracks=[]
for a,z in zip(path,path[1:]):
 t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(*(p.FromMM(v) for v in a)));t.SetEnd(p.VECTOR2I(*(p.FromMM(v) for v in z)));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(1.55));t.SetNetCode(pads['L501','2'].GetNetCode());b.Add(t);tracks.append(t)
guard=require_constant_width_branch(tracks,net='+1V0_PHY',layer=p.F_Cu,width_mm=1.55,start_mm=start,end_mm=end)
from phy_reset_pin_route import add_reset_pin_route
reset_route=add_reset_pin_route(b)
outdir=Path(tempfile.mkdtemp(prefix='phoenix-compact-output-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',outdir/'fp-lib-table');p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);b.BuildConnectivity()
drc=outdir/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
new=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(drc.read_text()))
connected=pads['C511','1'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['L501','2'])}
key=lambda r:(r['reservation'],r['ref']);mechanical=sorted({key(r) for r in screen(b)}-{key(r) for r in screen(old)})
preservation=verify_preservation(old,b)
root_preservation=verify_preservation(p.LoadBoard(str(root)),b,replaced_copper=list(proof['preservation']['explicitly_replaced_copper']))
result={'status':'COMPACT_OUTPUT_GEOMETRY_PASSED' if not new and connected and not mechanical else 'COMPACT_OUTPUT_REJECTED','source_sha256':cp['sha256'],'parent_sha256':proof['candidate_sha256'],'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'temporary_candidate':str(out),'path_mm':path,'length_mm':sum(math.dist(a,z) for a,z in zip(path,path[1:])),'width_guard':guard,'reset_route':reset_route,'connected':connected,'new_violations':new,'mechanical_conflicts':mechanical,'preservation':preservation,'root_preservation':root_preservation,'checkpoint_modified':False,'assembly_ready':False,'limitations':['Only L501.2 to C511.1 output branch: regulator switch node, input supply and load distribution remain open.','1.55 mm exceeds the historical rev1.1 width screen; current layout guide, copper stackup, ripple, effective capacitance and thermal validation remain required.','Alternative BOM is experimental, not adopted or production qualified.']}
assert hashlib.sha256(root.read_bytes()).hexdigest()==cp['sha256']
(D/'pcb/phy-compact-output-probe.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
