#!/usr/bin/env python3
"""PCB-only UART edge-pin study. Not a schematic-matched checkpoint."""
import pcbnew as p,json,hashlib,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/stacked-expansion';D=R/'pcb';cp=json.loads((R/'working-candidate.json').read_text());src=R/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));b.BuildConnectivity();f=next(f for f in b.GetFootprints() if f.GetReference()=='J3');pads={a.GetNumber():a for a in f.Pads()};moves=[]
for old,new,net in [('25','39','EXP_UART_TX'),('26','40','EXP_UART_RX')]:
 assert pads[old].GetNetname()==net and pads[new].GetNetCode()==0
 assert not b.GetConnectivity().GetConnectedTracks(pads[old]) and not b.GetConnectivity().GetConnectedTracks(pads[new])
 pads[new].SetNet(b.FindNet(net));pads[old].SetNetCode(0);moves.append({'net':net,'from_pin':old,'to_pin':new})
out=D/'uart-edge-remap.kicad_pcb';p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
for ext in ['kicad_dru','kicad_pro']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
(D/'uart-edge-remap.json').write_text(json.dumps({'status':'PCB_ONLY_PINOUT_STUDY_NOT_PROMOTED','source_sha256':cp['sha256'],'changes':moves,'schematic_updated':False,'assembly_ready':False},indent=2)+'\n')
