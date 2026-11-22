"""Extend capacitor-connected supply copper to nearby same-rail balls on the same package."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from audit_mount_component_reservations import screen
from pcb_preservation import verify_preservation
from pcb_bounds import inflated_box
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
package_feeds='--package-feeds' in sys.argv
extended='--bank-feeds' in sys.argv or package_feeds
other_banks='--regulator-banks' in sys.argv or extended
pullups='--emmc-pullups' in sys.argv
diagonals='--diagonal-neighbors' in sys.argv
aux='--peripheral-supplies' in sys.argv
cap_bank='--cap-bank' in sys.argv or other_banks
meta=json.loads((root/('layout-bank-feeds.json' if package_feeds else 'layout-regulator-banks.json' if extended else 'layout-emmc-pullups.json' if other_banks else 'layout-usb-shell.json' if diagonals or pullups else 'layout-cap-bank.json' if aux else 'layout-adjacent-supplies.json' if cap_bank else 'layout-phy-pin40-powered.json')).read_text())
src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
board=p.LoadBoard(str(src));board.BuildConnectivity()
pads=[q for f in board.GetFootprints() for q in f.Pads()]
rails={'+1V1_LPDDR4','+1V8_SYS','EMMC_IO_1V8','EMMC_3V3','+3V3_IO','VDD_CPU','VDD_GPU','VDD_LOGIC','VDD_NPU','VCCA_1V8','VCCA1V8_PMU','VDDA0V9_PMU','VDDA_0V9','USB_AVDD_0V9','USB_AVDD_1V8'}
if diagonals:rails.update({'VDDA0V9_IMAGE','+3V3_PMU','VCCIO_SD','VCCA1V8_IMAGE','+3V3_SD','VCCIO_ACODEC'})
if aux:rails={'VDDA0V9_IMAGE','+3V3_PMU','VCCIO_SD','VCCA1V8_IMAGE','+3V3_SD','VCCIO_ACODEC'}
if other_banks:rails.update({'+5V_MAIN','+3V3_SYS','+3V3_PMU','+3V3_SD','VCCIO_SD','VCCA1V8_IMAGE','VDDA0V9_IMAGE','VCCIO_ACODEC','+3V58_WIFI','EMMC_VDDI'})
def label(q):return q.GetParentFootprint().GetReference()+'.'+q.GetNumber()
def group(q):return {i.m_Uuid.AsString() for i in board.GetConnectivity().GetConnectedItems(q)}
ground=group(board.FindFootprintByReference('C511').FindPadByNumber('2'))
caps=[q for q in pads if q.GetNetname() in rails and q.GetParentFootprint().GetReference().startswith('C') and any(g.m_Uuid.AsString() in ground for g in q.GetParentFootprint().Pads())]
islands='--adjacent-balls' in sys.argv
stage='diagonal-supply-balls' if diagonals else 'peripheral-supply-balls' if aux else 'local-cap-bank' if cap_bank else 'package-adjacent-supplies' if islands else 'package-supply-neighbors'
if pullups:
    rails={'EMMC_IO_1V8'}
    stage='emmc-pullup-supply'
    caps.extend(q for q in pads if q.GetNetname() in rails and q.GetParentFootprint().GetReference() in {'R8001','R8002','R8003','R8006'})
if other_banks:stage='bank-feeds' if extended else 'regulator-banks'
if package_feeds:
    stage='package-feeds'
    # Connect a grounded bypass to its supply land, keeping branches short.
    caps.extend(q for q in pads if q.GetNetname() in rails and q.GetParentFootprint().GetReference().startswith('U'))
records=[]
for ref in (('front','back') if cap_bank or pullups else ('U1','U2','U8001')):
    chip=board.FindFootprintByReference(ref)
    layer=(p.F_Cu if ref=='front' else p.B_Cu) if cap_bank or pullups else chip.GetLayer()
    for net in sorted(rails):
        balls=[q for q in (caps if cap_bank or pullups else chip.Pads()) if q.GetNetname()==net and q.IsOnLayer(layer)]
        if not balls:continue
        candidates=[]
        for cap in (q for q in caps if q.GetNetname()==net):
            original=group(cap)
            for a in balls:
                if a.m_Uuid.AsString() not in original:continue
                for z in balls:
                    if z.m_Uuid.AsString() in original:continue
                    d=(a.GetPosition()-z.GetPosition()).EuclideanNorm()
                    if d<=1600000:candidates.append((d,cap,a,z))
        if islands or cap_bank or aux or diagonals or pullups:
            for i,a in enumerate(balls):
                for z in balls[i+1:]:
                    d=(a.GetPosition()-z.GetPosition()).EuclideanNorm()
                    if 0<d<=(4000000 if extended else 2800000 if other_banks else 3600000 if pullups else 940000 if diagonals else 1500000 if cap_bank else 660000):candidates.append((d,a,a,z))
        for _,cap,a,z in sorted(candidates,key=lambda k:k[0]):
            if z.m_Uuid.AsString() in group(a):continue
            if package_feeds:
                refs=[q.GetParentFootprint().GetReference()[0] for q in (a,z)]
                if sorted(refs)!=['C','U']:continue
            u,v=a.GetPosition(),z.GetPosition();dx,dy=v-u
            d=min(abs(dx),abs(dy));step=p.VECTOR2I(int(math.copysign(d,dx)),int(math.copysign(d,dy)))
            obs=[o.GetEffectiveShape(layer) for o in pads+list(board.GetTracks()) if o.IsOnLayer(layer) and o.GetNetCode()!=a.GetNetCode() and inflated_box(o,4800000 if extended else 4200000 if pullups or other_banks else 2200000).Contains(u)]
            for c in (u+step,v-step):
                tracks=[]
                for i,j in ((u,c),(c,v)):
                    if i==j:continue
                    t=p.PCB_TRACK(board);t.SetNetCode(a.GetNetCode());t.SetWidth(500000);t.SetLayer(layer);t.SetStart(i);t.SetEnd(j)
                    if any(t.GetEffectiveShape(layer).Collide(o,200000) for o in obs):break
                    tracks.append(t)
                else:
                    for t in tracks:board.Add(t)
                    board.BuildConnectivity()
                    assert z.m_Uuid.AsString() in group(cap)
                    records.append(dict(pair=[label(cap),label(z)],branch_from=label(a),width_mm=.5,length_mm=sum(t.GetLength() for t in tracks)/1e6))
                    break
out=src
if records:
    folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
    for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/n,folder/n)
    out=folder/src.name;p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(out),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));assert not delta,delta
    saved=p.LoadBoard(str(out));saved.BuildConnectivity();verify_preservation(p.LoadBoard(str(src)),saved);assert not screen(saved)
    for rec in records:
        a,z=[saved.FindFootprintByReference(r).FindPadByNumber(n) for r,n in (s.split('.') for s in rec['pair'])]
        assert z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(a)}
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=meta['sha256'],records=records,assembly_ready=False),indent=2)+'\n')
print(records,flush=True);os._exit(0)
