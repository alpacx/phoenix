#!/usr/bin/env python3
"""Joint C517/RX termination move on compact study; never promotes main PCB."""
import json,hashlib,tempfile,shutil,sys,os,subprocess,math
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
S=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-compact-inductor'
if '--audit' in sys.argv:
 m=json.loads(Path(sys.argv[-1]).read_text());src=Path(m['source']);out=Path(m['candidate']);drc=out.parent/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 raw=json.loads(drc.read_text());new=introduced(json.loads((src.parent/'phy-compact-output-drc.json').read_text()),raw);ids={i for r in new for i in r['items']}
 m.update(new_violations=new,details=[r for r in raw['violations'] if any(i['uuid'] in ids for i in r['items'])],status='PLACEMENT_ONLY_NOT_ROUTED',assembly_ready=False)
 (S/m['report']).write_text(json.dumps(m,indent=2)+'\n');print(json.dumps({'violations':len(new),'status':m['status']}),flush=True);os._exit(0)
cp=json.loads((S/'study-checkpoint.json').read_text());src=S/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['candidate_sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()};v=lambda q:p.VECTOR2I(*(p.FromMM(c) for c in q))
input_mode='--input-corridor' in sys.argv
for ref in (['R511','R507','R512'] if input_mode else ['R511','R507']):
 f=fs[ref];assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()),ref
 f.Flip(f.GetPosition(),False)
f=fs['C517'];f.SetPosition(v((62.2,27.0) if input_mode else (62.5,27.0)));f.SetOrientationDegrees(0 if input_mode else 90)
if '--search-r511' in sys.argv or input_mode:
 from local_pcb_router import LocalRouter
 f=fs['R511'];r=LocalRouter(b,(58,23,65,30),width=.2,grid=.025)
 r.pads=[q for q in r.pads if q.GetParentFootprint().GetReference()!='R511']
 blocked={q.GetNumber():r.blocked(p.B_Cu,q.GetNetname(),math.hypot(p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y))) for q in f.Pads()}
 boxes=[g.GetCourtyard(p.B_Cu).BBox() for g in b.GetFootprints() if g.GetLayer()==p.B_Cu and g.GetReference()!='R511']
 choices=sorted([(x/4,y/4) for x in range(232,261) for y in range(92,121)],key=lambda q:math.dist(q,(60.5,27)))
 found=False
 for xy in choices:
  if math.dist(xy,(60.5,27))>3:continue
  for angle in [0,90]:
   f.SetPosition(v(xy));f.SetOrientationDegrees(angle)
   if any(f.GetCourtyard(p.B_Cu).BBox().Intersects(q) for q in boxes):continue
   if any(r.cell(r.xy(q)) in blocked[q.GetNumber()] for q in f.Pads()):continue
   found=True;break
  if found:break
 assert found,'No R511 placement in bounded search'

if input_mode:
 from local_pcb_router import LocalRouter
 f=fs['R512'];r=LocalRouter(b,(58,23,69,33),width=.2,grid=.025)
 r.pads=[q for q in r.pads if q.GetParentFootprint().GetReference()!='R512']
 blocked={q.GetNumber():r.blocked(p.B_Cu,q.GetNetname(),math.hypot(p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y))) for q in f.Pads()}
 boxes=[g.GetCourtyard(p.B_Cu).BBox() for g in b.GetFootprints() if g.GetLayer()==p.B_Cu and g.GetReference()!='R512']
 choices=sorted([(x/4,y/4) for x in range(232,277) for y in range(92,133)],key=lambda q:math.dist(q,(61.5,25.5)))
 found=False
 for xy in choices:
  if math.dist(xy,(61.5,25.5))>6:continue
  for angle in [0,90]:
   f.SetPosition(v(xy));f.SetOrientationDegrees(angle)
   if any(f.GetCourtyard(p.B_Cu).BBox().Intersects(q) for q in boxes):continue
   if any(r.cell(r.xy(q)) in blocked[q.GetNumber()] for q in f.Pads()):continue
   found=True;break
  if found:break
 assert found,'No R512 placement in bounded search'

outdir=Path(tempfile.mkdtemp(prefix='phoenix-switch-corridor-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
(outdir/'fp-lib-table').write_text((src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent)))
p.SaveBoard(str(out),b)
m={'report':'input-corridor-placement.json' if input_mode else ('switch-corridor-placement-searched.json' if '--search-r511' in sys.argv else 'switch-corridor-placement.json'),'source':str(src),'candidate':str(out),'parent_sha256':cp['candidate_sha256'],'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'moves':{ref:[p.ToMM(fs[ref].GetPosition().x),p.ToMM(fs[ref].GetPosition().y),fs[ref].GetOrientationDegrees(),'F' if fs[ref].GetLayer()==p.F_Cu else 'B'] for ref in (['C517','R511','R507','R512'] if input_mode else ['C517','R511','R507'])},'limitations':['C517 former ground and bypass branches still require restoration.','RX terminations have no existing copper; new layer requires future SI/fanout validation.','No switch-node or primary power trace added; electrical constraints unchanged.']}
mp=outdir/'input.json';mp.write_text(json.dumps(m));os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),'--audit',str(mp)])
