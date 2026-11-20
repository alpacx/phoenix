"""Join the remaining local PHY bypass to the integrated 3.3 V distribution on an inner layer."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
detour='--five-volt-clearance' in sys.argv
parent=json.loads((root/('phy-pin40-5v-clearance.json' if detour else 'phy-pin40-integrated.json')).read_text())
if detour:assert parent['change']
src=root/parent['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==parent['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
def copper(ref):
    pad=b.FindFootprintByReference(ref).FindPadByNumber('1')
    ids={k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(pad)}
    return [t for t in b.GetTracks() if t.m_Uuid.AsString() in ids]
source=copper('C515');load=copper('C518')
vias=[v for v in load if isinstance(v,p.PCB_VIA)]
assert len(vias)==1
pos=tuple(vias[0].GetPosition());code=vias[0].GetNetCode();solutions=[]
tap='--paired-tap' in sys.argv
offset='--barrel-entry' in sys.argv or tap
partners={}
def barrel(board,xy):
    v=p.PCB_VIA(board);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetWidth(600000);v.SetDrill(300000);v.SetPosition(p.VECTOR2I(*xy));v.SetNetCode(code);return v
stage='phy-pin40-paired-tap' if tap else 'phy-pin40-supply-offset' if offset else 'phy-pin40-supply'
if detour:stage+='-5v-clear'
starts=[pos]
if offset:
    starts.extend((pos[0]+dx*50000,pos[1]+dy*50000) for dx in range(-6,7) for dy in range(-6,7) if 0<dx*dx+dy*dy<=36)
for layer in ([p.In3_Cu] if tap else (p.In2_Cu,p.In3_Cu,p.B_Cu,p.F_Cu) if offset else (p.In2_Cu,p.In3_Cu)):
    obstacles,pads=geometry(b,layer,code,oval_caps=True)
    zones=[z.Outline().Outline(0) for z in b.Zones() if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks()]
    keepouts=[[tuple(k.CPoint(i)) for i in range(k.PointCount())] for k in zones]
    goals=set()
    for t in source:
        if not t.IsOnLayer(layer):continue
        a,z=t.GetStart(),t.GetEnd();n=max(1,math.ceil(math.dist(tuple(a),tuple(z))/200000))
        for i in range(n+1):
            goals.add(tuple(round(x+(y-x)*i/n) for x,y in zip(a,z)))
    if tap:
        goals.clear()
        tracks=list(b.GetTracks());pads_all=[q for f in b.GetFootprints() for q in f.Pads()]
        layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
        candidates=set()
        for t in source:
            if isinstance(t,p.PCB_VIA) or t.GetLayer()!=p.In2_Cu or t.GetWidth()<1050000:continue
            a,z=t.GetStart(),t.GetEnd();n=max(1,math.ceil(t.GetLength()/100000))
            for i in range(n+1):
                center=tuple(round(x+(y-x)*i/n) for x,y in zip(a,z))
                for dx,dy in ((0,0),(150000,0),(-150000,0),(0,150000),(0,-150000)):
                    candidates.add((center[0]+dx,center[1]+dy))
        for site in sorted(candidates):
            v=barrel(b,site);xy=v.GetPosition()
            if any(q.GetBoundingBox().Inflate(351000).Contains(xy) for q in pads_all):continue
            near=[t for t in tracks if t.GetBoundingBox().Inflate(850000).Contains(xy)]
            if any(isinstance(t,p.PCB_VIA) and (t.GetPosition()-xy).EuclideanNorm()<800000 for t in near):continue
            if any(t.GetNetCode()!=code and t.IsOnLayer(l) and t.GetEffectiveShape(l).Collide(v.GetEffectiveShape(l),200000) for l in layers for t in near):continue
            if any(z.GetIsRuleArea() and z.GetDoNotAllowVias() and z.Outline().Collide(v.GetEffectiveShape(p.F_Cu),0) for z in b.Zones()):continue
            goals.add(site)
        clear_sites=goals.copy();goals.clear()
        for a in sorted(clear_sites):
            for z in sorted(clear_sites,key=lambda z:math.dist(a,z)):
                if not 800000<=math.dist(a,z)<=1400000:continue
                t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(1050000);t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z))
                if any(k.GetNetCode()!=code and k.IsOnLayer(layer) and t.GetEffectiveShape(layer).Collide(k.GetEffectiveShape(layer),200000) for k in tracks if t.GetBoundingBox().Inflate(201000).Intersects(k.GetBoundingBox())):continue
                partners[a]=z;goals.add(a);break
    if tap:print('sites',len(candidates),len(clear_sites),len(goals),flush=True)
    req=dict(grid_nm=100000,bounds=[43000000,11000000,74000000,39500000],layers=[[obstacles,pads,keepouts]],through=[],via_keepouts=[[],[]],start=[starts],end=[sorted(goals)],width_nm=1050000)
    proc=subprocess.run(['python3',str(Path(__file__).with_name('control_board_grid.py'))],input=json.dumps(req),capture_output=True,text=True,check=True)
    sol=json.loads(proc.stdout)
    if sol:
        path=[p.VECTOR2I(x,y) for _,x,y in sol['path']]
        solutions.append((sum((a-z).EuclideanNorm() for a,z in zip(path,path[1:])),layer,path))
folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
out=src;change=None
for length,layer,path in sorted(solutions,key=lambda row:row[0]):
    board=p.LoadBoard(str(src))
    if tap:
        last=tuple(path[-1]);mate=partners[last]
        for xy in (last,mate):board.Add(barrel(board,xy))
        path.append(p.VECTOR2I(*mate));length+=(path[-2]-path[-1]).EuclideanNorm()
    for a,z in zip(path,path[1:]):
        t=p.PCB_TRACK(board);t.SetLayer(layer);t.SetWidth(1050000);t.SetNetCode(code);t.SetStart(a);t.SetEnd(z);board.Add(t)
    for name in ('fp-lib-table','phy-joint.kicad_dru','phy-joint.kicad_pro'):shutil.copy2(src.parent/name,folder/name)
    candidate=folder/src.name;p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(candidate),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(candidate)],capture_output=True,check=True)
    if introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text())):continue
    saved=p.LoadBoard(str(candidate));saved.BuildConnectivity()
    assert not screen(saved)
    a=saved.FindFootprintByReference('C515').FindPadByNumber('1')
    z=saved.FindFootprintByReference('U5').FindPadByNumber('40')
    assert z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(a)}
    change=dict(preservation=verify_preservation(b,saved),layer=b.GetLayerName(layer),length_mm=length/1e6,path_nm=[tuple(a) for a in path]);out=candidate;break
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=parent['sha256'],change=change,assembly_ready=False),indent=2)+'\n')
print(len(solutions),bool(change),flush=True);os._exit(0)
