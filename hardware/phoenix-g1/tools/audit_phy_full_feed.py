"""Verify full-width PHY routing, parallel barrels, breaks and mechanical datums on saved boards."""
import hashlib,json,math,os,sys,subprocess,re,tempfile
from pathlib import Path
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((root/(n+'.json')).read_text())
def load(n):
    r=read(n);path=root/r['board']
    assert r['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    b=p.LoadBoard(str(path));b.BuildConnectivity();return b
if '--probe' in sys.argv:
    board=p.LoadBoard(sys.argv[2]);board.BuildConnectivity()
    def check(ref,num):
        a=board.FindFootprintByReference(ref).FindPadByNumber(num)
        return {k.m_Uuid.AsString() for k in board.GetConnectivity().GetConnectedItems(a)}
    cap=board.FindFootprintByReference('C515').FindPadByNumber('1').m_Uuid.AsString()
    assert (cap in check('U5','11'))==(sys.argv[3]=='yes')
    assert board.FindFootprintByReference('U5').FindPadByNumber('38').m_Uuid.AsString() in check('C511','1')
    if sys.argv[4]=='complete':assert cap in check('R530','2')
    os._exit(0)
old=load('layout-opposite-bypass');new=load('phy-joint-terminal-shift')
def uid(o):return o.m_Uuid.AsString()
def linked(b,r1,n1,r2,n2):
    a=b.FindFootprintByReference(r1).FindPadByNumber(n1);z=b.FindFootprintByReference(r2).FindPadByNumber(n2)
    return uid(z) in {uid(k) for k in b.GetConnectivity().GetConnectedItems(a)}
assert not linked(old,'C515','1','U5','11') and linked(new,'C515','1','U5','11')
assert linked(new,'R530','2','C515','1') and linked(new,'C511','1','U5','38')
before={uid(t) for t in old.GetTracks()}
add=[t for t in new.GetTracks() if uid(t) not in before]
pv=[t for t in add if isinstance(t,p.PCB_VIA) and t.GetNetname()=='+3V3_PHY']
assert len(pv)==2 and all(t.GetWidth(p.F_Cu)==600000 and t.GetDrillValue()==300000 for t in pv)
signals=[t for t in add if not isinstance(t,p.PCB_VIA) and t.GetNetname()=='+3V3_PHY']
spurs=[t for t in signals if t.GetWidth()!=1050000]
assert len(spurs)==1 and spurs[0].GetWidth()==200000 and spurs[0].GetLength()<=1450000
path=read('phy-joint-terminal-shift')['change']['path']
trunk=[]
for a,z in zip(path,path[1:]):
    assert a[0]==z[0]==2
    ts=[t for t in signals if t.GetLayer()==p.In2_Cu and set((tuple(t.GetStart()),tuple(t.GetEnd())))==set((tuple(a[1:]),tuple(z[1:])))]
    assert len(ts)==1 and ts[0].GetWidth()==1050000
    trunk.extend(ts)
def test_cut(removed,expected,isolate_trunk=False):
    cut=set(removed)
    if isolate_trunk:
        cut.update(uid(k) for k in old.GetTracks() if not isinstance(k,p.PCB_VIA) and k.GetNetname()=='+3V3_PHY' and k.GetLayer()==p.In2_Cu)
    source=root/read('phy-joint-terminal-shift')['board']
    pattern=r'\n\t\((?:segment|via)\n.*?\n\t\)'
    found=set()
    def drop(match):
        ident=re.search(r'\(uuid "([^"]+)"',match[0]).group(1)
        if ident not in cut:return match[0]
        found.add(ident);return ''
    data=re.sub(pattern,drop,source.read_text(),flags=re.S);assert cut==found
    with tempfile.TemporaryDirectory() as temp:
        edited=Path(temp)/source.name;edited.write_text(data)
        subprocess.run([sys.executable,__file__,'--probe',str(edited),'yes' if expected else 'no','isolated' if isolate_trunk else 'complete'],check=True)
if '--cut' in sys.argv:
    test_cut(sys.argv[4:],sys.argv[2]=='yes',sys.argv[3]=='isolated')
    os._exit(0)
def isolated(removed,wanted,isolate_trunk=False):
    subprocess.run([sys.executable,__file__,'--cut','yes' if wanted else 'no','isolated' if isolate_trunk else 'complete',*removed],check=True,capture_output=True)
tests=[]
for t in pv:
    isolated([uid(t)],True);tests.append(dict(remove=[uid(t)],connected=True))
isolated([uid(t) for t in pv],False);tests.append(dict(remove=[uid(t) for t in pv],connected=False))
isolated([],True,True);tests.append(dict(remove_existing_inner_power_copper=True,connected=True))
isolated([uid(trunk[-1])],False,True);tests.append(dict(remove_existing_inner_power_copper=True,remove=[uid(trunk[-1])],connected=False))
def mounts(b):
    return {f.GetReference():tuple(f.GetPosition()) for f in b.GetFootprints() if f.GetReference().startswith('H81')}
original,current=mounts(old),mounts(new)
assert set(original)==set(current) and [n for n in current if original[n]!=current[n]]==['H8105']
hole=new.FindFootprintByReference('H8105');q=next(iter(hole.Pads()));assert q.GetAttribute()==p.PAD_ATTRIB_NPTH and tuple(q.GetDrillSize())==(2200000,2200000)
def outline(b):
    z=next(z for z in b.Zones() if z.GetZoneName()=='H8105 mechanical reservation')
    return [tuple(z.Outline().Outline(0).CPoint(i)) for i in range(z.Outline().Outline(0).PointCount())],list(z.GetLayerSet().Seq())
oldshape,oldlayers=outline(old);shape,layers=outline(new)
assert layers==oldlayers and len(shape)==len(oldshape) and all((x-ox,y-oy)==(200000,0) for (x,y),(ox,oy) in zip(shape,oldshape))
report=dict(board=read('phy-joint-terminal-shift')['board'],sha256=read('phy-joint-terminal-shift')['sha256'],parent_sha256=read('layout-opposite-bypass')['sha256'],power_vias_nm=[tuple(t.GetPosition()) for t in pv],trunk_width_mm=1.05,trunk_length_mm=sum(t.GetLength() for t in trunk)/1e6,local_spur_mm=spurs[0].GetLength()/1e6,cut_tests=tests,mounts_nm=current,old_H8105_nm=original['H8105'],hole_mm=2.2,all_reservation_vertices_translated=True,assembly_ready=False)
(root/'phy-full-feed-proof.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['trunk_length_mm'],report['local_spur_mm'],len(tests),flush=True);os._exit(0)
