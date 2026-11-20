"""Connect lightly loaded divider terminals to already connected power/ground copper."""
from pathlib import Path
import hashlib,json,math,os,subprocess,shutil
import pcbnew as p
from drc_regression import introduced
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
filter_cap='--filter' in sys.argv
cp=json.loads((root/('sense-filter-verified.json' if filter_cap else 'sense-front-verified.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
current=src;records=[]
original=p.LoadBoard(str(src))
def exactly(b,t):
    return b.FindFootprintByReference(t[0]).FindPadByNumber(t[1])
def group(b,q):
    return list(b.GetConnectivity().GetConnectedItems(q))
for ref,num,connected in ([('C1503','2',('R1506','2'))] if filter_cap else [('R1506','2',('C511','2')),('R1505','1',('C2007','1'))]):
    b=p.LoadBoard(str(current));b.BuildConnectivity();q=exactly(b,(ref,num));rail=exactly(b,connected)
    assert q.GetNetCode()==rail.GetNetCode()
    if q.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in group(b,rail)}:continue
    layers=[p.F_Cu,p.In2_Cu];origin=tuple(q.GetPosition())
    provider=group(b,rail);points=[]
    for l in layers:
        sites=set()
        for o in provider:
            if not o.IsOnLayer(l):continue
            if isinstance(o,p.PCB_TRACK):
                a,z=tuple(o.GetStart()),tuple(o.GetEnd())
                if min(math.dist(a,origin),math.dist(z,origin))>18e6:continue
                count=max(1,math.ceil(o.GetLength()/500000))
                sites.update(tuple(round(u+(v-u)*i/count) for u,v in zip(a,z)) for i in range(count+1))
            elif isinstance(o,p.PAD):sites.add(tuple(o.GetPosition()))
        points.append(sorted(sites,key=lambda z:math.dist(z,origin))[:250])
    geos={l:geometry(b,l,q.GetNetCode()) for l in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)}
    for l,(_,pads) in geos.items():
        for z in b.Zones():
            if z.GetIsRuleArea() and z.IsOnLayer(l) and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
                v=z.GetBoundingBox();pads.append((v.GetLeft(),v.GetTop(),v.GetRight(),v.GetBottom()))
    obj=dict(seeds=points,goals={ref:origin},layers=[geos[l] for l in layers],through=list(geos.values()),bounds=[max(1e6,origin[0]-18e6),max(1e6,origin[1]-15e6),min(89e6,origin[0]+18e6),39e6])
    sol=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('phy_bias_paths.py'))],input=json.dumps(obj),text=True,capture_output=True,check=True).stdout)
    if not sol:print(ref,'no path',flush=True);continue
    for (l,x,y),(k,u,v) in zip(sol['path'],sol['path'][1:]):
        if l==k:
            t=p.PCB_TRACK(b);t.SetLayer(layers[l]);t.SetWidth(200000);t.SetStart(p.VECTOR2I(x,y));t.SetEnd(p.VECTOR2I(u,v))
        else:
            assert (x,y)==(u,v)
            t=p.PCB_VIA(b);t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetWidth(450000);t.SetDrill(200000);t.SetPosition(p.VECTOR2I(x,y))
        t.SetNetCode(q.GetNetCode());b.Add(t)
    folder=root/'runs'/('local-passive-'+ref);folder.mkdir(exist_ok=True)
    for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    saved=p.LoadBoard(str(out));pres=verify_preservation(original,saved)
    assert q.m_Uuid.AsString() in {t.m_Uuid.AsString() for t in group(saved,exactly(saved,connected))}
    if not delta:current=out
    records.append(dict(ref=ref,pad=num,node=list(connected),path=sol['path'],new_drc=delta,preservation=pres))
    print(ref,delta,flush=True)
(root/('sense-filter-return.json' if filter_cap else 'local-passive-feeds.json')).write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),records=records),indent=2)+'\n');os._exit(0)
