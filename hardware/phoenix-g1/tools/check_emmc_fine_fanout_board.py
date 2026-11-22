"""Place the jointly reserved 3-mil escape pattern on actual copper without changing PCB rules."""
from pathlib import Path
import hashlib,json,math,shutil,subprocess
from collections import Counter
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make,barrel
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((root/(n+'.json')).read_text())
base=read('layout-emmc-data-power');study=read('emmc-bus-local-3mil-study')
src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']==study['parent_sha256']
b=p.LoadBoard(str(src));f=b.FindFootprintByReference('U8001');side=f.GetLayer();assert side==p.B_Cu
origin=f.FindPadByNumber('A3').GetPosition();vx=f.FindPadByNumber('A4').GetPosition()-origin;vy=f.FindPadByNumber('B3').GetPosition()-origin
def global_point(k):
    x=(k[0]+2.25)*2;y=(k[1]+3.25)*2
    return origin.x+round(x*vx.x+y*vy.x),origin.y+round(x*vx.y+y*vy.y)
for q in f.Pads():
    n=q.GetNumber();xy=((int(n[1:])-7.5)*.5,('ABCDEFGHJKLMNP'.index(n[0])-6.5)*.5)
    assert global_point(xy)==tuple(q.GetPosition())
objs=[*b.GetTracks(),*(q for component in b.GetFootprints() for q in component.Pads())]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
uid=lambda o:o.m_Uuid.AsString()
def desc(o):return dict(type=o.GetClass(),layer=b.GetLayerName(o.GetLayer()),net=o.GetNetname(),uuid=uid(o),pad=o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else None)
def errors(item,code,check_via):
    hit={}
    box=inflated_box(item,350000);relevant=layers if check_via else [side]
    for other in objs:
        if not box.Intersects(other.GetBoundingBox()):continue
        same=code==other.GetNetCode()
        lead=78200 if isinstance(other,p.PAD) and other.GetParentFootprint().GetReference()=='U8001' else 202000
        drilled=isinstance(other,p.PCB_VIA) or (isinstance(other,p.PAD) and other.GetDrillSize().x)
        for l in relevant:
            body=item.GetEffectiveShape(l)
            foreign=other.IsOnLayer(l) and not same
            if foreign and body.Collide(other.GetEffectiveShape(l),lead):hit[uid(other)]=desc(other)
            if drilled and body.Collide(other.GetEffectiveHoleShape(),252000):hit[uid(other)]=desc(other)
            if check_via and foreign and item.GetEffectiveHoleShape().Collide(other.GetEffectiveShape(l),252000):hit[uid(other)]=desc(other)
    return list(hit.values())
rows=[];pending=[]
for n,row in study['simultaneous'].items():
    assert row['sites']
    q=f.FindPadByNumber(n);code=q.GetNetCode()
    if n=='A3':continue
    input_path=[global_point(point) for point in row['path_mm']];clean=[]
    for pt in input_path:
        if len(clean)>1:
            a,mid=clean[-2:]
            if (pt[0]-mid[0])*(mid[1]-a[1])==(pt[1]-mid[1])*(mid[0]-a[0]):clean.pop()
        clean.append(pt)
    pieces=[make(b,a,z,76200,code,side) for a,z in zip(clean,clean[1:])]
    via=barrel(b,clean[-1],code)
    hits={q['uuid']:q for t in pieces for q in errors(t,code,False)}
    via_hits=errors(via,code,True)
    rows.append(dict(pin=n,net=q.GetNetname(),track_obstacles=list(hits.values()),barrel_obstacles=via_hits,path_nm=clean))
    pending.extend([*pieces,via])
for item in pending:b.Add(item)
folder=root/'runs/emmc-fine-bus-on-board';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
# A deliberate collision makes connectivity preservation impossible; report any physical merge separately.
saved=p.LoadBoard(str(out));saved.BuildConnectivity()
initial={uid(o):o for o in objs}
current={uid(o):o for o in [*saved.GetTracks(),*(q for f in saved.GetFootprints() for q in f.Pads())]}
shorts=[]
for violation in json.loads((folder/'drc.json').read_text())['violations']:
    if violation['type']!='shorting_items':continue
    parts=[current[t['uuid']] for t in violation['items'] if t['uuid'] in current]
    incident=[dict(**desc(t),existing=uid(t) in initial) for t in parts]
    nets=sorted({t.GetNetname() for t in parts})
    shorts.append(dict(nets=nets,different_nets=len(nets)>1,parts=incident))
report=dict(shorts=shorts,parent_sha256=base['sha256'],coupon=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),rows=rows,native_drc=dict(Counter(x['type'] for x in delta)),adopted=False,assembly_ready=False)
(root/'emmc-fine-bus-on-board.json').write_text(json.dumps(report,indent=2)+'\n')
print([(r['pin'],len(r['track_obstacles']),len(r['barrel_obstacles'])) for r in rows],report['native_drc'])
