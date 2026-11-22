"""Find a rear-side route to an existing grounded barrel from the shared CPU bypass returns."""
from pathlib import Path
import json,hashlib,math,subprocess,sys
import pcbnew as p
from phy_corridor_path import geometry
root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
soc="--soc-return" in sys.argv
bulk="--bulk-return" in sys.argv
stage="soc-ground-existing-barrel" if soc else "bulk-ground-existing-barrel" if bulk else "ground-cap-existing-barrel"
pinref=("U1","1F15") if soc else ("C1605","2") if bulk else ("C1609","2")
layer=p.F_Cu if soc else p.B_Cu
ref_labels=["U1.1F15","U1.1G13"] if soc else ["C1605.2"] if bulk else ["C1609.2","C1618.2"]
cp=json.loads((root/("layout-ground-cap-existing-barrel.json" if soc or bulk else "layout-ground-surface-bends.json")).read_text())
src=root/cp["board"];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp["sha256"]
board=p.LoadBoard(str(src));board.BuildConnectivity()
def connected(ref,pin):
    pad=board.FindFootprintByReference(ref).FindPadByNumber(pin)
    return {t.m_Uuid.AsString() for t in board.GetConnectivity().GetConnectedItems(pad)}
group=connected(*pinref);main=connected("U4","69")
starts={tuple(board.FindFootprintByReference(*pinref[:1]).FindPadByNumber(pinref[1]).GetPosition())};ends=[]
for t in board.GetTracks():
    uid=t.m_Uuid.AsString()
    if isinstance(t,p.PCB_VIA) and uid in main:ends.append(tuple(t.GetPosition()))
    if isinstance(t,p.PCB_VIA) or uid not in group or t.GetLayer()!=layer:continue
    a,z=tuple(t.GetStart()),tuple(t.GetEnd());count=math.ceil(t.GetLength()/100000)
    starts.update(tuple(round(i+(j-i)*k/count) for i,j in zip(a,z)) for k in range(count+1))
ends=[xy for xy in ends if min(math.dist(a,xy) for a in starts)<5000000]
req=dict(geometry=geometry(board,layer,board.FindNet("GND").GetNetCode(),oval_caps=True),
    width=250000,sites=sorted(starts)[::1 if bulk else 3],target=ends,limit=6500000)
proc=subprocess.run(["python3",str(Path(__file__).with_name("screen_cpu_launch_corridor.py"))],input=json.dumps(req),text=True,capture_output=True,check=True)
report=json.loads(proc.stdout);report.update(parent_sha256=cp["sha256"],grounded_barrels=len(ends),terminals=req["sites"])
(root/(stage+"-path.json")).write_text(json.dumps(report,indent=2)+"\n");print(report["path"],report["closest"],len(ends))
if report["path"]:
    import shutil
    from collections import Counter
    from pcb_power_leg import make
    from drc_regression import introduced
    from pcb_preservation import verify_preservation
    out=root/'runs'/stage;out.mkdir(exist_ok=True,parents=True);file=out/src.name
    for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
    shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table')
    for a,z in zip(report["path"],report["path"][1:]):board.Add(make(board,a,z,250000,board.FindNet("GND").GetNetCode(),layer))
    p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(file),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(file)],check=True,capture_output=True)
    db=json.loads((out/'drc.json').read_text());delta=introduced(json.loads((src.parent/'drc.json').read_text()),db)
    board=p.LoadBoard(str(file));board.BuildConnectivity()
    grounded=connected("U4","69")
    assert all(board.FindFootprintByReference(s.split(".")[0]).FindPadByNumber(s.split(".")[1]).m_Uuid.AsString() in grounded for s in ref_labels)
    proof=verify_preservation(p.LoadBoard(str(src)),board)
    report.update(board=str(file.relative_to(root)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),drc_delta=delta,preservation=proof,remaining_minimum_joins=len(db["unconnected_items"]))
    (root/(stage+"-path.json")).write_text(json.dumps(report,indent=2)+"\n")
    print(report['remaining_minimum_joins'],delta[:2])
    if not delta and report["remaining_minimum_joins"]==cp["remaining_minimum_joins"]-1:
        opens=cp["open_nets"].copy();groups=opens["GND"];left=next(g for g in groups if ref_labels[0] in g);right=next(g for g in groups if "U4.69" in g)
        opens["GND"]=[g for g in groups if g!=left and g!=right]+[sorted(left+right)]
        pairs=sorted({tuple(sorted(pair)) for pair in cp["verified_pairs"]}|{tuple(sorted((s,"U4.69"))) for s in ref_labels})
        cached={}
        for a,z in pairs:
            if a not in cached:cached[a]=connected(*a.split("."))
            ref,pin=z.split(".")
            assert board.FindFootprintByReference(ref).FindPadByNumber(pin).m_Uuid.AsString() in cached[a],(a,z)
        adopted=dict(board=report["board"],sha256=report["sha256"],parent_sha256=cp["sha256"],verified_pairs=pairs,preservation=proof,open_nets=opens,remaining_minimum_joins=report["remaining_minimum_joins"],new_drc=[],drc_counts=dict(Counter(v["type"] for v in db["violations"])),assembly_ready=False)
        (root/("layout-"+stage+".json")).write_text(json.dumps(adopted,indent=2)+"\n")
