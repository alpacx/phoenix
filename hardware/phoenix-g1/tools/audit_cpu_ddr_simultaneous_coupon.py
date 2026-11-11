#!/usr/bin/env python3
"""Check actual coupon copper and independent KiCad DRC, not solver claims."""
import json,csv,hashlib
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'migration-rk3562/experiments/lpddr4-1gb';D=P/'cpu-simultaneous-coupon'
def key(p):return p.x,p.y
def main():
    board=D/'cpu-simultaneous.kicad_pcb';b=pcbnew.LoadBoard(str(board));r=json.loads((D/'manifest.json').read_text());drc=json.loads((D/'drc.json').read_text())
    assert all(v['type']=='via_dangling' for v in drc['violations']), 'Unexpected DRC violations'
    signals=[s for s in csv.DictReader((P/'signal-map.csv').open()) if 'ODT0_CA' not in s['signal']];pads={p.GetNumber():p for f in b.GetFootprints() for p in f.Pads()};verified=[]
    for s in signals:
        ts=[t for t in b.GetTracks() if t.GetNetname()==s['signal']];vs=[t for t in ts if isinstance(t,pcbnew.PCB_VIA)]
        if not vs:continue
        assert len(vs)==1
        edges={}
        for t in ts:
            if isinstance(t,pcbnew.PCB_VIA):continue
            a,z=key(t.GetStart()),key(t.GetEnd());edges.setdefault(a,set()).add(z);edges.setdefault(z,set()).add(a)
        seen={key(pads[s['soc_ball']].GetPosition())};todo=list(seen)
        while todo:
            for z in edges.get(todo.pop(),[]):
                if z not in seen:seen.add(z);todo.append(z)
        assert key(vs[0].GetPosition()) in seen, ('Disconnected escape',s)
        verified.append(s['soc_ball'])
    assert len(verified)==r['escaped']==len(drc['violations'])
    result={'status':'GEOMETRY_AND_COPPER_CONNECTIVITY_CHECK','board_sha256':hashlib.sha256(board.read_bytes()).hexdigest(),'connected_escape_count':len(verified),'required':65,'verified_balls':verified,'unexpected_drc_findings':0,'intentional_dangling_vias':len(verified),'assembly_ready':False,'excludes':['Neighbor components and existing board copper','DDR power and return paths','Impedance and timing','Manufacturing qualification','Physical tests']}
    (D/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['connected_escape_count','required','unexpected_drc_findings']}))
if __name__=='__main__':main()
