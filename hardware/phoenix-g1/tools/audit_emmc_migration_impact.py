#!/usr/bin/env python3
"""Inventory eMMC replacement impact against current routing; no CAD mutation."""
import pcbnew as p,json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];E=R/'migration-rk3562/experiments';S=E/'stacked-expansion';O=E/'emmc-8gb';cp=json.loads((S/'working-candidate.json').read_text());src=S/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));b.BuildConnectivity();pads={(f.GetReference(),a.GetNumber()):a for f in b.GetFootprints() for a in f.Pads()}
rows=[]
for file in (S/'system/review').glob('*expected.json'):rows+=json.loads(file.read_text())
contract={(r['ref'],r['pin']):r['net'] for r in rows};mapping=json.loads((O/'signal-map.json').read_text());impact=[]
for m in mapping:
 ball=m['soc_ball'];pad=pads['U1',ball];assert contract['U1',ball]==m['previous_net'];assert pad.GetNetname()==(m['previous_net'] or '')
 impact.append({**m,'existing_connected_tracks_vias':len(b.GetConnectivity().GetConnectedTracks(pad))})
old=json.loads((S/'system/review/boot-flash-expected.json').read_text());refs=sorted({r['ref'] for r in old});flash=[]
for ref in refs:
 pp=[a for (r,_),a in pads.items() if r==ref];flash.append({'ref':ref,'nets':sorted({a.GetNetname() for a in pp}),'existing_connected_tracks_vias':sum(len(b.GetConnectivity().GetConnectedTracks(a)) for a in pp)})
assert pads['U1','1F14'].GetNetname()=='+3V3_IO';assert len(mapping)==11
report={'status':'REPLACEMENT_IMPACT_INVENTORY_NOT_INTEGRATED','source_board_sha256':cp['sha256'],'signal_changes':impact,'old_boot_flash_sheet_components':flash,'power_domain_change':{'pad':'U1.1F14','domain':'VCCIO2','from':'+3V3_IO','to_candidate':'EMMC_IO_1V8','existing_connected_tracks_vias':len(b.GetConnectivity().GetConnectedTracks(pads['U1','1F14'])),'qualified_source_and_sequence':False},'VCCIO3_SDMMC0_unchanged':True,'domain_evidence':'RK3562 reference page 8 labels VCCIO2 eMMC/FSPI separately from VCCIO3 SDMMC0; do not infer domains from GPIO bank number alone','storage_candidate':'KLM8G1GETF-B041 8GB','old_NOR_must_not_remain_parallel':True,'required_next':['Replace boot-flash sheet and references in integrated schematic/BOM','Reconnect all 11 SoC signals and change ONLY U1.1F14 domain','Qualify 1.8V/3.3V sources, sequencing, reset, straps and recovery','Place eMMC and local decoupling; do not put VDDI on an external rail','Export and audit whole-system netlist before PCB changes'],'assembly_ready':False}
(O/'review/migration-impact.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
