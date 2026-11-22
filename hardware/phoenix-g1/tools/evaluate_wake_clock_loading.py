"""Estimate load, propagation, reference continuity and switching-node proximity of the terminated LPO route."""
from collections import Counter
from pathlib import Path
import json,math,hashlib,os
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text());cp=read('wake-clock-long-cad-model');src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();res=b.FindFootprintByReference('R2003');groups={o.m_Uuid.AsString() for q in res.Pads() for o in b.GetConnectivity().GetConnectedItems(q)};tracks=[o for o in b.GetTracks() if o.m_Uuid.AsString() in groups]
layers={p.F_Cu:p.In1_Cu,p.In2_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu,p.B_Cu:p.In4_Cu}
refs={l:[z.GetFilledPolysList(l) for z in b.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(l) and z.HasFilledPolysForLayer(l)] for l in set(layers.values())}
switch=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if o.GetNetname() in ['WIFI_VBAT_SW','WIFI_BUCK_SW','CPU_BUCK_LX'] or o.GetNetname().startswith('PMIC_SW')]
lens=Counter();refcov=Counter();noise=Counter();vias=[]
for t in tracks:
 if isinstance(t,p.PCB_VIA):vias.append(t);continue
 l=t.GetLayer();rl=layers[l];width=t.GetWidth()/1e6;length=t.GetLength()/1e6;w=t.GetWidth()/2;name=t.GetLayerName();lens[name,width]+=length
 a,z=t.GetStart(),t.GetEnd();count=max(1,math.ceil(length/.05));each=length/count;roi=inflated_box(t,2500000)
 adjacent=[o for o in switch if o.GetBoundingBox().Intersects(roi)]
 for i in range(count):
  at=p.VECTOR2I(round(a.x+(z.x-a.x)*(i+.5)/count),round(a.y+(z.y-a.y)*(i+.5)/count))
  g=any(poly.Contains(at) for poly in refs[rl]);refcov[name,'over_ground' if g else 'no_ground']+=each
  if any(o.IsOnLayer(l) and o.GetEffectiveShape(l).Collide(at,round(1000000+w)) for o in adjacent):noise['same_layer_within_1mm']+=each
  if any(o.GetEffectiveShape(o.GetLayer()).Collide(at,round(1000000+w)) for o in adjacent):noise['projected_within_1mm_any_layer']+=each
sim=read('usb-ddr-stack-simulation');models={}
for name,stack in sim['stacks'].items():
 cap=0;delay=0
 for (layer,w),length in lens.items():
  arr=sorted((m for m in stack['outside' if layer in ('F.Cu','B.Cu') else 'inner'] if m['mode']=='single'),key=lambda m:m['width_mm'])
  lo=max([m for m in arr if m['width_mm']<=w],key=lambda m:m['width_mm']);hi=min([m for m in arr if m['width_mm']>=w],key=lambda m:m['width_mm']);factor=(w-lo['width_mm'])/(hi['width_mm']-lo['width_mm']) if lo!=hi else 0
  td=lambda m:1e6*math.sqrt(m['effective_er'])/299792458
  cf=lambda m:td(m)*1000/m['ohms']
  cap+=length*(cf(lo)+(cf(hi)-cf(lo))*factor);delay+=length*(td(lo)+(td(hi)-td(lo))*factor)
 models[name]=dict(trace_pF=cap,one_way_delay_ns_length_sum=delay,remaining_pF_at_receiver_limit_before_vias_and_pads=15-5-cap)
out=dict(sha256=cp['sha256'],route_length_mm=sum(lens.values()),series_ohms=res.GetValue(),via_count=len(vias),length_by_layer_mm={l:sum(v for (k,w),v in lens.items() if k==l) for l,w in lens},reference_mm={l:{k:round(refcov[l,k],4) for k in ('over_ground','no_ground')} for l,w in lens},switching_copper_proximity_mm=dict(noise),models=models,
 source=dict(document='reference/wifi-clock-c5274152.pdf, Taitien OV Rev(17)04/2017',CMOS_rise_fall_max_ns_at_15pF=50,frequency_kHz=32.768),
 receiver=dict(document='reference/wifi-ap6256.pdf section External LPO signal characteristics',input_capacitance_limit_pF=5,jitter_Hz_max_300Hz_15kHz=1),
 limitations=['Source datasheet gives maximum edge time at 15 pF, not minimum edge time or an RC driver model.','Pads, via barrels and packages are not included in the 2D trace capacitance.','Total includes connected branches. Noise distances are geometric screens, not crosstalk simulation.','36 mm was an exploration bound, not a vendor length limit. Supply transient and receiver jitter remain unmeasured.'],assembly_ready=False)
(root/'wake-clock-loading-and-return.json').write_text(json.dumps(out,indent=2)+'\n');print(out['route_length_mm'],out['models'],out['reference_mm'],out['switching_copper_proximity_mm'],flush=True);os._exit(0)
