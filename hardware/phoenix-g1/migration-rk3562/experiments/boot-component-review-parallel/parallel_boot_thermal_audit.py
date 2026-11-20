import pcbnew,json
from pathlib import Path
p=Path(__file__).parent;bdir=p.parent/'pmic-ldo-inputs';c=json.loads((bdir/'working-candidate.json').read_text());b=pcbnew.LoadBoard(str(bdir/c['board']));out=[]
for f in b.GetFootprints():
 if not f.GetReference().startswith('U'):continue
 for pad in f.Pads():
  sz=pcbnew.ToMM(pad.GetSize())
  if min(sz)<1 or not pad.IsOnLayer(pcbnew.F_Paste):continue
  holes=[]
  for q in f.Pads():
   if q.GetDrillSize().x and pad.HitTest(q.GetPosition()):holes.append({'number':q.GetNumber(),'drill_mm':pcbnew.ToMM(q.GetDrillSize())})
  out.append({'ref':f.GetReference(),'value':f.GetValue(),'pad':pad.GetNumber(),'size_mm':sz,'paste_margin':pad.GetLocalSolderPasteMargin(),'paste_ratio':pad.GetLocalSolderPasteMarginRatio(),'holes_with_centers_inside':holes})
(p/'thermal-pad-audit.json').write_text(json.dumps({'checkpoint':c,'large_paste_pads':out,'note':'Screening only. Graphics and global paste settings must be reviewed before computing final Gerber aperture.'},indent=2)+'\n')
print([(x['ref'],x['pad'],x['size_mm'],len(x['holes_with_centers_inside'])) for x in out])
