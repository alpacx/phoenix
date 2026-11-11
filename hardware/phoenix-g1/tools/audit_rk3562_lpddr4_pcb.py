#!/usr/bin/env python3
"""Independent checks of candidate pad nets and preserved existing copper."""
import json,hashlib,collections,argparse
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'migration-rk3562';P=BASE/'experiments/lpddr4-1gb';S=P/'system'
def copper(board):
    return collections.Counter((type(t).__name__,t.GetNetname(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,(t.GetWidth(pcbnew.F_Cu) if isinstance(t,pcbnew.PCB_VIA) else t.GetWidth()),t.GetDrill() if isinstance(t,pcbnew.PCB_VIA) else 0) for t in board.GetTracks())
def main():
    source=BASE/'experiments/pmic-io-feed/candidate.kicad_pcb'
    ap=argparse.ArgumentParser();ap.add_argument('--board',type=Path,default=S/'kicad/pcb/phoenix-lpddr4-placement.kicad_pcb');args=ap.parse_args();path=args.board
    b=pcbnew.LoadBoard(str(path));old=pcbnew.LoadBoard(str(source))
    expected={(r['ref'],r['pin']):r['net'] or '' for r in json.loads((S/'review/integrated-contract.json').read_text())}
    seen={};nc=0
    for f in b.GetFootprints():
        for p in f.Pads():
            k=(f.GetReference(),p.GetNumber())
            if k in expected:
                assert p.GetNetname()==expected[k],(k,p.GetNetname(),expected[k]);seen[k]=True
    missing=sorted(set(expected)-set(seen));assert all(k[0]=='DS1' for k in missing),missing
    original=copper(old);current=copper(b)
    assert not (original-current),'Existing copper changed unexpectedly'
    added=current-original;assert sum(added.values())==130
    assert all(row[1].startswith('LPDDR4_') for row in added),'Unexpected added non-DDR copper'
    drc=json.loads((S/'review/pcb-drc.json').read_text());types=collections.Counter(v['type'] for v in drc['violations'])
    assert not any(types[k] for k in ['clearance','shorting_items','courtyards_overlap']),types
    assert types['track_width']==1,'Non-DDR width rule must retain the known PMIC neck violation'
    assert types['via_dangling']==65,'65 DDR escape vias intentionally await routing'
    result={'status':'PASS_PAD_NETS_AND_COPPER_PRESERVATION_NOT_RELEASE','pcb_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'matched_pad_dispositions':len(seen),'missing_display_pads':missing,'preserved_copper_items':sum(original.values()),'added_ram_fanout_items':sum(added.values()),'drc_categories':dict(types),'unconnected_reported':len(drc['unconnected_items']),'note':'499 unconnected report may be capped; RAM escape added, CPU and end-to-end DDR unrouted; footprint land approval pending'}
    (S/'review/pcb-migration-audit.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='missing_display_pads'})
if __name__=='__main__':main()
