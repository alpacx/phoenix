#!/usr/bin/env python3
"""Isolated short analog-bias route trial; does not alter the working checkpoint."""
import hashlib,json,shutil,subprocess,tempfile,math
from pathlib import Path
import pcbnew as p
from local_pcb_router import LocalRouter
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text());src=D/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};a,z=pads['U5','39'],pads['R513','1']
assert a.GetNetname()==z.GetNetname()=='PHY_RSET'
r=LocalRouter(b,(56,23,69,35),width=.2,grid=.025)
start=(60.0,32.4);path=r.solve(r.blocked(p.F_Cu,'PHY_RSET'),r.cell(start),r.cell(r.xy(z)))
result={'source_sha256':cp['sha256'],'checkpoint_modified':False,'assembly_ready':False,'limits':['Geometric routing only: analog noise coupling and return path remain to be qualified.'],'width_mm':.2,'extent_mm':list(r.extent),'start_mm':start}
if not path:
 result['status']='NO_FRONT_PATH_IN_BOUNDED_MODEL';result['next_constraint']='Review R513 placement jointly with crystal and switch-node geometry; do not force a long analog-bias detour.'
else:
 pts=[r.xy(a),start]+path+[r.xy(z)];result['path_mm']=pts;result['length_mm']=sum(math.dist(x,y) for x,y in zip(pts,pts[1:]))
 for x,y in zip(pts,pts[1:]):
  v=lambda q:p.VECTOR2I(*(p.FromMM(c) for c in q))
  if v(x)==v(y):continue
  t=p.PCB_TRACK(b);t.SetStart(v(x));t.SetEnd(v(y));t.SetWidth(p.FromMM(.2));t.SetLayer(p.F_Cu);t.SetNetCode(a.GetNetCode());b.Add(t)
 outdir=Path(tempfile.mkdtemp(prefix='phoenix-rset-pin-'));out=outdir/src.name
 for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
 (outdir/'fp-lib-table').write_text((src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent)))
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);b.BuildConnectivity()
 drc=outdir/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads(drc.read_text()));connected=z.m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(a)}
 result.update(status='RSET_GEOMETRY_PASSED' if not new and connected else 'RSET_GEOMETRY_REJECTED',temporary_candidate=str(out),candidate_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),connected=connected,new_violations=new,preservation=verify_preservation(p.LoadBoard(str(src)),b))
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
(D/'pcb/phy-rset-pin-probe.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
