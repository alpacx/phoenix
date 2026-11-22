"""Reroute one display PWM segment while reserving an ordinary eMMC H5 escape."""
import hashlib,json,subprocess,shutil,math
from pathlib import Path
import pcbnew as p
import sys
from pcb_bounds import inflated_box
from pcb_power_leg import make,barrel
from phy_corridor_path import geometry
from drc_regression import introduced
from pcb_preservation import verify_preservation
tools=Path(__file__).resolve().parent;r=tools.parent/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((r/'layout-recovery-adc-relocated.json').read_text());src=r/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));source=b.FindFootprintByReference('U8001').FindPadByNumber('H5')
old=next(t for t in b.GetTracks() if t.m_Uuid.AsString()=='cac73c71-c298-4d9b-99c9-37b934261b25')
uid=old.m_Uuid.AsString();start=tuple(old.GetStart());end=tuple(old.GetEnd());b.Remove(old)
seed=(36325000,8750000)
refine='--refine' in sys.argv
ddr='--shift-ca' in sys.argv
changed=[uid]
if ddr:
    clock=next(t for t in b.GetTracks() if t.m_Uuid.AsString()=='50054298-022f-48b8-8d86-fb9b1fd39f74')
    a,z=tuple(clock.GetStart()),tuple(clock.GetEnd());length=math.dist(a,z);dx,dy=(z[0]-a[0])/length,(z[1]-a[1])/length
    s=(seed[0]-a[0])*dx+(seed[1]-a[1])*dy
    cx,cy=a[0]+s*dx,a[1]+s*dy
    normal=(cx-seed[0],cy-seed[1]);norm=math.hypot(*normal);nx,ny=normal[0]/norm,normal[1]/norm
    at=lambda along,offset: (round(cx+along*dx+offset*nx),round(cy+along*dy+offset*ny))
    pts=[a,at(-600000,0),at(-200000,65000),at(200000,65000),at(600000,0),z]
    assert 600000<s<length-600000
    b.Remove(clock);changed.append(clock.m_Uuid.AsString())
    for u,v in zip(pts,pts[1:]):b.Add(make(b,u,v,clock.GetWidth(),clock.GetNetCode(),clock.GetLayer()))
    ca_extra=sum(math.dist(x,y) for x,y in zip(pts,pts[1:]))-length

if refine:
    local=inflated_box(source,1350000)
    objs=[o for o in [*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())] if local.Intersects(o.GetBoundingBox())]
    layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
    lands=[(o.GetBoundingBox(),o.GetEffectiveShape(o.GetParentFootprint().GetLayer())) for o in objs if isinstance(o,p.PAD)]
    foreign=[(o.GetBoundingBox(),o.GetEffectiveShape(l),l) for o in objs for l in layers if o.GetNetCode()!=source.GetNetCode() and o.IsOnLayer(l)]
    holes=[(o.GetBoundingBox(),o.GetEffectiveHoleShape()) for o in objs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    candidates=[]
    for dx in range(-300000,300001,5000):
     for dy in range(-300000,300001,5000):
        pos=(seed[0]+dx,seed[1]+dy);v=barrel(b,pos,source.GetNetCode());bb=inflated_box(v,300000);sh=v.GetEffectiveShape(p.F_Cu);hole=v.GetEffectiveHoleShape()
        if any(bb.Intersects(box) and sh.Collide(g,100000) for box,g in lands) or any(bb.Intersects(box) and sh.Collide(g,252000) for box,g in holes) or any(bb.Intersects(box) and (sh.Collide(g,202000) or hole.Collide(g,252000)) for box,g,l in foreign):continue
        line=make(b,tuple(source.GetPosition()),pos,200000,source.GetNetCode(),p.B_Cu);bs=inflated_box(line,300000);ls=line.GetEffectiveShape(p.B_Cu)
        if any(l==p.B_Cu and bs.Intersects(box) and ls.Collide(g,202000) for box,g,l in foreign) or any(bs.Intersects(box) and ls.Collide(g,252000) for box,g in holes):continue
        candidates.append((math.dist(pos,seed),pos))
    if not candidates:
        (r/'emmc-strobe-pwm-refined.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],tested=121**2,sites=0,includes_hole_clearance_mm=.252),indent=2)+'\n');print('no refined point');sys.exit()
    ground=(37150000,9200000)
    print('via options',len(candidates),'closest reference mm',min(math.dist(pos,ground) for _,pos in candidates)/1e6)
    seed=min(candidates,key=lambda item:(math.dist(item[1],ground),item[0]))[1]
via=barrel(b,seed,source.GetNetCode());b.Add(via)
b.Add(make(b,tuple(source.GetPosition()),seed,200000,source.GetNetCode(),p.B_Cu))
geo=geometry(b,p.F_Cu,old.GetNetCode(),oval_caps=True)
req=dict(geometry=geo,sites=[start],target=[end],width=old.GetWidth(),limit=13000000)
proc=subprocess.run(['python3',str(tools/'screen_cpu_launch_corridor.py')],input=json.dumps(req),text=True,capture_output=True,check=True);result=json.loads(proc.stdout)
row=dict(parent_sha256=cp['sha256'],old_pwm_endpoints_nm=[start,end],pwm_path=result['path'],remaining_gap=result['closest'])
if result['path']:
    for a,z in zip(result['path'],result['path'][1:]):b.Add(make(b,a,z,old.GetWidth(),old.GetNetCode(),p.F_Cu))
    out=r/('runs/strobe-ca-pwm' if ddr else 'runs/strobe-pwm-refined' if refine else 'runs/strobe-pwm-restored');out.mkdir(exist_ok=True,parents=True);file=out/src.name
    for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
    shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table');p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(file)],check=True,capture_output=True)
    db=json.loads((out/'drc.json').read_text());after=p.LoadBoard(str(file));after.BuildConnectivity()
    row.update(board=str(file.relative_to(r)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),new_drc=introduced(json.loads((src.parent/'drc.json').read_text()),db),remaining=len(db['unconnected_items']),preservation=verify_preservation(p.LoadBoard(str(src)),after,replaced_copper=changed))
if ddr:row['ca1_extra_mm']=ca_extra/1e6
(r/('emmc-strobe-ca-pwm.json' if ddr else 'emmc-strobe-pwm-refined.json' if refine else 'emmc-strobe-pwm-relief.json')).write_text(json.dumps(row,indent=2)+'\n');print(len(result['path']),row.get('remaining'),row.get('new_drc'))
