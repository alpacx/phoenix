"""Try a single-face oscillator tree while reserving access to the bias pin."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
parent=json.loads((root/'layout-regulator-banks.json').read_text());src=root/parent['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==parent['sha256']
current=src;rows=[];retained=[]
for net,capref in [('PHY_XIN','C520'),('PHY_XOUT','C521')]:
    if net!=sys.argv[1]:continue
    b=p.LoadBoard(str(current));retained.append(b);layer=p.F_Cu;code=b.GetNetcodeFromNetname(net)
    old=[k for k in b.GetTracks() if k.GetNetCode()==code];ids={k.m_Uuid.AsString() for k in old}
    widths={k.GetWidth() for k in old if not isinstance(k,p.PCB_VIA)};assert widths
    width=max(widths);limit=sum(k.GetLength() for k in old if not isinstance(k,p.PCB_VIA))
    # Keep the original narrow QFN escape, including its exact endpoint.
    toe=[k for k in old if not isinstance(k,p.PCB_VIA) and k.GetLayer()==layer and k.GetWidth()<width]
    ends={tuple(pt) for k in toe for pt in (k.GetStart(),k.GetEnd())}
    land_u5=next(q for q in b.FindFootprintByReference('U5').Pads() if q.GetNetCode()==code)
    starts=[pt for pt in ends if not land_u5.HitTest(p.VECTOR2I(*pt))]
    for k in old:
        if k not in toe:b.Remove(k)
    ids.difference_update(k.m_Uuid.AsString() for k in toe)
    limit-=sum(k.GetLength() for k in toe)
    obs,pads=geometry(b,layer,code,oval_caps=True)
    obs.append([(59700000,32900000),(59700000,32900000),450000])
    areas=[z.Outline().Outline(i) for z in b.Zones() if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks() for i in range(z.Outline().OutlineCount())]
    polys=[[tuple(k.CPoint(i)) for i in range(k.PointCount())] for k in areas]
    def land(ref):
        q=next(q for q in b.FindFootprintByReference(ref).Pads() if q.GetNetCode()==code);box=q.GetBoundingBox()
        return [(x,y) for x in range(box.GetLeft(),box.GetRight()+1,50000) for y in range(box.GetTop(),box.GetBottom()+1,50000) if q.HitTest(p.VECTOR2I(x,y))]
    req=dict(grid_nm=25000,bounds=[54000000,28500000,64000000,38750000],layers=[[obs,pads,polys]],through=[],via_keepouts=[[],[]],width_nm=width)
    targets=land('Y501');new=[]
    for ref in ('U5',capref):
        req.update(start=[starts if ref=='U5' and starts else land(ref)],end=[targets])
        ans=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('control_board_grid.py'))],input=json.dumps(req),text=True,capture_output=True,check=True).stdout)
        if not ans:break
        path=[p.VECTOR2I(x,y) for _,x,y in ans['path']]
        for u,v in zip(path,path[1:]):
            t=p.PCB_TRACK(b);t.SetStart(u);t.SetEnd(v);t.SetWidth(width);t.SetLayer(layer);t.SetNetCode(code);new.append(t)
            n=max(1,round(t.GetLength()/50000))
            targets.extend((round(u.x+(v.x-u.x)*i/n),round(u.y+(v.y-u.y)*i/n)) for i in range(n+1))
    else:
        if sum(k.GetLength() for k in new)<=limit:
            for t in new:b.Add(t)
            folder=root/'runs'/('front-tree-toe-'+net);folder.mkdir(exist_ok=True)
            for name in ('fp-lib-table','phy-joint.kicad_dru','phy-joint.kicad_pro'):shutil.copy2(current.parent/name,folder/name)
            out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
            subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
            delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
            if not delta:
                saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(current)),saved,replaced_copper=ids);assert not screen(saved)
                rows.append(dict(net=net,length_mm=sum(k.GetLength() for k in new)/1e6,original_mm=limit/1e6,preservation=pres));current=out;continue
    rows.append(dict(net=net,held=True))
(root/('phy-front-tree-toe-'+sys.argv[1]+'.json')).write_text(json.dumps(dict(parent_sha256=parent['sha256'],board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),results=rows,qualified=False),indent=2)+'\n')
print([(r['net'],r.get('length_mm')) for r in rows],flush=True);os._exit(0)
