"""Join adjacent same-supply eMMC balls with short, surface-only copper on the saved board."""
import hashlib,itertools,json,math,os,shutil,subprocess,sys
import native_front_splice as bend
from pathlib import Path
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
memory_rails="--memory-rail-offsets" in sys.argv
storage_ground="--storage-ground-neighbors" in sys.argv
ground=storage_ground or "--soc-ground-neighbors" in sys.argv or "--memory-ground-neighbors" in sys.argv
memory_ground="--memory-ground-neighbors" in sys.argv
core="--soc-core-neighbors" in sys.argv
soc="--soc-analog-perimeter" in sys.argv
ram="--ram-supply-perimeter" in sys.argv
chip="U8001" if storage_ground else "U2" if memory_ground or memory_rails else "U1" if soc or core or ground else "U2" if ram else "U8001"
contour="--perimeter" in sys.argv or soc or ram
base="layout-ground-land-offsets.json" if memory_rails else "layout-soc-ground-neighbors.json" if memory_ground or storage_ground else "layout-soc-core-neighbors.json" if ground else "layout-usb-direction-complete.json" if soc or ram or core else "layout-emmc-adjacent-supply.json" if contour else "layout-usb-analog-1v8.json"
cp=json.loads((root/base).read_text());source=root/cp["board"]
assert cp["sha256"]==hashlib.sha256(source.read_bytes()).hexdigest()
label="memory-rail-offsets" if memory_rails else "storage-ground-neighbors" if storage_ground else "memory-ground-neighbors" if memory_ground else "soc-ground-neighbors" if ground else "soc-core-neighbors" if core else "soc-analog-perimeter" if soc else "ram-supply-perimeter" if ram else "emmc-perimeter-supply" if contour else "emmc-adjacent-supply-lands"
folder=root/"runs"/label;folder.mkdir(exist_ok=True)
for name in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):shutil.copy2(source.parent/name,folder/name)
b=p.LoadBoard(str(source));f=b.FindFootprintByReference(chip);l=f.GetLayer()
pads=list(f.Pads())
foreign=list(b.GetTracks())+[q for fp in b.GetFootprints() for q in fp.Pads()]
candidates=[]
for a,z in itertools.combinations(pads,2):
    rails=('+1V1_LPDDR4','VDDQ_LPDDR4','+1V8_SYS') if memory_rails else ('GND',) if ground else ('VDD_LOGIC','VDD_CPU','VDD_GPU','VDD_NPU','+1V1_LPDDR4') if core else ('VCCA1V8_IMAGE','VDDA0V9_IMAGE','VCCA_1V8','VCCA1V8_PMU','VDDA_0V9','VDDA0V9_PMU') if soc else ('+1V1_LPDDR4','VDDQ_LPDDR4','+1V8_SYS') if ram else ('EMMC_IO_1V8','EMMC_3V3')
    if a.GetNetname() not in rails or a.GetNetCode()!=z.GetNetCode(): continue
    distance=(a.GetPosition()-z.GetPosition()).EuclideanNorm()
    if distance<=(1800000 if contour or storage_ground or memory_ground or memory_rails else 1000000):candidates.append((distance,a.GetNumber(),z.GetNumber(),a,z))
accepted=[];rejected=[]
for dist,_,__,a,z in sorted(candidates,key=lambda e:e[:3]):
    b.BuildConnectivity()
    if z.m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(a)}:continue
    if contour:
        bend.side=l
        surface_width=500000 if soc or ram else 300000
        args=(tuple(a.GetPosition()),tuple(z.GetPosition()),surface_width,a.GetNetCode())
        pts,diag=bend.recover(b,[args],a.GetNetname(),None,search_all_obstacles=True,minimum_clearance_nm=202000 if soc or ram else None)
        if not pts:
            rejected.append(dict(balls=[a.GetNumber(),z.GetNumber()],diagnosis=diag))
            continue
        if diag['length_mm']>3.0:
            rejected.append(dict(balls=[a.GetNumber(),z.GetNumber()],length_mm=diag['length_mm']))
            continue
        wires=[bend.wire(b,x,y,a.GetNetCode(),surface_width) for x,y in zip(pts,pts[1:])]
        for wire in wires:b.Add(wire)
        accepted.append(dict(pair=[chip+"."+a.GetNumber(),chip+"."+z.GetNumber()],net=a.GetNetname(),width_mm=surface_width/1e6,length_mm=diag['length_mm']))
        continue
    diff=z.GetPosition()-a.GetPosition()
    unit=(diff.x/dist,diff.y/dist)
    local_box=inflated_box(a,round(dist)+750000)
    local_copper=[o for o in foreign if o.GetNetCode()!=a.GetNetCode() and local_box.Intersects(o.GetBoundingBox())]
    for width,side_offset in ([(w,dy) for w in ((500000,400000,300000) if ground else (500000,)) for dy in (0,-25000,25000,-50000,50000,-75000,75000,-100000,100000)] if core or ground or memory_rails else [(w,0) for w in (400000,350000,300000)]):
        t=p.PCB_TRACK(b);t.SetNetCode(a.GetNetCode());t.SetWidth(width);t.SetLayer(l)
        # End inside each ball land; avoid an artificial flare beyond the lands.
        inset=min(100000,int(dist/4))
        offset=p.VECTOR2I(round(unit[0]*inset),round(unit[1]*inset))
        normal=p.VECTOR2I(round(-unit[1]*side_offset),round(unit[0]*side_offset))
        t.SetStart(a.GetPosition()+offset+normal);t.SetEnd(z.GetPosition()-offset+normal)
        sh=t.GetEffectiveShape(l);bb=inflated_box(t,350000)
        nearby=[o for o in local_copper if bb.Intersects(o.GetBoundingBox())]
        if any((o.IsOnLayer(l) and sh.Collide(o.GetEffectiveShape(l),200000)) or (isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x) and sh.Collide(o.GetEffectiveHoleShape(),250000) for o in nearby):continue
        assert all(sh.Collide(q.GetEffectiveShape(l),0) for q in (a,z))
        b.Add(t);foreign.append(t);accepted.append(dict(pair=[chip+"."+a.GetNumber(),chip+"."+z.GetNumber()],net=a.GetNetname(),width_mm=width/1e6,length_mm=t.GetLength()/1e6));break
    else:rejected.append([a.GetNumber(),z.GetNumber()])
target=folder/source.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(target),b)
subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(target)],capture_output=True,check=True)
delta=introduced(json.loads((source.parent/"drc.json").read_text()),json.loads((folder/"drc.json").read_text()))
saved=p.LoadBoard(str(target));original=p.LoadBoard(str(source));pres=verify_preservation(original,saved);fp=saved.FindFootprintByReference(chip)
for row in accepted:
    a,z=(fp.FindPadByNumber(q.split(".")[1]) for q in row["pair"])
    assert z.m_Uuid.AsString() in {q.m_Uuid.AsString() for q in saved.GetConnectivity().GetConnectedItems(a)}
(root/(label+".json")).write_text(json.dumps(dict(parent_sha256=cp["sha256"],board=str(target.relative_to(root)),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),accepted=accepted,rejected=rejected,preservation=pres,new_drc=delta,assembly_ready=False),indent=2)+"\n");print(accepted,delta,flush=True);os._exit(0)
