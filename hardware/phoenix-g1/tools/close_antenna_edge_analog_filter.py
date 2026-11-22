"""Join the relocated USB analog supply link to its existing output-capacitor bank."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
import native_front_splice as router
from pcb_preservation import verify_preservation
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
ref="R1602" if "--1v8" in sys.argv else "R1601"
cp=json.loads((root/("rf-edge-"+ref.lower()+"-recovery.json")).read_text())["result"][0]
source=root/cp["board"]
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp["sha256"]
board=p.LoadBoard(str(source))
def pin(b,ref,n):return b.FindFootprintByReference(ref).FindPadByNumber(n)
q=pin(board,ref,"2")
router.side=q.GetParentFootprint().GetLayer()
net=q.GetNetname()
pos=tuple(q.GetPosition())
caps=[(math.dist(pos,tuple(c.GetPosition())),f.GetReference(),c) for f in board.GetFootprints() if f.GetReference().startswith("C") for c in f.Pads() if c.GetNetCode()==q.GetNetCode()]
attempts=[]
folder=root/"runs"/("rf-edge-"+ref.lower()+"-load");folder.mkdir(exist_ok=True)
for name in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):
    shutil.copy2(source.parent/name,folder/name)
final=None
for distance,name,cap in sorted(caps):
    if distance>4600000:continue
    path,info=router.recover(board,[(pos,tuple(cap.GetPosition()),300000,q.GetNetCode())],net,None)
    attempts.append(dict(sink=name,distance_mm=distance/1e6,search=info))
    if not path:continue
    added=[router.wire(board,a,z,q.GetNetCode(),300000) for a,z in zip(path,path[1:])]
    for t in added:board.Add(t)
    out=folder/source.name
    p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(out),board)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((source.parent/"drc.json").read_text()),json.loads((folder/"drc.json").read_text()))
    saved=p.LoadBoard(str(out))
    prev=p.LoadBoard(str(source));guard=verify_preservation(prev,saved)
    match={k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(pin(saved,ref,"2"))}
    assert pin(saved,name,cap.GetNumber()).m_Uuid.AsString() in match
    if not delta:
        final=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),sink=name,width_mm=.30,route_mm=info["length_mm"],physical_groups_preserved=guard["existing_connected_pad_groups_preserved"],new_drc=delta)
        break
    attempts[-1]["introduced_drc"]=delta
    for t in added:board.Remove(t)
(root/("rf-edge-"+ref.lower()+"-load.json")).write_text(json.dumps(dict(parent_sha256=cp["sha256"],attempts=attempts,result=final,assembly_ready=False),indent=2)+"\n")
print(attempts,final,flush=True);os._exit(0)
