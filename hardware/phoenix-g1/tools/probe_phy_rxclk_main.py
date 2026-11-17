#!/usr/bin/env python3
"""Test RXCLK strap integration on authoritative component choices, in isolation."""
import json,hashlib,tempfile,shutil,sys,os,subprocess
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
if '--audit' in sys.argv:
 m=json.loads(Path(sys.argv[-1]).read_text());src=Path(m['source']);out=Path(m['candidate']);drc=out.parent/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 raw=json.loads(drc.read_text());new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),raw);ids={i for r in new for i in r['items']};m.update(new_violations=new,details=[r for r in raw['violations'] if any(i['uuid'] in ids for i in r['items'])],status='RXCLK_MAIN_REJECTED',assembly_ready=False)
 if not new:
  original=p.LoadBoard(str(src));candidate=p.LoadBoard(str(out));m['preservation']=verify_preservation(original,candidate,replaced_copper=m['route']['replaced_copper']);key=lambda r:(r['reservation'],r['ref']);m['mechanical_conflicts']=sorted({key(r) for r in screen(candidate)}-{key(r) for r in screen(original)})
  if not m['mechanical_conflicts']:m['status']='RXCLK_MAIN_GEOMETRY_PASSED'
 (D/'pcb/phy-rxclk-main-probe.json').write_text(json.dumps(m,indent=2)+'\n');print(m['status'],flush=True);os._exit(0)
cp=json.loads((D/'working-candidate.json').read_text());src=D/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src))
from phy_rxclk_strap_route import add_rxclk_strap_route
route,held=add_rxclk_strap_route(b)
outdir=Path(tempfile.mkdtemp(prefix='phoenix-rxclk-main-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
(outdir/'fp-lib-table').write_text((src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent)));filler=p.ZONE_FILLER(b);filler.Fill(b.Zones());p.SaveBoard(str(out),b)
m={'source':str(src),'candidate':str(out),'source_sha256':cp['sha256'],'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'route':route,'checkpoint_modified':False,'limitations':['Short bias branch only. PHY-to-MAC path, impedance and timing remain open. No component or width change.']}
mp=outdir/'input.json';mp.write_text(json.dumps(m));os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),'--audit',str(mp)])
