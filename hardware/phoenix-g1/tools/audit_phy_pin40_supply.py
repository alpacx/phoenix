"""Prove which copper supplies the PHY by removing it only from throwaway boards."""
import hashlib,json,os,re,subprocess,sys,tempfile
from pathlib import Path
import pcbnew as p

def check(board,a,z):
    def pad(key):
        ref,num=key.split('.')
        return board.FindFootprintByReference(ref).FindPadByNumber(num)
    target=pad(z).m_Uuid.AsString()
    return target in {q.m_Uuid.AsString() for q in board.GetConnectivity().GetConnectedItems(pad(a))}
regulator='--regulator' in sys.argv
pairs=[('U5.30','L501.1'),('L501.2','C511.1'),('C511.1','C522.1'),('C522.1','U5.38'),('R530.2','C518.1')] if regulator else [('C515.1','C518.1'),('C518.1','U5.40'),('R530.2','C515.1'),('C511.1','U5.38'),('C518.2','C511.2')]
if '--probe' in sys.argv:
    board=p.LoadBoard(sys.argv[2]);board.BuildConnectivity()
    flags=[check(board,a,z) for a,z in pairs]
    print(json.dumps(flags),flush=True);os._exit(0)

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def read(name):
    meta=json.loads((root/(name+'.json')).read_text())
    path=root/meta['board']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==meta['sha256']
    return path,p.LoadBoard(str(path))
path,board=read('layout-peripheral-supply-balls' if regulator else 'layout-phy-pin40-powered')
_,parent=read('phy-pin40-5v-clearance')
old={t.m_Uuid.AsString() for t in parent.GetTracks()}
new=[t for t in board.GetTracks() if t.m_Uuid.AsString() not in old]
assert regulator or new and all(t.GetNetname()=='+3V3_PHY' and t.GetLayer()==p.In2_Cu and t.GetWidth()==1050000 for t in new)
pos=board.FindFootprintByReference('C518').FindPadByNumber('1').GetPosition()
vias=[v for v in board.GetTracks() if isinstance(v,p.PCB_VIA) and (v.GetPosition()-pos).EuclideanNorm()<1000 and v.GetNetname()=='+3V3_PHY']
assert len(vias)==1
assert vias[0].GetFillingMode()==p.FILLING_MODE_FILLED and vias[0].GetCappingMode()==p.CAPPING_MODE_CAPPED
text=path.read_text()
def probe(file):
    result=subprocess.run([sys.executable,__file__,'--probe',str(file)]+(['--regulator'] if regulator else []),text=True,capture_output=True,check=True)
    return json.loads(result.stdout.strip().splitlines()[-1])
assert probe(path)==[True]*5
tests=[]
with tempfile.TemporaryDirectory() as tmp:
    def by_id(*ids):
        tracks=[t for t in board.GetTracks() if t.m_Uuid.AsString() in ids]
        assert len(tracks)==len(ids) and all(t.GetWidth()==1550000 for t in tracks)
        return tracks
    cuts=[('switch_entry',by_id('f1dd6464-b754-4958-8b4d-81fe96a54b71','46fb40c4-4bf0-4f43-aed1-623ec66430f2')),('inductor_output',by_id('95ed1b31-eadd-4e8f-a9cd-7aba1dbedbd4','b1c52a0c-3e10-4d38-b2db-6652c09c4626'))] if regulator else [('distribution',new),('local_plated_via',vias)]
    for name,removed in cuts:
        ids={o.m_Uuid.AsString() for o in removed}
        pattern=r'\n\t\((?:segment|via)\n(?:(?!\n\t\)).)*?\n\t\)'
        edited=re.sub(pattern,lambda m:'' if any(i in m[0] for i in ids) else m[0],text,flags=re.S)
        assert all(k not in edited for k in ids)
        file=Path(tmp)/(name+'.kicad_pcb');file.write_text(edited)
        flags=probe(file)
        # Removing the barrel splits the F.Cu pin from the rear cap as well.
        expected=[name!='switch_entry',name!='inductor_output',True,True,True] if regulator else [False,name=='distribution',True,True,True]
        assert flags==expected,(name,flags)
        tests.append(dict(cut=name,checks=flags))
(root/('phy-regulator-cut-tests.json' if regulator else 'phy-pin40-cut-tests.json')).write_text(json.dumps(dict(board_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pairs=['/'.join(pair) for pair in pairs],intact=[True]*5,tests=tests),indent=2)+'\n')
print(tests,flush=True);os._exit(0)
