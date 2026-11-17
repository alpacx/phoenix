import pcbnew as p,json,math
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
stages=['five-volt-testpoint','display-led-feed','display-enable','display-buffer-bypass','display-buffer-feed','display-input-pulls','display-input-returns','display-reservoir','display-io-bleed','display-backlight-control','ethernet-reset-passives','ethernet-strap-grounds','ethernet-center-tap','ethernet-bias-grounds','ethernet-clock-placement','ethernet-clock-grounds','ethernet-clock-pins','ethernet-cap-grounds','ethernet-bypass-local','ethernet-avdd33-bypass','ethernet-io-power-link','ethernet-avdd10-escape','ethernet-io-bypass-escape','ethernet-dvdd33-bypass'];results=[]
for a,z in zip(stages,stages[1:]):
 before=p.LoadBoard(str(D/(a+'.kicad_pcb')));after=p.LoadBoard(str(D/(z+'.kicad_pcb')));old={t.m_Uuid.AsString() for t in before.GetTracks()};new=[t for t in after.GetTracks() if t.m_Uuid.AsString() not in old]
 rows={};overlap=[]
 for t in new:
  if isinstance(t,p.PCB_VIA):
   for f in after.GetFootprints():
    for q in f.Pads():
     if q.GetBoundingBox().Contains(t.GetPosition()):overlap.append({'via_mm':[p.ToMM(t.GetPosition().x),p.ToMM(t.GetPosition().y)],'pad':f.GetReference()+'.'+q.GetNumber(),'net':q.GetNetname()})
  else:
   k=t.GetNetname()+':'+t.GetLayerName();rows[k]=rows.get(k,0)+p.ToMM(t.GetLength())
 results.append({'stage':z,'added_elements':len(new),'removed_elements':len(old-{t.m_Uuid.AsString() for t in after.GetTracks()}),'track_lengths_mm':rows,'via_centers_inside_pad_bounds':overlap})
(D/'display-routing-metrics.json').write_text(json.dumps({'status':'GEOMETRY_ONLY','stages':results,'electrical_qualified':False,'assembly_ready':False},indent=2)+'\n');print(json.dumps(results,indent=2))
