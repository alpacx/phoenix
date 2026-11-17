#!/usr/bin/env python3
"""Restore the old 5V trunk on a copy and require DRC to detect its XIN-via short."""
import hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
import pcbnew as p
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text());source=D/cp['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(source))
def vec(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
via=next(t for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='PHY_XIN' and t.GetPosition()==vec(59.875,31))
track=p.PCB_TRACK(b);track.SetStart(vec(60.5,24.5));track.SetEnd(vec(60.5,32.95))
track.SetWidth(p.FromMM(.8));track.SetLayer(p.In2_Cu);track.SetNetCode(b.GetNetcodeFromNetname('+5V_MAIN'));b.Add(track)
expected={track.m_Uuid.AsString(),via.m_Uuid.AsString()}
with tempfile.TemporaryDirectory(prefix='phoenix-clock-fault-') as work:
 out=Path(work)/'fault.kicad_pcb';p.SaveBoard(str(out),b)
 for suffix in ['.kicad_pro','.kicad_dru']:shutil.copy2(source.with_suffix(suffix),out.with_suffix(suffix))
 (out.parent/'fp-lib-table').write_text((source.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(source.parent.resolve())))
 report=out.with_suffix('.json')
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(report),str(out)],check=True,capture_output=True)
 violations=json.loads(report.read_text())['violations']
 assert any(v['type']=='shorting_items' and expected<={q['uuid'] for q in v['items']} for v in violations),'Expected XIN/5V short was not detected'
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
print('PASS: restoring the old 5V trunk creates the expected XIN-via short; checkpoint unchanged.')
