"""Connect a local bypass to an opposite-face supply ball with a single short via path."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
bank='--bank-lands' in sys.argv
filled='--filled-cap' in sys.argv
paired='--c2308-return' in sys.argv
bends='--bends' in sys.argv or paired or filled or bank
stage='bank-lands' if bank else 'opposite-filled-cap' if filled else 'c2308-paired-return' if paired else 'opposite-bypass-bends' if bends else 'opposite-power-bypass'
cp=json.loads((root/('layout-cap-bank.json' if bank else 'layout-opposite-bypass.json' if bends else 'layout-package-local.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
pads=[q for f in b.GetFootprints() for q in f.Pads()]
chips=[b.FindFootprintByReference(ref) for ref in ('U1','U2','U8001')]
grounds={k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('C511').FindPadByNumber('2'))}
def own(q):return q.GetParentFootprint().GetReference()+'.'+q.GetNumber()
def ids(q):return {k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(q)}
rails={'+1V1_LPDDR4','+1V8_SYS','EMMC_IO_1V8','EMMC_3V3','+3V3_IO','VDD_CPU','VDD_GPU','VDD_LOGIC','VDD_NPU','VCCA_1V8','VCCA1V8_PMU','VDDA0V9_PMU','VDDA_0V9','USB_AVDD_0V9','USB_AVDD_1V8'}
pairs=[]
for cap in b.GetFootprints():
    if not cap.GetReference().startswith('C'):continue
    q=cap.FindPadByNumber('1');g=cap.FindPadByNumber('2')
    if not q or not g or q.GetNetname() not in rails or g.m_Uuid.AsString() not in grounds:continue
    for chip in chips:
        if chip.GetLayer()==cap.GetLayer():continue
        for ball in chip.Pads():
            distance=math.dist(tuple(ball.GetPosition()),tuple(q.GetPosition()))
            if q.GetNetCode()==ball.GetNetCode() and distance<=2200000:pairs.append((distance,q,ball))
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
if paired:
    c=b.FindFootprintByReference('C2308').FindPadByNumber('2')
    chip=b.FindFootprintByReference('U2')
    pairs=[(math.dist(tuple(c.GetPosition()),tuple(ball.GetPosition())),c,ball) for ball in chip.Pads() if ball.GetNetname()=='GND' and math.dist(tuple(c.GetPosition()),tuple(ball.GetPosition()))<2000000]
records=[]
for _,q,ball in sorted(pairs,key=lambda pair:pair[0]):
    if not paired and ball.m_Uuid.AsString() in ids(q):continue
    start,end=ball.GetPosition(),q.GetPosition()
    layer1=ball.GetParentFootprint().GetLayer();layer2=q.GetParentFootprint().GetLayer()
    local=[o for o in pads+list(b.GetTracks()) if o.GetBoundingBox().Inflate(3300000).Contains(start)]
    obstacles={l:[o.GetEffectiveShape(l) for o in local if o.IsOnLayer(l) and o.GetNetCode()!=q.GetNetCode()] for l in layers}
    def clear(t,l):
        return all(not t.GetEffectiveShape(l).Collide(shape,200000) for shape in obstacles[l])
    def track(a,z,l):
        t=p.PCB_TRACK(b);t.SetWidth(500000);t.SetNetCode(q.GetNetCode());t.SetLayer(l);t.SetStart(a);t.SetEnd(z);return t
    def clear_path(a,z,l):
        x,y=z-a;distance=min(abs(x),abs(y))
        step=p.VECTOR2I(int(math.copysign(distance,x)),int(math.copysign(distance,y)))
        for c in (a+step,z-step):
            traces=[track(u,v,l) for u,v in ((a,c),(c,z)) if u!=v]
            if all(clear(t,l) for t in traces):return traces
        return None
    options=[]
    for ix in range(-12,13):
      for iy in range(-12,13):
        z=start+p.VECTOR2I(ix*100000,iy*100000)
        if paired and not 800000<=math.dist(tuple(z),(25000000,5325000))<=1200000:continue
        length=math.dist(tuple(start),tuple(z))+math.dist(tuple(z),tuple(end))
        if length>2200000:continue
        if filled:
            # Keep the capped barrel completely inside the existing land.
            if any(not q.HitTest(z+p.VECTOR2I(round(300000*math.cos(i*math.pi/32)),round(300000*math.sin(i*math.pi/32)))) for i in range(64)):continue
        if not bank and any(isinstance(o,p.PAD) and (not filled or o.m_Uuid!=q.m_Uuid) and o.GetBoundingBox().Inflate(351000).Contains(z) for o in local):continue
        if any(isinstance(o,p.PCB_VIA) and math.dist(tuple(o.GetPosition()),tuple(z))<800000 for o in local):continue
        if any(zone.GetIsRuleArea() and zone.GetDoNotAllowVias() and zone.GetBoundingBox().Inflate(301000).Contains(z) for zone in b.Zones()):continue
        v=p.PCB_VIA(b);v.SetPosition(z);v.SetWidth(600000);v.SetDrill(300000);v.SetNetCode(q.GetNetCode());v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu)
        if bank and any(v.GetEffectiveShape(o.GetLayer()).Collide(o.GetEffectiveShape(o.GetLayer()),51000) for o in local if isinstance(o,p.PAD)):continue
        if filled:
            v.SetWidth(550000);v.SetFillingMode(p.FILLING_MODE_FILLED);v.SetCappingMode(p.CAPPING_MODE_CAPPED)
            front=clear_path(start,z,layer1)
            if front and all(clear(v,l) for l in layers):
                options.append((sum(t.GetLength() for t in front),front+[v]))
            continue
        if bends:
            if not all(clear(v,l) for l in layers):continue
            front=clear_path(start,z,layer1)
            if bank and front is None:
                for ix,iy in ((-75000,0),(75000,0),(0,75000),(0,-75000)):
                    toe=start+p.VECTOR2I(ix,iy)
                    if ball.HitTest(toe):
                        front=clear_path(toe,z,layer1)
                        if front is not None:break
            if front is None:continue
            for dx,dy in ((0,0),(-150000,0),(150000,0),(0,150000),(0,-150000)):
                target=end+p.VECTOR2I(dx,dy)
                if not q.HitTest(target):continue
                back=clear_path(z,target,layer2)
                if back is None:continue
                run=sum(t.GetLength() for t in front+back)
                if run<=2200000:options.append((run,front+[v]+back))
            continue
        t=track(start,z,layer1);r=track(z,end,layer2)
        if clear(t,layer1) and clear(r,layer2) and all(clear(v,l) for l in layers):options.append((length,[t,v,r]))
    if options:
        length,lines=min(options,key=lambda entry:entry[0])
        for t in lines:b.Add(t)
        b.BuildConnectivity();records.append(dict(pair=[own(q),own(ball)],surface_length_mm=length/1e6,via_nm=[tuple(t.GetPosition()) for t in lines if isinstance(t,p.PCB_VIA)]))
        if paired:break
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
