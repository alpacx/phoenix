"""Launch a relocated PMIC management bus pin to a legal through via before trunk reconnection."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from native_front_splice import compact
from drc_regression import introduced
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def read(path):return json.loads(path.read_text())
reverse='--left-first' in sys.argv
name='SDA' if '--sda' in sys.argv else 'SCL';num='2' if name=='SDA' else '1'
d=read(root/('rotated-pmic-scl-complete.json' if name=='SDA' else 'rotated-pmic-cap-ground-pivots.json'));src=root/d['board'];meta=read(root/('rotated-pmic-secondary-control-exits.json' if name=='SDA' else 'rotated-pmic-long-control-exits.json'))
if reverse:
    d=read(root/('rotated-pmic-cap-ground-pivots.json' if name=='SDA' else 'rotated-left-sda-complete.json'))
    src=root/d['board'];meta=read(root/('rotated-pmic-long-control-exits.json' if name=='SDA' else 'rotated-left-scl-exits.json'))
cleared='--after-c422' in sys.argv
if cleared:
    d=read(root/'rotated-scl-cap-release.json')['candidate'];src=root/d['board'];meta=read(root/'rotated-c422-scl-exits.json')
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['coupon_sha256']==d['sha256']
opts=[o for r in meta['circuits'] if r['label'].startswith('U4.'+num+' ') for o in r['via_paths']]
if reverse and name=='SDA':opts.sort(key=lambda o:math.dist(o['via_nm'],(60500000,1050000)))
label=('rotated-c422-' if cleared else 'rotated-left-' if reverse else 'rotated-pmic-')+name.lower()
parent=p.LoadBoard(str(src));base=read(src.parent/'drc.json');attempts=[];result=None
for index,opt in enumerate(opts):
    b=p.LoadBoard(str(src));fp=b.FindFootprintByReference('U4');q=fp.FindPadByNumber(num);code=q.GetNetCode()
    points=compact([tuple(pt) for j,pt in enumerate(opt['track_nm']) if j==0 or pt!=opt['track_nm'][j-1]])
    for a,z in zip(points,points[1:]):
        t=p.PCB_TRACK(b);t.SetLayer(p.F_Cu);t.SetWidth(200000);t.SetNetCode(code);t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));b.Add(t)
    v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetWidth(450000);v.SetDrill(200000);v.SetNetCode(code);v.SetPosition(p.VECTOR2I(*opt['via_nm']));b.Add(v)
    folder=root/'runs'/(label+'-launch-'+str(index));folder.mkdir(exist_ok=True)
    for filename in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/filename,folder/filename)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(base,read(folder/'drc.json'));attempts.append(dict(site=opt['via_nm'],new_drc=delta))
    via_id=v.m_Uuid.AsString()
    if any(x['type']!='via_dangling' or x['items']!=[via_id] for x in delta):continue
    saved=p.LoadBoard(str(out));guard=verify_preservation(parent,saved);pin=saved.FindFootprintByReference('U4').FindPadByNumber(num)
    assert via_id in {t.m_Uuid.AsString() for t in saved.GetConnectivity().GetConnectedItems(pin)}
    result=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=d['sha256'],via_id=via_id,via_nm=opt['via_nm'],pin='U4.'+num,length_mm=opt['length_mm'],preservation=guard,new_drc=delta);break
(root/(label+'-launch.json')).write_text(json.dumps(dict(candidate=result,attempts=attempts,assembly_ready=False),indent=2)+'\n')
print(name,result and result['via_nm'],attempts,flush=True);os._exit(0)
