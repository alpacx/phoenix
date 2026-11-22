"""Resolve local power-stage placement using one binary per physical footprint pose."""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.optimize import Bounds,LinearConstraint,milp

def choose(groups,allowed):
    # Each configuration is a tuple of footprint poses. Each physical component is
    # selected once by its parent's configuration. Pure-CAD clearance is disjunctive.
    configs=[];poses={};by_group=[];links={}
    for i,g in enumerate(groups):
        options=[]
        for k,(score,row) in enumerate(g):
            if not allowed[i]&(1<<k):continue
            cid=len(configs);configs.append((i,k,score));options.append(cid)
            for ref,xy,q,face,r in row:
                key=(ref,r)
                if key not in poses:poses[key]=len(poses);links[key]=[]
                links[key].append(cid)
        by_group.append(options)
    n=len(configs);size=n+len(poses);ri=[];ci=[];data=[];lo=[];hi=[]
    def add(indices,values,low,high):
        ri.extend([len(lo)]*len(indices));ci.extend(indices);data.extend(values);lo.append(low);hi.append(high)
    for group in by_group:add(group,[1]*len(group),1,1)
    for key,v in poses.items():
        ids=links[key];add(ids+[n+v],[1]*len(ids)+[-1],0,0)
    keys=list(poses);rects=np.array([k[1] for k in keys])
    for i,(ref,r) in enumerate(keys):
        layer,x,y,z,w=r
        mask=(rects[:i,0]==layer)&(rects[:i,1]<z+.1)&(x<rects[:i,3]+.1)&(rects[:i,2]<w+.1)&(y<rects[:i,4]+.1)
        for j in np.flatnonzero(mask):
            if keys[j][0]!=ref:add([n+i,n+j],[1,1],-np.inf,1)
    A=coo_matrix((data,(ri,ci)),shape=(len(lo),size)).tocsc()
    result=milp(c=np.zeros(size),integrality=np.r_[np.zeros(n),np.ones(len(poses))],bounds=Bounds(np.zeros(size),np.ones(size)),constraints=LinearConstraint(A,lo,hi),options={'time_limit':45})
    if result.x is None:return None,result.message
    chosen=[]
    for opts in by_group:
        # If multiple alternatives differ only by electrically oriented but geometrically
        # identical parts, select the lowest-score compatible whole configuration.
        live=[key for key in opts if result.x[key]>1e-6]
        selected=min(live,key=lambda k:configs[k][2]);chosen.append(configs[selected][:2])
    return chosen,result.message
