"""Preserve each positive terminal and rotate a bypass to obtain a manufacturable ground return."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_power_leg import route_leg
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
source=root/'runs/rotated-bent-plane-C412/phy-joint.kicad_pcb';current=source;digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest();meta=json.loads((source.parent/'output-legs.json').read_text());assert digest(source)==meta['board_sha256']
records=[];failed=[]
def pin(b,ref,num):return b.FindFootprintByReference(ref).FindPadByNumber(num)
for name in ('C431','C432','C421','C422','C483','C470'):
    limits={};win=False
    for rotation in (180,90,270):
        board=p.LoadBoard(str(current));prior=p.LoadBoard(str(current));fp=board.FindFootprintByReference(name)
        a,z=(fp.FindPadByNumber(n) for n in ('1','2'));anchor=a.GetPosition();old=fp.GetPosition();side=fp.GetLayer()
        fp.SetOrientationDegrees(fp.GetOrientationDegrees()+rotation);fp.Move(anchor-a.GetPosition());assert a.GetPosition()==anchor
        court=fp.GetCourtyard(side)
        other=[f for f in board.GetFootprints() if f.GetReference()!=name and f.GetLayer()==side]
        if any(court.Collide(f.GetCourtyard(side),50000) for f in other) or screen(board):
            limits[rotation]='courtyard';continue
        pth=[q for f in board.GetFootprints() if f.GetReference()!=name for q in f.Pads() if q.GetAttribute() in (p.PAD_ATTRIB_PTH,p.PAD_ATTRIB_NPTH)]
        if any(court.Collide(q.GetEffectiveShape(side),50000) for q in pth):
            limits[rotation]='through-hole body';continue
        positions=[tuple(z.GetPosition())]
        for x,y in ((150000,0),(-150000,0),(0,150000),(0,-150000)):
            pos=z.GetPosition()+p.VECTOR2I(x,y)
            if z.HitTest(pos):positions.append(tuple(pos))
        w=600000 if name in ('C431','C432','C421','C422') else 300000
        reached=None
        for tap in positions:
            report=route_leg(board,'GND',tap,side,tap,p.In4_Cu if side==p.B_Cu else p.In1_Cu,w,2.4,shifted=True)
            if report['connected']:reached=report;break
        if not reached:
            limits[rotation]='two return barrels unreachable';continue
        folder=root/'runs'/('rotated-cap-gnd-pivot-'+name+'-'+str(rotation));folder.mkdir(exist_ok=True)
        for cfg in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):shutil.copy2(current.parent/cfg,folder/cfg)
        out=folder/source.name;p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(out),board)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
        delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
        if delta:
            limits[rotation]=delta;continue
        saved=p.LoadBoard(str(out));guard=verify_preservation(prior,saved)
        ground={t.m_Uuid.AsString() for t in saved.GetConnectivity().GetConnectedItems(pin(saved,'U4','69'))}
        assert pin(saved,name,'2').m_Uuid.AsString() in ground
        row=dict(name=name,rotation=rotation,original_positive_nm=tuple(anchor),component_movement_mm=(fp.GetPosition()-old).EuclideanNorm()/1e6,width_mm=w/1e6,ground=reached,groups_preserved=guard['existing_connected_pad_groups_preserved'])
        records.append(row);current=out;meta['board_sha256']=digest(out);meta['pivoted_ground_returns']=records
        (folder/'output-legs.json').write_text(json.dumps(meta,indent=2)+'\n')
        win=True;print(name,rotation,flush=True);break
    if not win:failed.append(dict(part=name,angles=limits))
(root/'rotated-pmic-cap-ground-pivots.json').write_text(json.dumps(dict(source_sha256=digest(source),board=str(current.relative_to(root)),sha256=digest(current),records=records,failed=failed,assembly_ready=False),indent=2)+'\n');print(len(records),len(failed),flush=True);os._exit(0)
