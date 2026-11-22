"""Release an isolated serialized bus exit by moving the one demonstrated blocking capacitor."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'rotated-left-sda-complete.json').read_text());src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
evidence=json.loads((root/'rotated-left-scl-channel.json').read_text());assert evidence['coupon_sha256']==base['sha256']
original=p.LoadBoard(str(src));trials=[];result=None
for ref,sourcepin in [('C422','10'),('C470','55')]:
    b=p.LoadBoard(str(src));b.BuildConnectivity();f=b.FindFootprintByReference(ref);side=f.GetLayer();pwr,gnd=(f.FindPadByNumber(n) for n in ('1','2'))
    blocker=evidence['circuits'][0]['single_copper_blockers'][ref+'.2'];at=p.VECTOR2I(*blocker['first_site_nm'])
    via=p.PCB_VIA(b);via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetWidth(450000);via.SetDrill(200000);via.SetPosition(at)
    shape=via.GetEffectiveShape(side);drill=via.GetEffectiveHoleShape()
    old=f.GetPosition();angle=f.GetOrientationDegrees();pos=pwr.GetPosition();ps=b.FindFootprintByReference('U4').FindPadByNumber(sourcepin)
    assert ps.GetNetCode()==pwr.GetNetCode()
    old_dist=(pos-ps.GetPosition()).EuclideanNorm()
    objs=[o for o in list(b.GetTracks())+[q for f0 in b.GetFootprints() if f0.GetReference()!=ref for q in f0.Pads()] if inflated_box(o,6600000).Contains(old)]
    obstacles=[(o,o.GetEffectiveShape(side)) for o in objs if o.IsOnLayer(side)]
    courtyards=[fp.GetCourtyard(side) for fp in b.GetFootprints() if fp.GetReference()!=ref and fp.GetLayer()==side and inflated_box(fp,6600000).Contains(old)]
    pths=[q.GetEffectiveShape(side) for q in objs if isinstance(q,p.PAD) and q.GetAttribute() in (p.PAD_ATTRIB_PTH,p.PAD_ATTRIB_NPTH)]
    boardbox=b.GetBoardEdgesBoundingBox();boardbox.Inflate(-250000)
    poses=[]
    for turn in (0,180,90,270):
        f.SetOrientationDegrees(angle+turn)
        for x in range(-13,14):
            for y in range(-13,14):
                f.SetPosition(old+p.VECTOR2I(x*150000,y*150000))
                dist=(pwr.GetPosition()-ps.GetPosition()).EuclideanNorm()
                if dist>old_dist+150000 or (ref=='C470' and (pwr.GetPosition()-pos).EuclideanNorm()>650000):continue
                if any(shape.Collide(q.GetEffectiveShape(side),202000) or drill.Collide(q.GetEffectiveShape(side),252000) for q in f.Pads()):continue
                court=f.GetCourtyard(side)
                if not boardbox.Contains(court.BBox()) or any(court.Collide(c,50000) for c in courtyards+pths):continue
                if any(q.GetNetCode()!=o.GetNetCode() and q.GetEffectiveShape(side).Collide(sh,202000) for q in f.Pads() for o,sh in obstacles):continue
                score=(pwr.GetPosition()-pos).EuclideanNorm()+.35*(f.GetPosition()-old).EuclideanNorm()+.25*dist
                poses.append((score,tuple(f.GetPosition()),angle+turn,dist/1e6))
    trials.append(dict(ref=ref,physical_sites=len(poses),initial_supply_distance_mm=old_dist/1e6))
    for score,xy,theta,dist in sorted(poses)[:20]:
        f.SetPosition(p.VECTOR2I(*xy));f.SetOrientationDegrees(theta)
        folder=root/'runs'/('rotated-scl-release-'+ref);folder.mkdir(exist_ok=True)
        for cfg in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):shutil.copy2(src.parent/cfg,folder/cfg)
        out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
        delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
        if delta:continue
        saved=p.LoadBoard(str(out));guard=verify_preservation(original,saved);assert not screen(saved)
        result=dict(ref=ref,site_nm=tuple(at),center_nm=xy,angle_deg=theta,supply_distance_mm=dist,board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=base['sha256'],preservation=guard,new_drc=delta)
        break
    if result:break
(root/'rotated-scl-cap-release.json').write_text(json.dumps(dict(candidate=result,trials=trials,assembly_ready=False),indent=2)+'\n');print(trials,result and result['ref'],flush=True);os._exit(0)
