#!/usr/bin/env python3
"""Conservative courtyard/bounding-circle screen; not mechanical qualification."""
import argparse,hashlib,json,math
from pathlib import Path
import pcbnew as p
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
def screen(board):
 rows=[]
 for z in board.Zones():
  if not z.GetIsRuleArea() or not z.GetZoneName().endswith(' mechanical reservation'):continue
  box=z.GetBoundingBox();x=p.ToMM(box.GetX()+box.GetWidth()/2);y=p.ToMM(box.GetY()+box.GetHeight()/2);r=p.ToMM(max(box.GetWidth(),box.GetHeight()))/2
  for f in board.GetFootprints():
   box=f.GetCourtyard(f.GetLayer()).BBox()
   if box.GetWidth()<=0 or box.GetHeight()<=0:continue
   left,top,right,bottom=[p.ToMM(v) for v in (box.GetX(),box.GetY(),box.GetRight(),box.GetBottom())]
   distance=math.hypot(max(left-x,0,x-right),max(top-y,0,y-bottom))
   if distance<=r:rows.append({'reservation':z.GetZoneName(),'ref':f.GetReference(),'layer':board.GetLayerName(f.GetLayer()),'courtyard_bbox_mm':[left,top,right,bottom]})
 return sorted(rows,key=lambda q:(q['reservation'],q['ref']))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--board',type=Path);ap.add_argument('--baseline',type=Path);ap.add_argument('--output',type=Path);args=ap.parse_args()
 cp=json.loads((D/'working-candidate.json').read_text());src=args.board or D/cp['board'];rows=screen(p.LoadBoard(str(src)))
 report={'status':'CONSERVATIVE_COMPONENT_RESERVATION_SCREEN','board_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'potential_conflicts':rows,'limitations':['Bounding circle and courtyard rectangles can overestimate collision.','Existing rule areas prohibit copper but intentionally do not prohibit pads/footprints.','No actual mounting holes or completed mechanical assembly are implied.'],'assembly_ready':False}
 if args.baseline:
  old=screen(p.LoadBoard(str(args.baseline)));key=lambda r:(r['reservation'],r['ref']);before={key(r) for r in old};after={key(r) for r in rows};report['baseline_sha256']=hashlib.sha256(args.baseline.read_bytes()).hexdigest();report['introduced_conflicts']=sorted(after-before);report['resolved_conflicts']=sorted(before-after)
 out=args.output or D/'pcb/mount-component-screen.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
