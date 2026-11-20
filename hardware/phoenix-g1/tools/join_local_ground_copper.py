"""Join isolated decoupler and crystal-case grounds to verified nearby surface copper."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
source=json.loads((root/'corner-escape.json').read_text())
src=root/source['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==source['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
def pad(board,ref,num):return board.FindFootprintByReference(ref).FindPadByNumber(num)
anchor=pad(b,'C511','2')
def grounded(board):
    return {i.m_Uuid.AsString() for i in board.GetConnectivity().GetConnectedItems(pad(board,'C511','2'))}
known=grounded(b)
objects=[q for f in b.GetFootprints() for q in f.Pads()]+list(b.GetTracks())
touched=[]
def closest(start,target):
    if isinstance(target,p.PCB_TRACK):
        x,y=target.GetStart();u,v=target.GetEnd()
        dx,dy=u-x,v-y;den=dx*dx+dy*dy
        weight=max(0,min(1,((start.x-x)*dx+(start.y-y)*dy)/den)) if den else 0
        return p.VECTOR2I(round(x+weight*dx),round(y+weight*dy))
    return target.GetPosition()
for f in sorted(b.GetFootprints(),key=lambda f:f.GetReference()):
    if not f.GetReference().startswith(('C','Y')):continue
    layer=f.GetLayer()
    for q in f.Pads():
        if q.GetNetname()!='GND' or q.m_Uuid.AsString() in known:continue
        origin=q.GetPosition();near=[item for item in objects if item.IsOnLayer(layer) and item.GetBoundingBox().Inflate(1800000).Contains(origin)]
        targets=[i for i in near if i.m_Uuid.AsString() in known]
        obstacles=[i.GetEffectiveShape(layer) for i in near if i.GetNetCode()!=q.GetNetCode()]
        options=[]
        for dx in (-150000,0,150000):
            for dy in (-150000,0,150000):
                start=origin+p.VECTOR2I(dx,dy)
                if not q.HitTest(start):continue
                for other in targets:
                    end=closest(start,other);distance=math.dist(tuple(start),tuple(end))
                    if 0<distance<=1200000:options.append((distance,tuple(start),tuple(end)))
        for length,start,end in sorted(set(options)):
            t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(*start));t.SetEnd(p.VECTOR2I(*end));t.SetWidth(300000);t.SetLayer(layer);t.SetNetCode(q.GetNetCode())
            if any(t.GetEffectiveShape(layer).Collide(shape,200000) for shape in obstacles):continue
            b.Add(t);touched.append(dict(ref=f.GetReference(),pad=q.GetNumber(),length_mm=length/1e6));break
folder=root/'runs/surface-ground';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
assert not delta,delta
saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved);assert not screen(saved)
ground=grounded(saved)
for row in touched:assert pad(saved,row['ref'],row['pad']).m_Uuid.AsString() in ground,row
if not touched:out=src
(root/'surface-ground.json').write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),added=touched,preservation=pres,assembly_ready=False),indent=2)+'\n')
print(touched,flush=True);os._exit(0)
