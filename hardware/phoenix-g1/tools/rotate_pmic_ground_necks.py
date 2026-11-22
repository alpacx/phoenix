"""Restore original RK809 perimeter land-to-paddle necks in the placed package coordinate frame."""
from pathlib import Path
import hashlib,itertools,json,math,os,shutil,subprocess
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def read(name):return json.loads((root/(name+'.json')).read_text())
def load(d):
    path=root/d['board'];assert hashlib.sha256(path.read_bytes()).hexdigest()==d['sha256']
    return path,p.LoadBoard(str(path))
source,b=load(read('rotated-pmic-short-plane-returns'))
_,original=load(read('layout-pmic-pwron-filter'))
old=original.FindFootprintByReference('U4');new=b.FindFootprintByReference('U4')
def pin(f,n):return f.FindPadByNumber(n)
def uid(o):return o.m_Uuid.AsString()
oldcenter=old.GetPosition();newcenter=new.GetPosition()
def rotate(v,k):
    x,y=v.x,v.y
    for _ in range(k):x,y=-y,x
    return p.VECTOR2I(x,y)
rot,= [k for k in range(4) if all(newcenter+rotate(pin(old,n).GetPosition()-oldcenter,k)==pin(new,n).GetPosition() for n in ('1','4','17','39'))]
ep_old=[q.GetEffectiveShape(p.F_Cu) for q in old.Pads() if q.GetNumber()=='69']
spec={}
for n in ('14','15','16','17','19','40','47','56','62','63'):
    pad=pin(old,n);sh=pad.GetEffectiveShape(p.F_Cu)
    traces=[t for t in original.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and t.GetLayer()==p.F_Cu and t.GetLength()<1600000 and sh.Collide(t.GetEffectiveShape(p.F_Cu),0) and any(g.Collide(t.GetEffectiveShape(p.F_Cu),0) for g in ep_old)]
    spec[n]=traces
folder=root/'runs/rotated-package-ground-necks';folder.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/file,folder/file)
out=folder/source.name
added={};history=[]
for n,traces in spec.items():
    for t in traces:
        oid=uid(t)
        if oid in added:continue
        newt=p.PCB_TRACK(b);newt.SetNet(b.FindNet('GND'));newt.SetLayer(p.F_Cu);newt.SetWidth(t.GetWidth());newt.SetStart(newcenter+rotate(t.GetStart()-oldcenter,rot));newt.SetEnd(newcenter+rotate(t.GetEnd()-oldcenter,rot));b.Add(newt);added[oid]=newt
baseline=json.loads((source.parent/'drc.json').read_text())
while True:
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(baseline,json.loads((folder/'drc.json').read_text()))
    if not delta:break
    ids={i for row in delta for i in row['items']};conflict=[key for key,t in added.items() if uid(t) in ids]
    history.append(dict(introduced=delta,removed_sources=conflict));assert conflict
    for key in conflict:b.Remove(added.pop(key))
saved=p.LoadBoard(str(out));prior=p.LoadBoard(str(source));guard=verify_preservation(prior,saved)
g=pin(saved.FindFootprintByReference('U4'),'69');ground={uid(k) for k in saved.GetConnectivity().GetConnectedItems(g)}
restored=[n for n in spec if uid(pin(saved.FindFootprintByReference('U4'),n)) in ground]
report=dict(board_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),rotation_quarter_turns=rot,sources={n:[uid(t) for t in ts] for n,ts in spec.items()},restored=restored,retained_source_traces=list(added),rejected=history,preservation=guard,new_drc=delta,assembly_ready=False)
detail=json.loads((source.parent/'output-legs.json').read_text());detail['board_sha256']=report['board_sha256'];detail['restored_package_ground']=report
(folder/'output-legs.json').write_text(json.dumps(detail,indent=2)+'\n')
(root/'rotated-package-ground-necks.json').write_text(json.dumps(report,indent=2)+'\n')
print('restored',restored,'source counts',[(n,len(v)) for n,v in spec.items()],'rejected passes',len(history),flush=True);os._exit(0)
