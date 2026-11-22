"""Evaluate 50-ohm selector copper and the open pad branch for both candidate stacks."""
from pathlib import Path
import hashlib,json,math
from scipy.constants import c
from simulate_outer_pair_impedance import solve_pair,check_parallel_plates
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';d=json.loads((root/'wifi-selector-branch-coupon.json').read_text())['candidate'];assert hashlib.sha256((root/d['board']).read_bytes()).hexdigest()==d['sha256']
steps=(.012,.008,.006);results={}
for name,(h,er) in {'JLC06161H-3313':(.0994,4.1),'JLC06161H-7628':(.2104,4.4)}.items():
 runs=[]
 for mesh in steps:
  r=solve_pair(d['width_mm'],.25,step=mesh,wall=1.5,substrate_mm=h,substrate_er=er,single=True);runs.append(dict(mesh_mm=mesh,ohms=r['single_ended_ohms'],effective_er=r['effective_er']))
 low,high=(.10,.20) if name.endswith('3313') else (.28,.40)
 for _ in range(8):
  mid=(low+high)/2;value=solve_pair(mid,.25,step=.008,wall=1.5,substrate_mm=h,substrate_er=er,single=True)['single_ended_ohms']
  if value>50:low=mid
  else:high=mid
 target=round((low+high)/2,3)
 own=solve_pair(target,.25,step=.006,wall=1.5,substrate_mm=h,substrate_er=er,single=True)
 last=runs[-1];beta=2*math.pi*5.85e9*math.sqrt(last['effective_er'])/c;length=d['stub_to_unfitted_center_mm']*.001
 # Lossless, open shunt stub across equal-impedance lines. Land/fringing are not in this model.
 susceptance=math.tan(beta*length);gamma=abs(susceptance)/math.sqrt(4+susceptance**2)
 results[name]=dict(solutions=runs,stack_specific_width_mm=target,stack_specific_fine_mesh_ohms=own['single_ended_ohms'],stub_phase_deg=math.degrees(beta*length),stub_only_return_loss_db=-20*math.log10(gamma),isolated_line_nominal_50ohm_error_pct=(last['ohms']-50)*2)
out=dict(board_sha256=d['sha256'],line_width_mm=d['width_mm'],open_stub_to_center_mm=d['stub_to_unfitted_center_mm'],frequency_GHz=5.85,stacks=results,limitations=['Finite-element section assumes an isolated outer trace over an infinite plane. Actual pour holes, copper edges, coplanar ground, module RF land, 0402 lands, end fringing, material tolerance and case are excluded.','Use final stack and manufacturer controlled-impedance coupon, 3D connector/selector model and VNA before qualifying performance.'],assembly_ready=False)
(root/'wifi-selector-impedance-model.json').write_text(json.dumps(out,indent=2)+'\n');print([(n,round(v['solutions'][-1]['ohms'],2),round(v['stub_only_return_loss_db'],1)) for n,v in results.items()])
