#!/usr/bin/env python3
"""Joint clock detour / analog bias escape on the compact experimental PCB only."""
import hashlib,json,shutil,subprocess,tempfile,math,os,sys
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
S=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-compact-inductor'
if len(sys.argv)>1 and sys.argv[1]=='--audit':
 meta=json.loads(Path(sys.argv[2]).read_text());src=Path(meta['source']);out=Path(meta['candidate']);drc=out.parent/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 raw=json.loads(drc.read_text());new=introduced(json.loads((src.parent/'phy-compact-output-drc.json').read_text()),raw)
 ids={i for row in new for i in row['items']};details=[row for row in raw['violations'] if any(i['uuid'] in ids for i in row['items'])]
 proof={'status':'NOT_RUN_REJECTED_DRC'}
 if not new:
  original=p.LoadBoard(str(src));candidate=p.LoadBoard(str(out));proof=verify_preservation(original,candidate,replaced_copper=meta['removed'])
 meta.update(status='CLOCK_RSET_ESCAPE_GEOMETRY_PASSED' if not new else 'CLOCK_RSET_ESCAPE_REJECTED',new_violations=new,details=details,preservation=proof,assembly_ready=False,limitations=['Bias resistor remains disconnected. No oscillator or analog noise qualification. Experimental parent and main checkpoint unchanged.'])
 (S/meta['report']).write_text(json.dumps(meta,indent=2)+'\n')
 assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['parent_sha256']
 print(meta['status'],flush=True);os._exit(0)
cp=json.loads((S/'study-checkpoint.json').read_text());src=S/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['candidate_sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
removed=[];old_length=0
for t in list(b.GetTracks()):
 if t.GetNetname()!='PHY_XOUT' or isinstance(t,p.PCB_VIA):continue
 coords=[p.ToMM(v) for v in (t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y)]
 if min(coords[0],coords[2])>=57.825 and max(coords[1],coords[3])<=33.025 and p.ToMM(t.GetWidth())==.2:
  removed.append(t.m_Uuid.AsString());old_length+=math.dist(coords[:2],coords[2:]);b.Remove(t)
assert removed
vec=lambda q:p.VECTOR2I(*(p.FromMM(c) for c in q))
def route(points,net,width):
 for a,z in zip(points,points[1:]):
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(width));t.SetNetCode(net);b.Add(t)
shifted='--shifted' in sys.argv
bias_x=59.5 if shifted else 59.9
clock=[(59.9,31.6),(59.4,31.6),(58.8,32.2),(58.8,33.025),(57.825,33.025)] if shifted else [(59.9,31.6),(58.475,33.025),(57.825,33.025)]
route(clock,pads['U5','37'].GetNetCode(),.2)
route([(60.6,32.4),(bias_x,32.4)],pads['U5','39'].GetNetCode(),.2)
v=p.PCB_VIA(b);v.SetPosition(vec((bias_x,32.4)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(pads['U5','39'].GetNetCode());b.Add(v)
outdir=Path(tempfile.mkdtemp(prefix='phoenix-clock-rset-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
(outdir/'fp-lib-table').write_text((src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent)))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);b.BuildConnectivity()
meta={'report':'clock-rset-shifted-probe.json' if shifted else 'clock-rset-escape-probe.json','source':str(src),'candidate':str(out),'parent_sha256':cp['candidate_sha256'],'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'removed':removed,'clock_path_mm':clock,'old_clock_replaced_length_mm':old_length,'new_clock_length_mm':sum(math.dist(a,z) for a,z in zip(clock,clock[1:])),'bias_via_mm':[bias_x,32.4,.45,.2]}
metafile=outdir/'probe-input.json';metafile.write_text(json.dumps(meta,indent=2)+'\n')
os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),'--audit',str(metafile)])
