#!/usr/bin/env python3
"""Replace long C515 ground escape with a wider front-side return to C1001 GND."""
import json,hashlib,tempfile,shutil,sys,os,subprocess,math
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
S=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-compact-inductor'
if '--audit' in sys.argv:
 m=json.loads(Path(sys.argv[-1]).read_text());src=Path(m['source']);out=Path(m['candidate']);drc=out.parent/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 raw=json.loads(drc.read_text());new=introduced(json.loads((src.parent/'drc.json').read_text()),raw);ids={i for r in new for i in r['items']};m.update(new_violations=new,details=[r for r in raw['violations'] if any(i['uuid'] in ids for i in r['items'])],status='BULK_RETURN_REJECTED',assembly_ready=False)
 if not new:
  original=p.LoadBoard(str(src));candidate=p.LoadBoard(str(out));m['preservation']=verify_preservation(original,candidate,replaced_copper=m['removed']);m['status']='BULK_RETURN_GEOMETRY_PASSED'
 (S/'bulk-return-probe.json').write_text(json.dumps(m,indent=2)+'\n');print(m['status'],flush=True);os._exit(0)
proof=json.loads((S/'input-corridor-bypass.json').read_text());assert proof['status']=='CORRIDOR_BYPASS_GEOMETRY_PASSED';src=Path(proof['candidate']);assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['candidate_sha256']
ground=json.loads((S.parent/'pmic-ldo-inputs/pcb/phy-compact-0603-ground-probe.json').read_text())['capacitors']['C515'];b=p.LoadBoard(str(src));vec=lambda q:p.VECTOR2I(*(p.FromMM(c) for c in q));edges={(tuple(vec(a)),tuple(vec(z))) for a,z in zip(ground['path_mm'],ground['path_mm'][1:]) if vec(a)!=vec(z)};removed=[];held=[]
for t in list(b.GetTracks()):
 if t.GetNetname()!='GND':continue
 match=isinstance(t,p.PCB_VIA) and t.GetPosition()==vec(ground['via_mm'])
 if not isinstance(t,p.PCB_VIA):match=(tuple(t.GetStart()),tuple(t.GetEnd())) in edges and t.GetLayer()==p.F_Cu
 if match:removed.append(t.m_Uuid.AsString());b.Remove(t);held.append(t)
assert len(removed)==len(edges)+1,(len(removed),len(edges))
path=[(63.525,24.2),(63.525,23.3),(64.5,22.325),(64.5,22)];tracks=[]
for a,z in zip(path,path[1:]):
 t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(.5));t.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(t);tracks.append(t)
from pcb_route_guards import require_constant_width_branch
require_constant_width_branch(tracks,net='GND',layer=p.F_Cu,width_mm=.5,start_mm=path[0],end_mm=path[-1])
outdir=Path(tempfile.mkdtemp(prefix='phoenix-bulk-return-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',outdir/'fp-lib-table');filler=p.ZONE_FILLER(b);filler.Fill(b.Zones());p.SaveBoard(str(out),b)
m={'source':str(src),'candidate':str(out),'parent_sha256':proof['candidate_sha256'],'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'removed':removed,'new_ground_path_mm':path,'width_mm':.5,'old_width_mm':.2,'old_length_mm':sum(math.dist(a,z) for a,z in zip(ground['path_mm'],ground['path_mm'][1:])),'length_mm':sum(math.dist(a,z) for a,z in zip(path,path[1:])),'limitations':['Geometric return improvement only. Shared-ground noise, loop inductance and plane currents are not qualified.','No reduction of original copper widths; regulator switching node remains open.']}
mp=outdir/'input.json';mp.write_text(json.dumps(m));os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),'--audit',str(mp)])
