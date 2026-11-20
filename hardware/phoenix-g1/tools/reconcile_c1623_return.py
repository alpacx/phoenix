"""Find an off-pad 0.60/0.30 mm ground return on the integrated board."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'reconciled-control.json').read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));pad=b.FindFootprintByReference('C1623').FindPadByNumber('2')
a=pad.GetPosition();via=p.PCB_VIA(b);via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetWidth(600000);via.SetDrill(300000)
t=p.PCB_TRACK(b);t.SetLayer(p.B_Cu);t.SetWidth(300000);t.SetStart(a)
for obj in (via,t):obj.SetNetCode(pad.GetNetCode())
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
pads=[q for f in b.GetFootprints() for q in f.Pads() if q.GetBoundingBox().Inflate(4500000).Contains(a)]
objects=pads+[q for q in b.GetTracks() if q.GetBoundingBox().Inflate(4500000).Contains(a)]
shapes={l:[o.GetEffectiveShape(l) for o in objects if o.IsOnLayer(l) and o.GetNetCode()!=pad.GetNetCode()] for l in layers}
for ix,iy in sorted(((i,j) for i in range(-40,41) for j in range(-40,41)),key=lambda xy:math.hypot(*xy)):
    z=a+p.VECTOR2I(ix*50000,iy*50000);via.SetPosition(z);t.SetEnd(z)
    if any(q.GetBoundingBox().Inflate(351000).Contains(z) for q in pads):continue
    if any(via.GetEffectiveShape(l).Collide(s,200000) for l in layers for s in shapes[l]):continue
    if not any(t.GetEffectiveShape(p.B_Cu).Collide(s,200000) for s in shapes[p.B_Cu]):break
else:raise RuntimeError('No local pad-clear site')
b.Add(t);b.Add(via)
folder=root/'runs/reconciled-c1623';folder.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
assert not delta,delta
saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved)
def get(name):
    ref,n=name.split('.');return saved.FindFootprintByReference(ref).FindPadByNumber(n)
ctrl=json.loads((root.parent/'pmic-ldo-inputs/pcb/final-audit.json').read_text())['checks']
pairs=[(r['from'],r['to']) for r in ctrl]+cp['verified_phy_pairs']
for a,z in pairs:assert get(z).m_Uuid.AsString() in {item.m_Uuid.AsString() for item in saved.GetConnectivity().GetConnectedItems(get(a))},(a,z)
assert not screen(saved)
report=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],site_mm=[p.ToMM(i) for i in via.GetPosition()],verified_pairs=pairs,new_drc=delta,mount_screen=[],preservation=pres,assembly_ready=False)
(root/'reconciled-c1623.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['site_mm'],len(pairs),flush=True);os._exit(0)
