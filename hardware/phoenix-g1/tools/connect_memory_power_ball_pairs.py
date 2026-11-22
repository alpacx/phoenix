"""Connect distinct nearby LPDDR4 supply-ball islands at the layout's 0.50-mm package-bank width."""
from pathlib import Path
import hashlib,json,math,shutil,subprocess
from collections import Counter
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced
import sys
part=next((arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--part=')),'U2')
assert part in ('U1','U2','U8001')
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((r/('layout-ground-copper-contact.json' if part!='U2' else 'layout-npu-local-bypass.json')).read_text());src=r/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();fp=b.FindFootprintByReference(part);objs=[*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())];side=fp.GetLayer()
def pad(board,label):
 a,z=label.split('.');return board.FindFootprintByReference(a).FindPadByNumber(z)
def points(q):
    x,y=q.GetPosition();return [(x+i,y+j) for i in (-75000,0,75000) for j in (-75000,0,75000) if q.HitTest(p.VECTOR2I(x+i,y+j))]
rows=[];added=[]
for net,groups in cp['open_nets'].items():
    if net=='GND' or not net.startswith(('+','VCC','VDD','EMMC_IO_1V8','EMMC_3V3','VDDA')):continue
    balls={n:i for i,g in enumerate(groups) for n in g if n.startswith(part+'.')}
    if not balls:continue
    code=b.FindNet(net).GetNetCode();roots=list(range(len(groups)))
    def root(i):
        while i!=roots[i]:i=roots[i]
        return i
    cases=sorted((math.dist(tuple(pad(b,a).GetPosition()),tuple(pad(b,z).GetPosition())),a,z) for a in balls for z in balls if a<z and balls[a]!=balls[z])
    for distance,a,z in cases:
        if distance>1800000:break
        if root(balls[a])==root(balls[z]):continue
        q=pad(b,a);dest=pad(b,z);bb=inflated_box(q,2400000);near=[o for o in objs if o.GetNetCode()!=code and bb.Intersects(o.GetBoundingBox())]
        fo=[o.GetEffectiveShape(side) for o in near if o.IsOnLayer(side)];holes=[o.GetEffectiveHoleShape() for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
        allowed=False
        for _,x,y in sorted((math.dist(x,y),x,y) for x in points(q) for y in points(dest)):
            dx=y[0]-x[0];dy=y[1]-x[1];di=min(abs(dx),abs(dy));vx=int(math.copysign(di,dx));vy=int(math.copysign(di,dy))
            for m in (x,(x[0]+vx,x[1]+vy),(y[0]-vx,y[1]-vy)):
                ps=[x]+([m] if m not in (x,y) else [])+[y];ts=[make(b,u,v,500000,code,side) for u,v in zip(ps,ps[1:])]
                if any(any(t.GetEffectiveShape(side).Collide(o,202000) for o in fo) or any(t.GetEffectiveShape(side).Collide(h,252000) for h in holes) for t in ts):continue
                for t in ts:b.Add(t);objs.append(t)
                added.append(dict(net=net,pads=[a,z],path=ps))
                roots[root(balls[a])]=root(balls[z]) 
                allowed=True;break
            if allowed:break
        rows.append((net,a,z,allowed))
report=dict(parent_sha256=cp['sha256'],width_mm=.5,tries=rows,added=added)
if added:
    out=r/('runs/physical-power-pairs-'+part if part!='U2' else 'runs/memory-power-pair-banks');out.mkdir(exist_ok=True,parents=True);file=out/src.name
    for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
    shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table');p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(file)],capture_output=True,check=True)
    db=json.loads((out/'drc.json').read_text());diff=introduced(json.loads((src.parent/'drc.json').read_text()),db);saved=p.LoadBoard(str(file));saved.BuildConnectivity()
    report.update(board=str(file.relative_to(r)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),remaining=len(db['unconnected_items']),new_drc=diff,preservation=verify_preservation(p.LoadBoard(str(src)),saved))
(r/('physical-power-pairs-'+part+'.json' if part!='U2' else 'memory-power-pair-banks.json')).write_text(json.dumps(report,indent=2)+'\n');print(len(rows),len(added),report.get('remaining'),report.get('new_drc'))
