"""Validate the continuous 0.50 mm rear branch between two existing 3V3 I/O bypass islands."""
from pathlib import Path
from collections import Counter
import sys,json,hashlib,shutil,subprocess
import pcbnew as p
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
output='--output-banks' in sys.argv
cp=json.loads((r/('layout-logic-output-cap-c441.json' if output else 'layout-io-bank-copper-contact.json')).read_text());src=r/cp['board']
report=json.loads((r/('output-bank-copper-edge-search.json' if output else 'core-copper-edge-search.json')).read_text());assert cp['sha256']==report['parent_sha256']==hashlib.sha256(src.read_bytes()).hexdigest()

# Retain the existing feedback pickup for the NPU buck pending a Kelvin review.
for name,labels in ([('npu-output-cap-c444',['C444.1','L404.2'])] if output else [('cpu-local-bulk-c1608',['C1601.1','C1608.1']),('cpu-cap-bank-c1606',['C1606.1','C1608.1']),('logic-output-cap-c441',['C441.1','L401.2'])]):
    row,=[q for q in report['rows'] if q['found'] and q['found']['groups']==labels]
    route=row['found'];b=p.LoadBoard(str(src))
    pts=[]
    for end in route['path_nm']:
        if len(pts)>1:
            a,z=pts[-2:]
            if (z[0]-a[0])*(end[1]-z[1])==(z[1]-a[1])*(end[0]-z[0]):pts.pop()
        pts.append(end)
    net=row['net'];code=b.FindNet(net).GetNetCode()
    for a,z in zip(pts,pts[1:]):b.Add(make(b,a,z,800000,code,b.GetLayerID(row['layer'])))
    out=r/'runs'/name;out.mkdir(exist_ok=True);file=out/src.name
    for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
    shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table')
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(file)],capture_output=True,check=True)
    old=json.loads((src.parent/'drc.json').read_text());drc=json.loads((out/'drc.json').read_text());fresh=p.LoadBoard(str(file));fresh.BuildConnectivity();uid=lambda o:o.m_Uuid.AsString()
    def pad(n):
        ref,num=n.split('.');return fresh.FindFootprintByReference(ref).FindPadByNumber(num)
    cache={}
    def connected(a,z):
        if a not in cache:cache[a]={uid(o) for o in fresh.GetConnectivity().GetConnectedItems(pad(a))}
        return uid(pad(z)) in cache[a]
    delta=introduced(old,drc);a,z=route['groups'];joins=len(drc['unconnected_items']);ok=not delta and connected(a,z) and joins<cp['remaining_minimum_joins']
    result=dict(parent_sha256=cp['sha256'],route=pts,groups=route['groups'],width_mm=.8,length_mm=route['length_mm'],connected=connected(a,z),new_drc=delta,joins=joins,adopted=ok)
    if ok:
        pairs=sorted({tuple(sorted(pair)) for pair in cp['verified_pairs']+[route['groups']]})
        assert all(connected(a,z) for a,z in pairs)
        nets=cp['open_nets'].copy();gs=nets[net];hit=[g for g in gs if route['groups'][0] in g or route['groups'][1] in g];assert len(hit)==2
        nets[net]=[g for g in gs if g not in hit]+[sorted(hit[0]+hit[1])]
        assert sum(len(gs)-1 for gs in nets.values())==joins
        state=dict(board=str(file.relative_to(r)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],verified_pairs=pairs,preservation=verify_preservation(p.LoadBoard(str(src)),fresh),open_nets=nets,remaining_minimum_joins=joins,new_drc=delta,drc_counts=dict(Counter(x['type'] for x in drc['violations'])),assembly_ready=False)
        (r/('layout-'+name+'.json')).write_text(json.dumps(state,indent=2)+'\n')
    (r/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(name,ok,joins,[e['type'] for e in delta],flush=True)
    if ok:cp=state;src=file
