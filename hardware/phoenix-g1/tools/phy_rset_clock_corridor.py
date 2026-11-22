"""Reform PHY crystal traces on their existing layers around a reserved RSET via."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
current='--current' in sys.argv
exact='--exact' in sys.argv or current
meta=json.loads((root/('layout-cpu-load-sense.json' if current else 'layout-emmc-pullups.json' if exact else 'layout-usb-shell.json')).read_text());src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
sites=[(59700000,32900000),(59800000,31000000)]
plans=[('PHY_XIN',p.B_Cu,(59875000,31000000),(61250000,34825000),None),
       ('PHY_XOUT',p.F_Cu,(59410000,31555000),(57825000,33025000),{'136afc0e-de08-4fed-afdf-7437906822cb','d4565017-8643-42c8-8c39-a4b8bdfeb97c','3f56d0f7-484e-4bfe-9672-a7d36ffa2dc5'})]
def switch_gap(board,parts,layer):
    switch=[t.GetEffectiveShape(layer) for t in board.GetTracks() if t.GetNetname()=='PHY_SW' and t.IsOnLayer(layer)]
    switch.extend(q.GetEffectiveShape(layer) for f in board.GetFootprints() for q in f.Pads() if q.GetNetname()=='PHY_SW' and q.IsOnLayer(layer))
    if not switch:return None
    lo,hi=0,15000000
    while hi-lo>1000:
        mid=(lo+hi)//2
        if any(t.GetEffectiveShape(layer).Collide(s,mid) for t in parts for s in switch):hi=mid
        else:lo=mid
    return lo
results=[]
for site in sites:
    b=p.LoadBoard(str(src));records=[];removed=set();trial=dict(site_nm=site,signals=records)
    results.append(trial)
    for net,layer,a,z,ids in plans:
        orig=[t for t in b.GetTracks() if t.GetNetname()==net and t.GetLayer()==layer and not isinstance(t,p.PCB_VIA) and (ids is None or t.m_Uuid.AsString() in ids)]
        origlen=sum(t.GetLength() for t in orig)
        assert orig and len({t.GetWidth() for t in orig})==1
        width=orig[0].GetWidth();margin=switch_gap(b,orig,layer)
        for t in orig:removed.add(t.m_Uuid.AsString());b.Remove(t)
        code=b.GetNetcodeFromNetname(net);obs,pads=geometry(b,layer,code,oval_caps=True);obs.append([site,site,450000])
        areas=[v.Outline().Outline(i) for v in b.Zones() if v.GetIsRuleArea() and v.IsOnLayer(layer) and v.GetDoNotAllowTracks() for i in range(v.Outline().OutlineCount())]
        polys=[[tuple(k.CPoint(i)) for i in range(k.PointCount())] for k in areas]
        req=dict(grid_nm=25000,bounds=[56000000,28500000,63000000,36500000],layers=[[obs,pads,polys]],through=[],via_keepouts=[[],[]],start=[[a]],end=[[z]],width_nm=width)
        if exact:
            from phy_exact_clock_grid import solve
            line=solve(b,net,layer,a,z,width,site);path={'path':[(0,x,y) for x,y in line]} if line else {}
        else:path=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('control_board_grid.py'))],input=json.dumps(req),text=True,capture_output=True,check=True).stdout)
        info=dict(net=net,original_mm=origlen/1e6,original_switch_gap_nm=margin);records.append(info)
        if not path:info['result']='no_path';break
        points=[p.VECTOR2I(x,y) for _,x,y in path['path']];parts=[]
        for u,v in zip(points,points[1:]):
            t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(width);t.SetStart(u);t.SetEnd(v);t.SetNetCode(code);parts.append(t)
        length=sum(t.GetLength() for t in parts);gap=switch_gap(b,parts,layer);info.update(length_mm=length/1e6,switch_gap_nm=gap)
        if length>origlen or (margin is not None and gap<margin):
            info['result']='exceeds_original_length_or_switch_proximity';break
        for t in parts:b.Add(t)
        info['result']='passed_geometry'
    else:
        folder=root/'runs'/(('phy-rset-current-' if current else 'phy-rset-exact-' if exact else 'phy-rset-clock-')+str(site[0]));folder.mkdir(exist_ok=True)
        for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/n,folder/n)
        out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
        delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));trial['delta']=delta
        if not delta:
            saved=p.LoadBoard(str(out));assert not screen(saved)
            trial.update(preservation=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=removed),board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest())
(root/('phy-rset-current-corridor.json' if current else 'phy-rset-exact-corridor.json' if exact else 'phy-rset-clock-corridor.json')).write_text(json.dumps(dict(parent_sha256=meta['sha256'],trials=results,oscillator_qualified=False),indent=2)+'\n')
print([r['signals'] for r in results],flush=True);os._exit(0)
