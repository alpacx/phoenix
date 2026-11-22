"""Reorient C511 about its live output land, retaining two independent ground barrels."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
filled='--filled-return' in sys.argv
mesh='--angled-mesh' in sys.argv
stage='phy-output-angled-mesh' if mesh else 'phy-output-capped-return' if filled else 'phy-output-cap-clearance'
cp=json.loads((root/('layout-core-ground-mesh.json' if mesh else 'layout-phy-full-feed.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));base=p.LoadBoard(str(src))
old={'2dc3ec34-d094-40ea-b2d6-1a5844f48bde','5cf46293-2b35-48a2-a200-d02be838d5e5','6958a641-cfc7-432a-8c48-4cfc10832957','a1aae4bb-416a-41dc-9cda-34227592146e','2a575363-a3e0-4044-bfce-896f6e5d1d64','d1b713af-53ef-4312-9433-e83b035b00e5'}
cut=[t for t in b.GetTracks() if t.m_Uuid.AsString() in old]
assert len(cut)==len(old) and all(t.GetNetname()=='GND' for t in cut)
for t in cut:b.Remove(t)
cap=b.FindFootprintByReference('C511');rail,gnd=[cap.FindPadByNumber(n) for n in ('1','2')]
fixed=rail.GetPosition();other=[f for f in b.GetFootprints() if f.GetReference()!='C511']
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
near=lambda t:t.GetBoundingBox().Inflate(6500000).Contains(fixed)
pads=[q for f in other for q in f.Pads() if near(q)];traces=[t for t in b.GetTracks() if near(t)]
courts=[f.GetCourtyard(p.F_Cu).BBox() for f in other if f.GetLayer()==p.F_Cu and near(f)]
obs={l:[(k.GetNetCode(),k.GetEffectiveShape(l)) for k in pads+traces if k.IsOnLayer(l)] for l in layers}
zones=[z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
def free(t,l):
 shape=t.GetEffectiveShape(l)
 return all(n==t.GetNetCode() or not shape.Collide(o,200000) for n,o in obs[l])
def barrel(site):
 v=p.PCB_VIA(b);v.SetWidth(450000);v.SetDrill(200000);v.SetNetCode(gnd.GetNetCode());v.SetPosition(site);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu)
 if filled:v.SetFillingMode(p.FILLING_MODE_FILLED);v.SetCappingMode(p.CAPPING_MODE_CAPPED)
 return v
def trace(site):
 t=p.PCB_TRACK(b);t.SetWidth(500000);t.SetLayer(p.F_Cu);t.SetNetCode(gnd.GetNetCode());t.SetStart(gnd.GetPosition());t.SetEnd(site);return t
def load_pose(angle,shift):
 cap.SetOrientationDegrees(angle);cap.Move(fixed+p.VECTOR2I(*shift)-rail.GetPosition())
options=[];fits=[];target=p.VECTOR2I(59300000,32300000)
for angle in (range(0,360,10) if mesh else (0,90,180,270)):
 for x in range(-4,5):
  for y in range(-4,5):
   shift=(x*100000,y*100000);load_pose(angle,shift);box=cap.GetCourtyard(p.F_Cu).BBox()
   if not rail.HitTest(fixed) or (any(cap.GetCourtyard(p.F_Cu).Collide(f.GetCourtyard(p.F_Cu),0) for f in other if f.GetLayer()==p.F_Cu and near(f)) if mesh else any(box.Intersects(c) for c in courts)) or not all(free(q,p.F_Cu) for q in (rail,gnd)):continue
   distance=math.hypot(max(box.GetLeft()-target.x,0,target.x-box.GetRight()),max(box.GetTop()-target.y,0,target.y-box.GetBottom()))
   if distance<600000:continue
   fits.append((angle,shift));land=[]
   for dx in range(-11,12):
    for dy in range(-11,12):
     site=gnd.GetPosition()+p.VECTOR2I(dx*100000,dy*100000);v=barrel(site);t=trace(site)
     if t.GetLength()>1100000 or not free(t,p.F_Cu) or t.GetEffectiveShape(p.F_Cu).Collide(rail.GetEffectiveShape(p.F_Cu),200000):continue
     if filled and any(not gnd.HitTest(site+p.VECTOR2I(round(250000*math.cos(i*math.pi/32)),round(250000*math.sin(i*math.pi/32)))) for i in range(64)):continue
     if any(q.GetBoundingBox().Inflate(276000).Contains(site) for q in pads+([rail] if filled else [rail,gnd])):continue
     if any(isinstance(k,p.PCB_VIA) and math.dist(tuple(k.GetPosition()),tuple(site))<650000 for k in traces):continue
     if not all(free(v,l) for l in layers) or any(z.Outline().Collide(v.GetEffectiveShape(p.F_Cu),0) for z in zones):continue
     land.append((t.GetLength(),tuple(site)))
   for i,(d,a) in enumerate(land):
    for e,z in land[i+1:]:
     if math.dist(a,z)>=650000 and min(math.dist(tuple(target),pt) for pt in (a,z))>=900000:options.append((max(d,e),-distance,angle,shift,a,z))
folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
for n in ('fp-lib-table','phy-joint.kicad_dru','phy-joint.kicad_pro'):shutil.copy2(src.parent/n,folder/n)
rec=None;attempts=0
for _,_,angle,shift,a,z in sorted(options):
 load_pose(angle,shift)
 if screen(b):continue
 items=[k for pt in (a,z) for k in (trace(p.VECTOR2I(*pt)),barrel(p.VECTOR2I(*pt)))]
 if filled:items=[k for k in items if isinstance(k,p.PCB_VIA)]
 for k in items:b.Add(k)
 out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));attempts+=1
 if not delta:
    saved=p.LoadBoard(str(out));pres=verify_preservation(base,saved,replaced_copper=old);assert not screen(saved)
    rec=dict(center_nm=tuple(cap.GetPosition()),angle=angle,rail_shift_nm=shift,ground_vias_nm=[a,z],preservation=pres);break
 for k in items:b.Remove(k)
 if attempts>=12:break
if not rec:out=src
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],poses=fits,paired_returns=len(options),attempts=attempts,change=rec,assembly_ready=False),indent=2)+'\n')
print(len(fits),len(options),attempts,bool(rec),flush=True);os._exit(0)
