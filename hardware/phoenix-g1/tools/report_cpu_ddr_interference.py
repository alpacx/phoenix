#!/usr/bin/env python3
"""Summarize failed integration without treating intentional diagnostics as release checks."""
import json,collections,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'migration-rk3562/experiments/lpddr4-1gb';D=P/'cpu-board-integration'
def main():
    r=json.loads((D/'drc.json').read_text());m=json.loads((D/'manifest.json').read_text());source=P/'system/kicad/pcb/phoenix-lpddr4-placement.kicad_pcb';assert hashlib.sha256(source.read_bytes()).hexdigest()==m['source_sha256']
    critical={'shorting_items','clearance','hole_clearance','hole_to_hole'};findings=[v for v in r['violations'] if v['type'] in critical];refs=collections.Counter();nets=collections.Counter()
    for v in findings:
        for i in v['items']:
            desc=i['description'];refs.update(re.findall(r'\b(?:U|R|C|L|FB|J|Y)\d+\b',desc));nets.update(re.findall(r'\[([^\]]+)\]',desc))
    out={'status':'FAILED_FULL_BOARD_INTEGRATION_NOT_FOR_MANUFACTURE','board_sha256':hashlib.sha256((D/'candidate.kicad_pcb').read_bytes()).hexdigest(),'drc_sha256':hashlib.sha256((D/'drc.json').read_bytes()).hexdigest(),'source_candidate_unchanged':True,'counts':dict(collections.Counter(v['type'] for v in r['violations'])),'critical_interference_count':len(findings),'involved_references':dict(refs.most_common()),'involved_nets':dict(nets.most_common()),'first_findings':findings[:12],'next_design_constraint':'Reserve CPU DDR through-via escape volume on both faces and all copper layers before relocating the routed Wi-Fi island or CPU/RAM group. Do not merge this diagnostic board.','manufacturing_ready':False}
    (D/'interference-summary.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['critical_interference_count','involved_references','source_candidate_unchanged']}))
if __name__=='__main__':main()
