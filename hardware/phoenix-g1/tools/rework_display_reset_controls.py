"""Test the joint reset, display DC and expansion GPIO1 breakout in the native SoC pad field."""
from collections import Counter,defaultdict
from pathlib import Path
import hashlib,heapq,json,math,os,shutil,subprocess,sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text())
base=read('layout-lcd-select-trunk');probe=read('lcd-reset-control-obstacles');src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']==probe['source_sha256']
v=lambda xy:p.VECTOR2I(*xy);uid=lambda o:o.m_Uuid.AsString();side=p.F_Cu
from native_front_splice import wire,compact,recover
full='--gpio-chain' in sys.argv
def source_chain(b):
    gpio=[t for t in b.GetTracks() if t.GetNetname()=='EXP_GPIO1' and t.IsOnLayer(side)]
    pos=tuple(b.FindFootprintByReference('U1').FindPadByNumber('L3').GetPosition());chain=set()
    while True:
        if any(isinstance(t,p.PCB_VIA) and tuple(t.GetPosition())==pos for t in gpio):return chain
        nxt=[t for t in gpio if uid(t) not in chain and not isinstance(t,p.PCB_VIA) and pos in (tuple(t.GetStart()),tuple(t.GetEnd()))]
        assert len(nxt)==1,(pos,len(nxt))
        t=nxt[0];chain.add(uid(t));pos=next(q for q in (tuple(t.GetStart()),tuple(t.GetEnd())) if q!=pos)
stem='display-reset-gpio-chain' if full else 'display-reset-control-fanout'
folder=root/'runs'/stem;folder.mkdir(exist_ok=True);out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
if full and 'PHOENIX_CASE' not in os.environ:
    results=[]
    for i in range(8):
        subprocess.run([sys.executable,__file__,'--gpio-chain'],env={**os.environ,'PHOENIX_CASE':str(i)},check=True)
        row=json.loads((folder/('case-'+str(i)+'.json')).read_text());results.append(row)
        if row['candidate']:break
    (root/(stem+'.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],results=results,assembly_ready=False),indent=2)+'\n');os._exit(0)
winner=None;attempts=[];unique=set()
for rec in probe['lines']['LCD_RESET_N']:
    if any(o['kind']!='PCB_TRACK' or o['layer']!='F.Cu' for o in rec['blockers']):continue
    # Different via endpoints can share the same local three-trace conflict.
    # Reuse tests only when their signal paths through that conflict are identical.
    prefix=tuple(tuple(pt) for pt in rec['signal_path_nm'] if pt[0]>35800000)
    ids={o['uuid'] for o in rec['blockers']};key=(prefix,tuple(sorted(ids)))
    if key in unique:continue
    unique.add(key)
    for order in [('EXP_GPIO1','LCD_DC'),('LCD_DC','EXP_GPIO1')]:
        idx=len(attempts)
        if full and str(idx)!=os.environ.get('PHOENIX_CASE'):attempts.append(None);continue
        b=p.LoadBoard(str(src));pin=b.FindFootprintByReference('U1').FindPadByNumber('N2');ids=ids|source_chain(b) if full else ids;original=list(b.GetTracks());retired=[t for t in original if uid(t) in ids]
        snapshot=defaultdict(list)
        for t in retired:snapshot[t.GetNetname()].append((tuple(t.GetStart()),tuple(t.GetEnd()),t.GetWidth(),t.GetNetCode()))
        for t in retired:b.Remove(t)
        sv=p.PCB_VIA(b);sv.SetWidth(450000);sv.SetDrill(200000);sv.SetViaType(p.VIATYPE_THROUGH);sv.SetLayerPair(p.F_Cu,p.B_Cu);sv.SetPosition(v(rec['via_nm']));sv.SetNetCode(pin.GetNetCode());b.Add(sv)
        rx=compact(rec['signal_path_nm'])
        for a,z in zip(rx,rx[1:]):b.Add(wire(b,a,z,pin.GetNetCode(),200000))
        branches=[]
        for net in order:
            raw=snapshot[net]
            if not raw:continue
            if net=='EXP_GPIO1' and full and len(branches)==1:
                temp=folder/('gpio-coupon-'+str(idx)+'.kicad_pcb')
                p.SaveBoard(str(temp),b)
            path,info=recover(b,raw,net,False);branches.append(dict(net=net,**info))
            if path is None:break
            for a,z in zip(path,path[1:]):b.Add(wire(b,a,z,info['code'],info['width']))
        else:
            p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
            subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
            delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
            if all(r['type']=='via_dangling' and r['items']==[uid(sv)] for r in delta):
                saved=p.LoadBoard(str(out));saved.BuildConnectivity();qs=saved.FindFootprintByReference('U1').FindPadByNumber('N2')
                if uid(sv) in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(qs)} and not screen(saved):
                    proof=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=ids);winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),preservation=proof,via_uuid=uid(sv),new_drc=delta,branches=branches);break
            branches.append(dict(delta=delta))
        attempts.append(dict(at=rec['via_nm'],order=order,branches=branches))
        if full:
            (folder/('case-'+str(idx)+'.json')).write_text(json.dumps(dict(attempt=attempts[-1],candidate=winner),indent=2)+'\n');os._exit(0)
    if winner:break
(root/(stem+'.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,attempts=attempts,assembly_ready=False),indent=2)+'\n');print(bool(winner),len(attempts),attempts[:2],flush=True);os._exit(0)
