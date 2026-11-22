"""Reposition supplied resistors around the existing via while clearing H8105."""
from pathlib import Path
import hashlib,json,math,os,subprocess,shutil
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
last='--remaining' in sys.argv
cp=json.loads((root/('strap-clearance-verified.json' if last else 'phy-fixture-checkpoint.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
original=p.LoadBoard(str(src));current=src;rows=[];replaced=[]
def conflict(board):return {(r['reservation'],r['ref']) for r in screen(board)}
for ref,target_ref,target_no in ([('R526','R507','2')] if last else [('R525','R508','2'),('R527','U5','32')]):
    b=p.LoadBoard(str(current));f=b.FindFootprintByReference(ref);target=b.FindFootprintByReference(target_ref).FindPadByNumber(target_no)
    anchor=p.VECTOR2I(73000000,32400000);one,two=(f.FindPadByNumber(n) for n in ('1','2'))
    feeders=[t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetLayer()==p.F_Cu and t.GetStart()==anchor and t.GetEnd()==two.GetPosition()]
    assert len(feeders)==(0 if last else 1)
    changed=[t.m_Uuid.AsString() for t in feeders]
    for t in feeders:b.Remove(t)
    options=[]
    for l in [p.F_Cu,p.B_Cu]:
        if f.GetLayer()!=l:f.Flip(f.GetPosition(),False)
        fps=[g for g in b.GetFootprints() if g.GetReference()!=ref]
        boxes=[g.GetCourtyard(l).BBox() for g in fps if g.GetLayer()==l and g.GetCourtyard(l).BBox().Inflate(7000000).Contains(anchor)]
        obs=[(o.GetNetCode(),o.GetEffectiveShape(l)) for o in list(b.GetTracks())+[q for g in fps for q in g.Pads()] if o.IsOnLayer(l) and o.GetBoundingBox().Inflate(7000000).Contains(anchor)]
        for angle in (0,90,180,270):
            f.SetOrientationDegrees(angle)
            for dx in range(-25,16):
                for dy in range(-24,16):
                    pos=anchor+p.VECTOR2I(dx*200000,dy*200000);f.SetPosition(pos)
                    if any(f.GetCourtyard(l).BBox().Intersects(z) for z in boxes):continue
                    t=p.PCB_TRACK(b);t.SetLayer(l);t.SetWidth(200000);t.SetNetCode(two.GetNetCode());t.SetStart(anchor);t.SetEnd(two.GetPosition())
                    if any(o.GetEffectiveShape(l).Collide(shape,200000) for o in (one,two,t) for n,shape in obs if n!=o.GetNetCode()):continue
                    if t.GetEffectiveShape(l).Collide(one.GetEffectiveShape(l),200000):continue
                    score=math.dist(tuple(one.GetPosition()),tuple(target.GetPosition()))+.3*t.GetLength()
                    options.append((score,l,angle,tuple(pos)))
    held=list(feeders);tested=0
    for _,l,angle,pos in sorted(options):
        if f.GetLayer()!=l:f.Flip(f.GetPosition(),False)
        f.SetOrientationDegrees(angle);f.SetPosition(p.VECTOR2I(*pos))
        if any(k[1]==ref for k in conflict(b)):continue
        tested+=1
        if tested>16:break
        t=p.PCB_TRACK(b);t.SetLayer(l);t.SetWidth(200000);t.SetNetCode(two.GetNetCode());t.SetStart(anchor);t.SetEnd(two.GetPosition());b.Add(t)
        folder=root/'runs'/('strap-clearance-'+ref);folder.mkdir(exist_ok=True)
        for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
        out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
        delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
        if not delta:
            saved=p.LoadBoard(str(out));pres=verify_preservation(original,saved,replaced_copper=replaced+changed)
            q=saved.FindFootprintByReference(ref).FindPadByNumber('2')
            assert saved.FindFootprintByReference('C515').FindPadByNumber('1').m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(q)}
            replaced.extend(changed);current=out;rows.append(dict(ref=ref,layer=b.GetLayerName(l),center_mm=[p.ToMM(i) for i in pos],preservation=pres));break
        b.Remove(t);held.append(t)
    print(ref,len(options),tested,current.parent.name,flush=True)
after=p.LoadBoard(str(current))
report=dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),records=rows,resolved=sorted(conflict(original)-conflict(after)),remaining=sorted(conflict(after)),assembly_ready=False)
(root/('strap-remaining-verified.json' if last else 'strap-clearance-verified.json')).write_text(json.dumps(report,indent=2)+'\n')
os._exit(0)
