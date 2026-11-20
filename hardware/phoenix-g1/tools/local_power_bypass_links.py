"""Connect a local bypass only to an adjacent same-face package supply ball."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
latest='--ground-surface' in sys.argv
stage='power-bypass-ground-surface' if latest else 'local-power-bypass'
cp=json.loads((root/('layout-all-ground-surface.json' if latest else 'layout-package-local.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
pads=[q for f in b.GetFootprints() for q in f.Pads()]
chips=[b.FindFootprintByReference(ref) for ref in ('U1','U2','U8001')]
grounds={k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('C511').FindPadByNumber('2'))}
def own(q):return q.GetParentFootprint().GetReference()+'.'+q.GetNumber()
def ids(q):return {k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(q)}
rails={'+1V1_LPDDR4','+1V8_SYS','EMMC_IO_1V8','EMMC_3V3','VDD_CPU','VDD_GPU','VDD_LOGIC','VDD_NPU','VCCA_1V8','VCCA1V8_PMU','VDDA0V9_PMU','VDDA_0V9','USB_AVDD_0V9','USB_AVDD_1V8'}
pairs=[]
for cap in b.GetFootprints():
    if not cap.GetReference().startswith('C'):continue
    q=cap.FindPadByNumber('1');g=cap.FindPadByNumber('2')
    if not q or not g or q.GetNetname() not in rails or g.m_Uuid.AsString() not in grounds:continue
    for chip in chips:
        if chip.GetLayer()!=cap.GetLayer():continue
        for ball in chip.Pads():
            distance=math.dist(tuple(ball.GetPosition()),tuple(q.GetPosition()))
            if q.GetNetCode()==ball.GetNetCode() and distance<=2200000:pairs.append((distance,q,ball))
records=[]
for _,q,ball in sorted(pairs,key=lambda pair:pair[0]):
    if ball.m_Uuid.AsString() in ids(q):continue
    layer=q.GetParentFootprint().GetLayer();start=ball.GetPosition();end=q.GetPosition()
    obstacles=[o.GetEffectiveShape(layer) for o in pads+list(b.GetTracks()) if o.IsOnLayer(layer) and o.GetNetCode()!=q.GetNetCode() and o.GetBoundingBox().Inflate(3000000).Contains(start)]
    options=[]
    for dx in (-150000,0,150000):
      for dy in (-150000,0,150000):
        target=end+p.VECTOR2I(dx,dy)
        if not q.HitTest(target):continue
        x,y=target-start;d=min(abs(x),abs(y));step=p.VECTOR2I(int(math.copysign(d,x)),int(math.copysign(d,y)))
        for corner in (start+step,target-step):
            lines=[]
            for a,z in ((start,corner),(corner,target)):
                if a==z:continue
                t=p.PCB_TRACK(b);t.SetWidth(500000);t.SetNetCode(q.GetNetCode());t.SetLayer(layer);t.SetStart(a);t.SetEnd(z)
                lines.append(t)
            length=sum(t.GetLength() for t in lines)
            if lines and length<=2000000 and all(not t.GetEffectiveShape(layer).Collide(o,200000) for t in lines for o in obstacles):options.append((length,lines))
    if options:
        length,lines=min(options,key=lambda entry:entry[0])
        for t in lines:b.Add(t)
        b.BuildConnectivity();records.append(dict(pair=[own(q),own(ball)],length_mm=length/1e6))
folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
for n in ('fp-lib-table','phy-joint.kicad_dru','phy-joint.kicad_pro'):shutil.copy2(src.parent/n,folder/n)
out=folder/src.name
if records:
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    assert not introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    saved=p.LoadBoard(str(out));verify_preservation(p.LoadBoard(str(src)),saved);assert not screen(saved)
    for record in records:
        a,z=[saved.FindFootprintByReference(r).FindPadByNumber(n) for r,n in [s.split('.') for s in record['pair']]]
        assert z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(a)}
else:out=src
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],nearby_pairs=len(pairs),records=records,assembly_ready=False),indent=2)+'\n')
print(len(pairs),records,flush=True);os._exit(0)
