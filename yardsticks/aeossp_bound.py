"""Upper bound on WCR: each task at most once; no time overlap of actions on one satellite.
Slew, settling and battery are relaxed (ignored), so the bound is valid but optimistic."""
import json,sys,yaml,time,numpy as np
from collections import defaultdict
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import coo_matrix
cand_path, case_dir, tl = sys.argv[1], sys.argv[2], float(sys.argv[3])
C=json.load(open(cand_path)); n=len(C)
tasks=yaml.safe_load(open(f'{case_dir}/tasks.yaml'))['tasks']
W=sum(t['weight'] for t in tasks)
tid={}; rows=[];cols=[]
for i,c in enumerate(C):
    r=tid.setdefault(c['task_id'],len(tid)); rows.append(r); cols.append(i)
nt=len(tid); bysat=defaultdict(list)
for i,c in enumerate(C): bysat[c['satellite_id']].append(i)
r0=nt
for s,idx in bysat.items():
    pts=sorted({C[i]['start_offset_s'] for i in idx}); pid={p:k for k,p in enumerate(pts)}
    P=np.array(pts)
    for i in idx:
        a,b=C[i]['start_offset_s'],C[i]['end_offset_s']
        lo=np.searchsorted(P,a); hi=np.searchsorted(P,b)   # start points in [a,b)
        for k in range(lo,hi): rows.append(r0+k); cols.append(i)
    r0+=len(pts)
A=coo_matrix((np.ones(len(rows)),(rows,cols)),shape=(r0,n)).tocsr()
w=-np.array([c['task_weight'] for c in C])
out={'n_cand':n,'n_rows':r0,'total_weight':W}
t=time.time(); lp=milp(w,constraints=LinearConstraint(A,-np.inf,1),bounds=Bounds(0,1))
out['LP_WCR_bound']=round(-lp.fun/W,4); out['lp_s']=round(time.time()-t,1)
t=time.time(); ip=milp(w,constraints=LinearConstraint(A,-np.inf,1),bounds=Bounds(0,1),integrality=np.ones(n),options={'time_limit':tl,'disp':False})
out['MILP_status']=ip.message[:60]; out['MILP_incumbent_WCR']=round(-ip.fun/W,4) if ip.x is not None else None
out['MILP_dual_WCR_bound']=round(-ip.mip_dual_bound/W,4) if getattr(ip,'mip_dual_bound',None) is not None else None
out['milp_s']=round(time.time()-t,1); print(json.dumps(out))
