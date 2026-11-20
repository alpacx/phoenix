"""Reconcile the saved control-board delta with the separately routed PHY candidate."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from parallel_mechanical_apply_h8104 import apply
from audit_mount_component_reservations import screen

ex=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments'
root=ex/'phy-power-parallel'
def checked(directory,checkpoint):
    data=json.loads((directory/checkpoint).read_text())
    path=directory/data['board']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==data['sha256']
    return path
src=checked(root,'reconciled-mount.json')
control=checked(ex/'pmic-ldo-inputs','working-candidate.json')
old=p.LoadBoard(str(src));board=p.LoadBoard(str(src));donor=p.LoadBoard(str(control))
mount=apply(board)
directory=ex/'control-routing-parallel'
specs=[json.loads((directory/f).read_text()) for f in ['delta.json','lcd-delta.json','ground-vias-delta.json','ram-ground-vias-delta.json','middle-ground-vias-delta.json','right-ground-safe-delta.json']]
pool={t.m_Uuid.AsString():t for t in donor.GetTracks()}
existing={t.m_Uuid.AsString() for t in board.GetTracks()}
added={};removed=[]
for spec in specs:
    for row in spec['tracks']:
        uid=row['uuid'];assert uid in pool and uid not in existing and uid not in added
        source=pool[uid];assert source.GetNetname()==row['net']
        t=source.Duplicate();t.SetUuid(p.KIID(uid));t.SetNetCode(board.GetNetcodeFromNetname(row['net']));board.Add(t);added[uid]=t
folder=root/'runs/reconciled-control';folder.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
out=folder/src.name;prior=json.loads((src.parent/'drc.json').read_text())
for attempt in range(12):
    p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(out),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(prior,json.loads((folder/'drc.json').read_text()))
    if not delta:break
    discard=set()
    for issue in delta:
        ids=set(issue['items'])&added.keys()
        assert ids,issue
        discard.update(ids)
    removed.append(dict(issues=delta,uuids=sorted(discard)))
    for uid in discard:board.Remove(added[uid])
else:raise RuntimeError('Non-convergent differential DRC')
saved=p.LoadBoard(str(out));pres=verify_preservation(old,saved)
def pad(ref):
    r,n=ref.split('.');return saved.FindFootprintByReference(r).FindPadByNumber(n)
audit=json.loads((control.parent/'final-audit.json').read_text())
def connected(pair):
    a,z=pad(pair[0]),pad(pair[1])
    return z.m_Uuid.AsString() in {t.m_Uuid.AsString() for t in saved.GetConnectivity().GetConnectedItems(a)}
historic=json.loads((root/'integrated-fixture-trunk.json').read_text())['verified_pairs']
assert all(connected(pair) for pair in historic)
print('audit sample',audit['checks'][:1],flush=True)
checks=[(r['from'],r['to']) for r in audit['checks']]
failed=[pair for pair in checks if not connected(pair)]
assert not screen(saved)
rep=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent=str(src.relative_to(root)),control_sha256=audit['sha256'],mount=mount,preservation=pres,control_pairs=len(checks),unresolved_control_pairs=failed,verified_phy_pairs=historic,rejected_copper=removed,new_drc=delta,mount_screen=screen(saved),assembly_ready=False)
(root/'reconciled-control.json').write_text(json.dumps(rep,indent=2)+'\n')
print('unresolved',failed,'added',pres['added_tracks_vias'],'discarded',[len(x['uuids']) for x in removed],flush=True);os._exit(0)
