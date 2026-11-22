"""Move a physically unjoined escape barrel outside the package solder land, keeping its dimensions."""
from pathlib import Path
import hashlib
import math
import sys
import json
import shutil
import subprocess

import pcbnew as p

from pcb_bounds import inflated_box
from pcb_power_leg import make,barrel
from pcb_preservation import verify_preservation
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
joint="--plan-return-pair" in sys.argv
paired="--existing-return" in sys.argv or joint
cp=json.loads((root/("layout-bga-referenced-barrel.json" if paired else "layout-command-ca1.json")).read_text())
land_review=json.loads((root/("ddr-referenced-escape-land-proximity.json" if paired else "ddr-escape-land-proximity.json")).read_text())
src=root/cp["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest()==land_review["board_sha256"]==cp["sha256"]
b=p.LoadBoard(str(src));b.BuildConnectivity()
all_objs=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
idof=lambda obj:obj.m_Uuid.AsString()
via_index={idof(t):t for t in b.GetTracks() if isinstance(t,p.PCB_VIA)}
layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
references={p.F_Cu:p.In1_Cu,p.In2_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu,p.B_Cu:p.In4_Cu}
planes={l:next(z.GetFilledPolysList(l) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(l)) for l in set(references.values())}
zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
gref=b.FindFootprintByReference("U4").FindPadByNumber("69")
gids={idof(t) for t in b.GetConnectivity().GetConnectedItems(gref)}
gpos=[tuple(v.GetPosition()) for key,v in via_index.items() if key in gids]
moved=[];trials=[]
for row in land_review["rows"]:
    if not row["drill_intersects_land"]:continue
    name=row["pad"].split(".")[1]
    land=b.FindFootprintByReference("U1").FindPadByNumber(name)
    code=land.GetNetCode()
    original=via_index[row["uuid"]]
    seen={idof(o) for o in b.GetConnectivity().GetConnectedItems(land)}
    if row["uuid"] not in seen:continue
    pin=tuple(land.GetPosition())
    oldat=tuple(original.GetPosition())
    nearest=[o for o in all_objs if inflated_box(o,3000000 if paired else 1850000).Contains(land.GetPosition()) and idof(o)!=idof(original)]
    obstacles={l:[(o,o.GetEffectiveShape(l),o.GetBoundingBox()) for o in nearest if o.IsOnLayer(l) and o.GetNetCode()!=code] for l in layers}
    pads=[o.GetEffectiveShape(o.GetParentFootprint().GetLayer()) for o in nearest if isinstance(o,p.PAD)]
    holes=[o.GetEffectiveHoleShape() for o in nearest if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    guards=[]
    for o in nearest:
        if not isinstance(o,p.PCB_TRACK) or isinstance(o,p.PCB_VIA) or o.GetNetCode()==code or o.GetLayer() not in references:continue
        if not o.GetNetname().startswith(("LPDDR4_","USB_","EMMC_","SOC_EMMC_","ETH_","PHY_","SOC_USB_","MUX_","WIFI_")):continue
        poly=p.SHAPE_POLY_SET();o.TransformShapeToPolygon(poly,o.GetLayer(),200000,500,p.ERROR_OUTSIDE)
        poly.BooleanIntersection(planes[references[o.GetLayer()]])
        guards.append(poly)
    found=[];clear_positions=0;safe_sites=[]
    for dx in range(-24 if paired else -15,25 if paired else 16):
        for dy in range(-24 if paired else -15,25 if paired else 16):
            if not 450000<=math.hypot(dx,dy)*100000<=(2400000 if paired else 1450000):continue
            site=pin[0]+dx*100000,pin[1]+dy*100000
            if paired and not joint and not any(math.dist(site,g)<=1000000 for g in gpos):continue
            via=barrel(b,site,code)
            sh=via.GetEffectiveShape(p.F_Cu);hole=via.GetEffectiveHoleShape();bb=inflated_box(via,260000)
            if any(sh.Collide(pad,100000) for pad in pads):continue
            if any(sh.Collide(h,252000) for h in holes):continue
            if any(bb.Intersects(bounds) and (sh.Collide(geo,202000) or hole.Collide(geo,252000)) for l in layers for o,geo,bounds in obstacles[l]):continue
            if any(z.Collide(sh,0) for z in zones) or any(guard.Collide(p.VECTOR2I(*site),430000) for guard in guards):continue
            clear_positions+=1;safe_sites.append(site)
            # Keep the pre-existing ultra-short terminal neck, extending it with a full-width trace.
            sx,sy=site[0]-oldat[0],site[1]-oldat[1];diag=min(abs(sx),abs(sy))
            vx,vy=int(math.copysign(diag,sx)),int(math.copysign(diag,sy))
            for elbow in ((oldat[0]+vx,oldat[1]+vy),(site[0]-vx,site[1]-vy)):
                paths=[make(b,a,z,200000,code,p.F_Cu) for a,z in zip((oldat,elbow),(elbow,site)) if a!=z]
                if any(inflated_box(t,260000).Intersects(bounds) and t.GetEffectiveShape(p.F_Cu).Collide(geo,202000) for t in paths for o,geo,bounds in obstacles[p.F_Cu]):continue
                if any(t.GetEffectiveShape(p.F_Cu).Collide(h,252000) for t in paths for h in holes):continue
                found.append((sum(t.GetLength() for t in paths),site,elbow));break
    trials.append({"pad":row["pad"],"safe_barrel_sites":clear_positions,"positions_nm":safe_sites,"joined_sites":len(found)})
    if joint:
        trials[-1]["joined_options"]=[{"length_mm":w/1e6,"via_nm":site,"elbow_nm":elbow,"tip_nm":oldat} for w,site,elbow in found]
        continue
    if not found:continue
    _,site,elbow=min(found)
    original.SetPosition(p.VECTOR2I(*site))
    for a,z in zip((oldat,elbow),(elbow,site)):
        if a==z:continue
        line=make(b,a,z,200000,code,p.F_Cu);b.Add(line);all_objs.append(line)
    moved.append({"pad":row["pad"],"uuid":row["uuid"],"via_site_nm":site,"tail_start_nm":oldat})
    b.BuildConnectivity()
out={"parent_sha256":cp["sha256"],"moved":moved,"trials":trials,"adopted":False}
if moved:
    folder=root/("runs/bga-existing-returns" if paired else "runs/bga-ordinary-barrels");folder.mkdir(exist_ok=True)
    for f in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):shutil.copyfile(src.parent/f,folder/f)
    file=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(file)],capture_output=True,check=True)
    drc=json.loads((folder/"drc.json").read_text());out.update(sha256=hashlib.sha256(file.read_bytes()).hexdigest(),board=str(file.relative_to(root)),new_drc=introduced(json.loads((src.parent/"drc.json").read_text()),drc))
(root/("bga-joint-return-sites.json" if joint else "bga-existing-returns.json" if paired else "bga-ordinary-barrels.json")).write_text(json.dumps(out,indent=2)+"\n")
print(len(moved),sum(t["safe_barrel_sites"] for t in trials))
