"""Route the named management-bus endpoints, checking each saved stage before reuse."""
from pathlib import Path
import hashlib,json,math,os,subprocess,shutil
import pcbnew as p
from phy_corridor_path import geometry
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
stages={
    '': ('low-speed-links', 'pmic-control-bus', 'pmic-control'),
    '--phy-config': ('local-controls-verified', 'phy-config-links', 'pmic-control'),
    '--service-links': ('layout-reset-connectivity', 'service-links', 'service-link'),
    '--off-pad-services': ('layout-reset-connectivity', 'off-pad-services', 'off-pad-service'),
    '--lead-escape': ('off-pad-services', 'lead-escape', 'control-toe'),
    '--corner-escape': ('control-passives', 'corner-escape', 'control-corner'),
    '--round-pad-escape': ('surface-ground', 'rounded-escape', 'control-rounded'),
    '--reservation-contour': ('rounded-escape', 'contour-escape', 'control-contour'),
    '--signal-layers': ('contour-escape', 'multilayer-controls', 'control-multilayer'),
    '--edge-corridor': ('multilayer-controls', 'perimeter-controls', 'control-perimeter'),
    '--sda-clearance': ('pmic-sda-clearance', 'sda-link', 'control-sda'),
    '--header-signals': ('sda-link', 'header-signals', 'header-io'),
    '--emmc-power-trunks': ('emmc-vccq-link', 'emmc-trunks', 'emmc-trunk'),
    '--rail-inputs': ('bias-feeds', 'emmc-rail-inputs', 'emmc-rail'),
    '--bias-feeds': ('emmc-input-bank', 'bias-feeds', 'bias-feed'),
}
mode=sys.argv[1] if len(sys.argv)>1 else ''
parent,report_name,folder_prefix=stages[mode]
straps=mode in ('--phy-config',)
service=mode in ('--service-links', '--off-pad-services', '--lead-escape', '--corner-escape', '--round-pad-escape', '--reservation-contour', '--signal-layers', '--edge-corridor', '--sda-clearance', '--header-signals', '--emmc-power-trunks', '--bias-feeds', '--rail-inputs')
assembly=mode in ('--off-pad-services', '--lead-escape', '--corner-escape', '--round-pad-escape', '--reservation-contour', '--signal-layers', '--edge-corridor', '--sda-clearance', '--header-signals', '--emmc-power-trunks', '--bias-feeds', '--rail-inputs')
controls=mode in ('--lead-escape', '--corner-escape', '--round-pad-escape', '--reservation-contour', '--signal-layers', '--edge-corridor', '--sda-clearance', '--header-signals', '--emmc-power-trunks', '--bias-feeds', '--rail-inputs')
corners=mode in ('--corner-escape', '--round-pad-escape', '--reservation-contour', '--signal-layers', '--edge-corridor', '--sda-clearance', '--header-signals', '--emmc-power-trunks', '--bias-feeds', '--rail-inputs')
rounded=mode in ('--round-pad-escape', '--reservation-contour', '--signal-layers', '--edge-corridor', '--sda-clearance', '--header-signals', '--emmc-power-trunks', '--bias-feeds', '--rail-inputs')
contour=mode in ('--reservation-contour', '--signal-layers', '--edge-corridor', '--sda-clearance', '--header-signals', '--emmc-power-trunks', '--bias-feeds', '--rail-inputs')
multi=mode in ('--signal-layers', '--edge-corridor', '--sda-clearance', '--header-signals', '--emmc-power-trunks', '--bias-feeds', '--rail-inputs')
perimeter=mode in ('--edge-corridor', '--sda-clearance', '--header-signals', '--emmc-power-trunks', '--bias-feeds', '--rail-inputs')
relief=mode in ('--sda-clearance', '--header-signals', '--emmc-power-trunks', '--bias-feeds', '--rail-inputs')
headers=mode in ('--header-signals', '--emmc-power-trunks', '--bias-feeds', '--rail-inputs')
rail_inputs=mode=='--rail-inputs'
power=mode=='--emmc-power-trunks' or rail_inputs
biases=mode=='--bias-feeds'
cp=json.loads((root/(parent+'.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
prior=json.loads((src.parent/'drc.json').read_text());original=p.LoadBoard(str(src));current=src;records=[];held=[]
def pad(b,s):
    r,n=s.split('.');return b.FindFootprintByReference(r).FindPadByNumber(n)
def group(b,q):return [q, *b.GetConnectivity().GetConnectedItems(q)]
def padset(items):return {o.m_Uuid.AsString() for o in items if isinstance(o,p.PAD)}
def terminals(b,items,layer):
    points=set()
    for o in items:
        if not o.IsOnLayer(layer):continue
        if isinstance(o,p.PAD):
            pos=o.GetPosition();points.add(tuple(pos))
            for d in range(-400000,400001,50000):
                for v in (p.VECTOR2I(d,0),p.VECTOR2I(0,d)):
                    site=pos+v
                    if o.HitTest(site):points.add(tuple(site))
        elif isinstance(o,p.PCB_TRACK):
            a,z=tuple(o.GetStart()),tuple(o.GetEnd());n=max(1,math.ceil(o.GetLength()/350000))
            points.update(tuple(round(x+(y-x)*i/n) for x,y in zip(a,z)) for i in range(n+1))
    return points
pairs=[('U4.1','R414.2'),('U4.2','R415.2'),('U10.A3','R414.1'),('U10.B1','R415.1'),('U1.AG23','U10.A3'),('U1.AE23','U10.B1'),('U4.7','R413.2'),('U4.67','U16.2')]
if straps:pairs=[('U5.33','R528.1'),('U5.34','R529.1')]
if service:
    pairs=[('R412.1','C465.1'),('R413.1','R412.1'),('C411.1','U16.2'),('R1103.1','C411.1'),('R1507.2','U16.2')]
if controls:
    pairs=[('U4.1','R414.2'),('U4.2','R415.2'),('U4.7','R413.2'),('U4.67','U16.2'),('U4.52','C412.1'),('U5.33','R528.1'),('U5.34','R529.1'),('U5.32','R527.1'),('U5.14','R514.1'),('U6.12','U16.4'),('U6.11','R602.2'),('U25.12','R2002.1'),('TP10.1','R1504.1')]
if relief:pairs=[('U4.2','R415.2')]
if headers:
    pairs=[('R2101.1','J3.23'),('R2102.1','J3.24'),('R2103.1','J3.34'),('R2104.1','J3.35'),
           ('U1.Y26','J3.25'),('U1.Y25','J3.26'),('U1.K3','J3.29'),('U1.L2','J3.30'),
           ('U1.AE20','TP12.1'),('U1.AF20','TP11.1'),('U1.T2','R515.1'),('U1.N2','U21.5'),
           ('U1.M3','U21.6'),('U1.L1','R1801.1'),('U1.V26','U25.13'),('U8001.K5','R8003.2')]
if power:pairs=[('R8007.2','C8009.1'),('R8006.2','C8006.1'),('R8006.2','C8003.1')]
if biases:
    pairs=[('R8001.1','C8003.1'),('R8002.1','C8005.1'),('R8003.1','C8004.1'),
           ('R2101.2','R2102.2'),('R2103.2','R2104.2'),('R2104.2','C465.1'),
           ]
if rail_inputs:pairs=[('R8006.1','C435.1'),('R8007.1','C470.1')]
for a,z in pairs:
    b=p.LoadBoard(str(current));b.BuildConnectivity();qa,qz=pad(b,a),pad(b,z);net=qa.GetNetCode();assert net==qz.GetNetCode()
    ga,gz=group(b,qa),group(b,qz)
    if qz.m_Uuid.AsString() in padset(ga):continue
    geos={l:geometry(b,l,net,oval_caps=rounded) for l in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)}
    for l,(_,boxes) in geos.items():
        polygons=[]
        for zone in b.Zones():
            if zone.GetIsRuleArea() and zone.IsOnLayer(l) and (zone.GetDoNotAllowTracks() or zone.GetDoNotAllowVias()):
                if contour and zone.Outline().OutlineCount()==1:
                    outline=zone.Outline().Outline(0)
                    polygons.append([tuple(outline.CPoint(i)) for i in range(outline.PointCount())])
                    continue
                box=zone.GetBoundingBox();boxes.append((box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom()))
        if contour:geos[l]=[*geos[l],polygons]
    candidates=[]
    outer=qz.GetParentFootprint().GetLayer() if controls else p.F_Cu
    for l in ((p.In3_Cu,) if multi else (p.In3_Cu,p.In2_Cu)):
        seeds=[sorted(terminals(b,ga,k)) for k in (outer,l)]
        if controls and qa.IsOnLayer(outer):
            box=qa.GetBoundingBox()
            # Beyond the pad toe the rounded trace cap maintains copper overlap.
            if a.startswith(('U4.','U5.','U6.')):
                center=qa.GetParentFootprint().GetPosition()
                x,y=tuple(qa.GetPosition())
                if box.GetWidth()>box.GetHeight():toe=(box.GetRight()+85000 if x>center.x else box.GetLeft()-85000,y)
                else:toe=(x,box.GetBottom()+85000 if y>center.y else box.GetTop()-85000)
                seeds[0].append(toe)
                if corners:
                    for edge in (box.GetLeft()+5000,box.GetRight()-5000):
                        for side in (box.GetTop()+5000,box.GetBottom()-5000):
                            if qa.HitTest(p.VECTOR2I(edge,side)):seeds[0].append((edge,side))
                    if rounded:
                        for dx in range(0,80001,20000):
                            for dy in range(0,80001,20000):
                                for edge in (box.GetLeft()+dx,box.GetRight()-dx):
                                    for side in (box.GetTop()+dy,box.GetBottom()-dy):
                                        if qa.HitTest(p.VECTOR2I(edge,side)):seeds[0].append((edge,side))
        if straps:
            # A round track cap overlaps the outer toe by 0.04 mm.
            box=qa.GetBoundingBox();toe=(box.GetRight()+60000,qa.GetPosition().y)
            if qa.GetPosition().x < qa.GetParentFootprint().GetPosition().x:toe=(box.GetLeft()-60000,qa.GetPosition().y)
            seeds[0].append(toe)
        goals=sorted(terminals(b,[qz] if rail_inputs else gz,outer))
        # Minimize only to representative contacts in the destination group.
        goals=sorted(goals,key=lambda pos:math.dist(pos,tuple(qa.GetPosition())))[:8]
        if not goals or not any(seeds):continue
        contacts=[*seeds[0],*seeds[1],*goals];xs,ys=zip(*contacts)
        bounds=[max(.5e6,min(xs)-3e6),max(.5e6,min(ys)-3e6),min(89.5e6,max(xs)+3e6),min(39.5e6,max(ys)+3e6)]
        obj=dict(seeds=seeds,goals={str(i):v for i,v in enumerate(goals)},layers=[geos[k] for k in (outer,l)],through=list(geos.values()),bounds=bounds)
        if assembly:
            pads=[q.GetBoundingBox() for f in b.GetFootprints() for q in f.Pads()]
            holes=[[tuple(t.GetPosition()),tuple(t.GetPosition()),t.GetDrillValue()+400000] for t in b.GetTracks() if isinstance(t,p.PCB_VIA)]
            obj['via_keepouts']=[holes,[(v.GetLeft(),v.GetTop(),v.GetRight(),v.GetBottom()) for v in pads]]
        stack=[outer,l]
        if multi:
            stack.extend([p.In2_Cu,p.B_Cu if outer==p.F_Cu else p.F_Cu])
            obj['layers']=[geos[k] for k in stack]
            obj['seeds']=seeds+[sorted(terminals(b,ga,k)) for k in stack[2:]]
            obj['grid_nm']=200000 if perimeter and not relief else 100000
            if perimeter:obj['bounds']=[500000,500000,89500000,39500000]
        if power:
            obj.update(trace_width_nm=500000,via_nm=650000)
            if not rail_inputs:obj['bounds']=[min(xs)-3e6,min(ys)-3e6,max(xs)+3e6,max(ys)+3e6]
        sol=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('phy_bias_paths.py'))],input=json.dumps(obj),capture_output=True,text=True,check=True).stdout)
        if sol:
            path=sol['path'];length=sum(math.dist(u[1:],v[1:]) for u,v in zip(path,path[1:]))/1e6
            transitions=sum(u[0]!=v[0] for u,v in zip(path,path[1:]))
            if power and (length>(35 if rail_inputs else 20) or transitions>2):continue
            candidates.append((length+2*transitions,length,l,path))
    accepted=False
    for _,length,inner,path in sorted(candidates):
        candidate=p.LoadBoard(str(current));new=[]
        for (l,x,y),(k,u,v) in zip(path,path[1:]):
            if l==k:
                t=p.PCB_TRACK(candidate);t.SetLayer(stack[l] if multi else (outer,inner)[l]);t.SetWidth(500000 if power else 200000);t.SetStart(p.VECTOR2I(x,y));t.SetEnd(p.VECTOR2I(u,v))
            else:
                assert (x,y)==(u,v)
                t=p.PCB_VIA(candidate);t.SetWidth(650000 if power else 450000);t.SetDrill(300000 if power else 200000);t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetPosition(p.VECTOR2I(x,y))
            t.SetNetCode(net);candidate.Add(t);new.append(t.m_Uuid.AsString())
        suffix=(z+'-' if power else '')+a
        folder=root/'runs'/(folder_prefix+'-'+suffix);folder.mkdir(exist_ok=True)
        for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
        dest=folder/src.name;p.ZONE_FILLER(candidate).Fill(candidate.Zones());p.SaveBoard(str(dest),candidate)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(dest)],check=True,capture_output=True)
        delta=introduced(prior,json.loads((folder/'drc.json').read_text()))
        saved=p.LoadBoard(str(dest));pres=verify_preservation(original,saved)
        if delta or padset(group(saved,pad(saved,a)))!=padset(ga)|padset(gz):continue
        assert not screen(saved)
        records.append(dict(pair=[a,z],net=qa.GetNetname(),length_mm=length,inner=saved.GetLayerName(inner),added=new));current=dest;accepted=True;break
    print(a,z,len(candidates),accepted,flush=True)
    if not accepted:held.append([a,z])
    (root/(report_name+'.json')).write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),records=records,held=held,assembly_ready=False),indent=2)+'\n')
os._exit(0)
