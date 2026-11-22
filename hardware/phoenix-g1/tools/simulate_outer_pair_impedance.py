"""Quasi-static, two-dimensional odd-mode FEM screen for Phoenix outer-layer pairs."""
from pathlib import Path
import hashlib
import json
import math

import numpy as np
from scipy.constants import c, epsilon_0
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

product=Path(__file__).resolve().parents[1]
root=product/'migration-rk3562/experiments/phy-power-parallel'
stack=json.loads((product/'review/stackup-3313-candidate.json').read_text())
base=json.loads((root/'layout-pmic-pwron-filter.json').read_text())
board=root/base['board']
assert hashlib.sha256(board.read_bytes()).hexdigest()==base['sha256']
rules=json.loads(board.with_suffix('.kicad_pro').read_text())['net_settings']['classes']
default=next(n for n in rules if n['name']=='Default')
h=stack['dielectrics_top_to_bottom'][0]['mm']
er=stack['dielectrics_top_to_bottom'][0]['er_published']
mil=.0254
copper=1.6*mil
narrowing=.7*mil
mask_base=1.2*mil
mask_top=.6*mil
mask_er=3.8


def partition(limits,step):
    cells=[]
    for l,r in zip(limits,limits[1:]):
        cells.extend(np.linspace(l,r,max(1,math.ceil((r-l)/step)),endpoint=False))
    return np.array(cells+[limits[-1]])


def triangles(nx,ny):
    grid=np.arange(nx*ny).reshape(ny,nx)
    nw,ne,sw,se=[a.ravel() for a in (grid[1:,:-1],grid[1:,1:],grid[:-1,:-1],grid[:-1,1:])]
    return np.vstack((np.stack((sw,se,ne),axis=1),np.stack((sw,ne,nw),axis=1)))


def capacitance(xy,tri,permittivity,zero,one):
    # Linear shape gradients form the local electrostatic stiffness matrices.
    p=xy[tri]
    shift=np.roll(p,-1,axis=1)-np.roll(p,-2,axis=1)
    grad=np.stack((shift[:,:,1],-shift[:,:,0]),axis=2)
    area2=(p[:,1,0]-p[:,0,0])*(p[:,2,1]-p[:,0,1])-(p[:,2,0]-p[:,0,0])*(p[:,1,1]-p[:,0,1])
    assert np.min(area2)>0
    local=np.einsum('nik,njk->nij',grad,grad)*(permittivity/(2*area2))[:,None,None]
    rows=np.broadcast_to(tri[:,:,None],local.shape)
    cols=np.broadcast_to(tri[:,None,:],local.shape)
    mat=coo_matrix((local.ravel(),(rows.ravel(),cols.ravel())),shape=(len(xy),len(xy))).tocsr()
    free=~(zero|one)
    voltage=one.astype(float)
    voltage[free]=spsolve(mat[free][:,free],-(mat@voltage)[free])
    # One conductor at 1 V and every other Dirichlet conductor at 0 V
    # makes 2*electric energy numerically equal to charge per unit length.
    return float(epsilon_0*np.sum(voltage*(mat@voltage)))


def solve_pair(w,gap,step=.008,wall=1.2,coated=True,substrate_mm=h,substrate_er=er,single=False):
    h=substrate_mm
    left=0 if single else gap/2;right=w/2 if single else left+w
    xs=partition(([0,right,wall] if single else [0,left,right,wall]),step)
    ys=partition(sorted({0,h,h+mask_base,h+copper,h+copper+mask_top,wall}),step)
    x,y=np.meshgrid(xs,ys);original_x=x.copy()
    fraction=np.clip((y[:,0]-h)/copper,0,1)
    for row,f in enumerate(fraction):
        x[row]=np.interp(xs,[0,right,wall],[0,right-f*narrowing/2,wall]) if single else np.interp(xs,[0,left,right,wall],[0,left+f*narrowing/2,right-f*narrowing/2,wall])
    xy=np.stack((x.ravel(),y.ravel()),axis=1);tri=triangles(len(xs),len(ys))
    one=((original_x>=left-1e-12)&(original_x<=right+1e-12)&(y>=h-1e-12)&(y<=h+copper+1e-12)).ravel()
    zero=(((original_x==0)&(not single))|(original_x==wall)|(y==0)|(y==wall)).ravel()
    cx,cy=xy[tri].mean(axis=1).T
    # The published mask thickness differs above bare laminate and copper.
    # Approximate the unreported shoulder by a linear 25-um transition.
    exposed_edge=cx-(right-narrowing/2) if single else np.maximum(left+narrowing/2-cx,cx-(right-narrowing/2))
    mask_height=h+mask_base+(copper+mask_top-mask_base)*np.clip(1-exposed_edge/.025,0,1)
    dielectric=np.where(cy<h,substrate_er,np.where(coated&(cy<=mask_height),mask_er,1.0))
    cd=capacitance(xy,tri,dielectric,zero,one)
    c0=capacitance(xy,tri,np.ones(len(tri)),zero,one)
    if single:
        return dict(width_mm=w,mesh_max_mm=step,outer_wall_mm=wall,coated=coated,substrate_mm=h,substrate_er=substrate_er,effective_er=cd/c0,single_ended_ohms=1/(2*c*math.sqrt(cd*c0)))
    return dict(width_mm=w,gap_mm=gap,mesh_max_mm=step,outer_wall_mm=wall,coated=coated,substrate_mm=h,substrate_er=substrate_er,
                odd_cap_pF_per_m=cd*1e12,vacuum_odd_cap_pF_per_m=c0*1e12,
                effective_er=cd/c0,differential_ohms=2/(c*math.sqrt(cd*c0)))


def check_parallel_plates():
    x,y=np.meshgrid(np.linspace(0,3,31),np.linspace(0,.2,9))
    xy=np.stack((x.ravel(),y.ravel()),axis=1);tri=triangles(x.shape[1],x.shape[0])
    expected=epsilon_0*4.1*3/.2
    actual=capacitance(xy,tri,np.full(len(tri),4.1),(y==0).ravel(),(y==.2).ravel())
    assert abs(actual/expected-1)<1e-10
    return dict(expected_pF_per_m=expected*1e12,simulated_pF_per_m=actual*1e12)


if __name__=='__main__':
    test=check_parallel_plates()
    w,g=default['diff_pair_width'],default['diff_pair_gap']
    samples=[solve_pair(w,g),solve_pair(w,g,.004),solve_pair(w,g,.008,1.8),solve_pair(w,g,coated=False)]
    samples.extend(solve_pair(w,gap) for gap in (.20,.30,.4,.6))
    samples.extend(solve_pair(width,g) for width in (.13,.14,.15,.16,.17,.18))
    assert abs(samples[0]['differential_ohms']-samples[1]['differential_ohms'])<1.5
    assert abs(samples[0]['differential_ohms']-samples[2]['differential_ohms'])<1
    # The 7628 sheet is offered with a thicker outer dielectric. Vary Dk here
    # because design Dk for the exact delivered construction has not been agreed.
    alternate=[solve_pair(width,g,substrate_mm=.21040,substrate_er=dk) for width in (w,.23,.24,.25) for dk in (4.1,4.4,4.7)]
    report=dict(alternative_7628_sensitivity=alternate,source_pcb_sha256=base['sha256'],applied_to_board=False,stack=stack['name'],
                substrate_height_mm=h,substrate_er=er,copper_mm=copper,top_width_reduction_mm=narrowing,
                mask_base_mm=mask_base,mask_over_copper_mm=mask_top,mask_er=mask_er,assumed_mask_shoulder_mm=.025,
                project_default=[w,g],analytical_test=test,samples=samples,
                sources=['https://jlcpcb.com/impedance','https://jlcpcb.com/help/article/user-guide-to-the-jlcpcb-impedance-calculator',
                         'https://www.ti.com/lit/ds/symlink/dp83867is.pdf'],
                limitations=['Assumed cross-section of an external noncoplanar pair above a continuous GND plane.','Two-dimensional quasi-static model. No production tolerances, surface roughness, dispersion, lands, pin fields, connectors, or via transitions.','The KiCad PCB does not declare a fabricated stackup. Fabricator approval and impedance coupon measurement remain open.'])
    (root/'outer-pair-impedance-simulation.json').write_text(json.dumps(report,indent=2)+'\n')
    print([(s['width_mm'],s['gap_mm'],round(s['differential_ohms'],2)) for s in samples])
