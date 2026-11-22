"""Check a complete bus rejoin against the circuit before the provisional launch."""
import hashlib,json,os,sys
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def read(name):return json.loads((root/(name+'.json')).read_text())
name='sda' if '--sda' in sys.argv else 'scl'
base=read('rotated-pmic-scl-complete' if name=='sda' else 'rotated-pmic-cap-ground-pivots')
reverse='--left-first' in sys.argv
cleared='--after-c422' in sys.argv
label=('rotated-c422-' if cleared else 'rotated-left-' if reverse else 'rotated-pmic-')+name
if reverse:base=read('rotated-pmic-cap-ground-pivots' if name=='sda' else 'rotated-left-sda-complete')
if cleared:base=read('rotated-scl-cap-release')['candidate']
reuse='--existing-pmic-via' in sys.argv
if reuse:
    name='scl';label='rotated-existing-scl';base=read('rotated-left-sda-complete')
    launch=dict(parent_sha256=base['sha256'],sha256=base['sha256'],via_id='98710ec6-52e5-4416-b308-6aeccbb8c6d1',pin='U4.1',length_mm=0)
else:
    launch=read(label+'-launch')['candidate']
trunk=read(label+'-trunk')
assert launch['parent_sha256']==base['sha256'] and trunk['parent_sha256']==launch['sha256']
def load(d):
    path=root/d['board'];assert hashlib.sha256(path.read_bytes()).hexdigest()==d['sha256'];return path,p.LoadBoard(str(path))
src,old=load(base);out,b=load(trunk)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((out.parent/'drc.json').read_text()));assert not delta,delta
guard=verify_preservation(old,b)
pin=b.FindFootprintByReference('U4').FindPadByNumber('2' if name=='sda' else '1')
ref='R415' if name=='sda' else 'R414';dst=b.FindFootprintByReference(ref).FindPadByNumber('2');group={q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pin)}
assert launch['via_id'] in group and dst.m_Uuid.AsString() in group
if reuse:
    for number,reference in [('1','R414'),('2','R415')]:
        net_pin=b.FindFootprintByReference('U4').FindPadByNumber(number)
        assert b.FindFootprintByReference(reference).FindPadByNumber('2').m_Uuid.AsString() in {x.m_Uuid.AsString() for x in b.GetConnectivity().GetConnectedItems(net_pin)}
report=dict(existing_through_via=launch['via_id'] if reuse else None,board=trunk['board'],sha256=trunk['sha256'],parent_sha256=base['sha256'],pin=launch['pin'],sink=ref+'.2',launch_mm=launch['length_mm'],trunk_mm=sum(v['length_mm'] for v in trunk['records']),preservation=guard,new_drc=delta,assembly_ready=False)
meta_src=root/read('rotated-left-sda-complete')['board'] if cleared else src
meta=json.loads((meta_src.parent/'output-legs.json').read_text());meta['board_sha256']=trunk['sha256'];meta['restored_'+name]=report
(out.parent/'output-legs.json').write_text(json.dumps(meta,indent=2)+'\n');(root/(label+'-complete.json')).write_text(json.dumps(report,indent=2)+'\n');print(report['pin'],report['sink'],report['launch_mm'],report['trunk_mm'],flush=True);os._exit(0)
