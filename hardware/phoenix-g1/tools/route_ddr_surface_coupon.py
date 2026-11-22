"""Evaluate via-to-via byte-lane paths on B.Cu over filled In4 GND. Layout coupon only."""
import hashlib,json,math,os,shutil,subprocess,sys
from phy_corridor_path import geometry
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
mesh='--core-ground-mesh' in sys.argv
command='--command-address' in sys.argv
cp=json.loads((root/('layout-emmc-data-power.json' if command else 'layout-core-ground-mesh.json' if mesh else 'layout-opposite-bypass.json')).read_text());src=root/cp['board']
info=json.loads((root/('ddr-reference-emmc-bank.json' if command else 'ddr-reference-core-ground-mesh.json' if mesh else 'ddr-reference-corridors.json')).read_text())
assert cp['sha256']==info['source_sha256']==hashlib.sha256(src.read_bytes()).hexdigest()
b=p.LoadBoard(str(src))
front='--front' in sys.argv
inner='--inner' in sys.argv
face=(p.In2_Cu if front else p.In3_Cu) if inner else (p.F_Cu if front else p.B_Cu)
refplane=p.In1_Cu if front else p.In4_Cu
gnd=next(z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname()=='GND' and z.IsOnLayer(refplane))
pads=[q for f in b.GetFootprints() for q in f.Pads() if q.IsOnLayer(face)]
bodies=[z for z in b.Zones() if z.GetIsRuleArea() and z.IsOnLayer(face) and z.GetDoNotAllowTracks()]
def route_points(a,z,direction,portion):
    x,y=z-a
    if not x or not y:return [a,z]
    sx,sy=1 if x>0 else -1,1 if y>0 else -1
    diagonal=min(abs(x),abs(y))
    diag=p.VECTOR2I(sx*diagonal,sy*diagonal);straight=z-a-diag
    first,last=(straight,diag) if direction else (diag,straight)
    shift=p.VECTOR2I(round(first.x*portion),round(first.y*portion))
    pts=[a,a+shift,a+shift+last,z]
    return [v for i,v in enumerate(pts) if not i or v!=pts[i-1]]
def reference(t,a,z):
    u,v=t.GetStart(),t.GetEnd();delta=v-u;length=t.GetLength()
    count=math.ceil(length/50000)
    for i in range(count+1):
        x=u.x+delta.x*i/count;y=u.y+delta.y*i/count
        if min(math.hypot(x-k.x,y-k.y) for k in (a,z))<600000:continue
        for offset in (-100000,0,100000):
            point=p.VECTOR2I(round(x-delta.y*offset/length),round(y+delta.x*offset/length))
            if not gnd.HitTestFilledArea(refplane,point):return False
    return True
all_data='--all-data' in sys.argv
maze='--byte-b1-maze' in sys.argv or all_data or command
stage='ddr-byte-b1-front' if front else 'ddr-byte-b1-maze' if maze else 'ddr-surface-coupon'
if inner:stage+='-inner'
if all_data:stage+='-all-data'
if mesh:stage+='-core-mesh'
if command:stage='ddr-command-'+b.GetLayerName(face).replace('.','-').lower()
compact='--compact' in sys.argv
if compact:stage+='-compact'
priority_a5='--reserve-a5' in sys.argv
if priority_a5:stage+='-a5-first'
shielded='--avoid-exp-gpio' in sys.argv
if shielded:stage+='-isolated'
parallel_guard='--avoid-parallel' in sys.argv
if parallel_guard:stage+='-broadside'
def polygon_points(line):return [tuple(line.CPoint(i)) for i in range(line.PointCount())]
poly=gnd.GetFilledPolysList(refplane)
plane=[[polygon_points(poly.Outline(i)),[polygon_points(poly.Hole(i,j)) for j in range(poly.HoleCount(i))]] for i in range(poly.OutlineCount())]
chosen=[];held=[];grid_results={}
rows=[r for r in info['nets'] if r['escape_via_counts']==[1,1] and ('_DQ' in r['net'] and '_DQS' not in r['net'] or '_DM' in r['net'])]
if command:
    rows=[r for r in info["nets"] if r["escape_via_counts"]==[1,1] and r["net"].startswith(("LPDDR4_A","LPDDR4_CKE","LPDDR4_CS"))]
for row in sorted(rows,key=lambda r:(priority_a5 and r['net']!='LPDDR4_A5_A',min(len(k['obstacle_nets']) for k in r['paths'] if k['layer']==('F.Cu' if front else 'B.Cu')))):
    net=row['net'];code=b.GetNetcodeFromNetname(net);a,z=[p.VECTOR2I(*v) for v in row['via_nm']]
    box=p.BOX2I(a,z-a);box.Normalize();box.Inflate(900000)
    shapes=[k.GetEffectiveShape(face) for k in pads+list(b.GetTracks()) if k.GetNetCode()!=code and k.IsOnLayer(face) and box.Intersects(k.GetBoundingBox())]
    accepted=False
    paths=[]
    if maze:
        if not command and not all_data and net not in {f'LPDDR4_DQ{i}_B' for i in range(8,16)}|{'LPDDR4_DM1_B'}:continue
        exclusions=[polygon_points(k.Outline().Outline(i)) for k in bodies for i in range(k.Outline().OutlineCount())]
        req=dict(via_nm=row['via_nm'],plane=plane,geometry=[*geometry(b,face,code,oval_caps=True),exclusions])
        if compact:req.update(compact_45=True,reference_half_width_nm=200000)
        if shielded:
            # Reserve the projected copper of the demonstrated broadside aggressor
            # across the thin central dielectric, including existing trace width.
            req["geometry"][0].extend([tuple(t.GetStart()),tuple(t.GetEnd()),t.GetWidth()]
                                      for t in b.GetTracks() if not isinstance(t,p.PCB_VIA)
                                      and t.GetLayer()==p.In2_Cu and t.GetNetname()=="EXP_GPIO1")
        if parallel_guard:
            req["projected_foreign"]=[[tuple(t.GetStart()),tuple(t.GetEnd()),t.GetWidth()]
                                      for t in b.GetTracks() if not isinstance(t,p.PCB_VIA)
                                      and t.GetLayer()==p.In2_Cu]
        sol=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('ddr_plane_grid.py'))],input=json.dumps(req),text=True,capture_output=True,check=True).stdout)
        grid_results[net]={k:v for k,v in sol.items() if k!='path'}
        if 'path' in sol:paths.append([p.VECTOR2I(*pt) for pt in sol['path']])
    else:
        paths=[route_points(a,z,direction,portion/100) for portion in sorted(range(101),key=lambda i:abs(i-50)) for direction in (False,True)]
    for pts in paths:
        items=[]
        for u,v in zip(pts,pts[1:]):
            t=p.PCB_TRACK(b);t.SetNetCode(code);t.SetLayer(face);t.SetWidth(200000);t.SetStart(u);t.SetEnd(v)
            shape=t.GetEffectiveShape(face)
            if any(shape.Collide(o,200000) for o in shapes):break
            if any(t.GetBoundingBox().Intersects(k.GetBoundingBox()) for k in bodies):break
            if not reference(t,a,z):break
            items.append(t)
        else:
            for t in items:b.Add(t)
            chosen.append(dict(net=net,path_nm=[tuple(v) for v in pts],routed_length_mm=sum(t.GetLength() for t in items)/1e6));accepted=True;break
    if not accepted:held.append(net)
folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
for n in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):shutil.copy2(src.parent/n,folder/n)
out=src
if chosen:
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    original=json.loads((src.parent/'drc.json').read_text());current=json.loads((folder/'drc.json').read_text())
    assert not introduced(original,current)
    saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved);assert not screen(saved)
    for rec in chosen:
        a,z=[next(q for q in saved.FindFootprintByReference(r).Pads() if q.GetNetname()==rec['net']) for r in ('U1','U2')]
        assert z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(a)}
        rec['pair']=['U1.'+a.GetNumber(),'U2.'+z.GetNumber()]
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],layout_only=True,route_layer=b.GetLayerName(face),reference_layer=b.GetLayerName(refplane),grid_results=grid_results,routes=chosen,held=held,impedance_qualified=False,timing_qualified=False,assembly_ready=False),indent=2)+'\n')
print(len(chosen),len(held),flush=True);os._exit(0)
