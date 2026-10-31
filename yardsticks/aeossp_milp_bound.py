"""Tighter WCR bound + exact schedule on the MWIS conflict graph (task, overlap, slew-transition conflicts).
Battery is the only relaxed constraint. Same candidate grid as both reference solvers."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import ROOT, AAB, WORK, ASSETS, FFMPEG, AEOSSP_PACK, REVISIT_DATA  # noqa: E402,F401
import sys,json,time,numpy as np
sys.path.insert(0, _os.path.join(AAB, 'solvers/aeossp_standard/mwis_conflict_graph'))
from pathlib import Path
from src.case_io import load_case
from src.candidates import CandidateConfig, generate_candidates
from src.graph import build_conflict_graph
from src.solution_io import write_solution
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import coo_matrix
split,case_id,tl=sys.argv[1],sys.argv[2],float(sys.argv[3])
cd=Path(AAB)/'benchmarks/aeossp_standard/dataset/cases'/split/case_id
t=time.time(); case=load_case(cd); cands,_=generate_candidates(case,CandidateConfig()); g=build_conflict_graph(case,cands); tg=time.time()-t
cands=sorted(cands,key=lambda c:c.candidate_id); idx={c.candidate_id:i for i,c in enumerate(cands)}; n=len(cands)
rows=[];cols=[];r=0
tid={}
for i,c in enumerate(cands): rows.append(tid.setdefault(c.task_id,len(tid))); cols.append(i)
r=len(tid)
for (a,b) in g.reason_edges['transition']|g.reason_edges['overlap']:
    rows+= [r,r]; cols+=[idx[a],idx[b]]; r+=1
A=coo_matrix((np.ones(len(rows)),(rows,cols)),shape=(r,n)).tocsr()
wt={tk.task_id:tk.weight for tk in case.tasks.values()} if isinstance(case.tasks,dict) else {tk.task_id:tk.weight for tk in case.tasks}
W=sum(wt.values()); w=-np.array([wt[c.task_id] for c in cands])
t=time.time(); ip=milp(w,constraints=LinearConstraint(A,-np.inf,1),bounds=Bounds(0,1),integrality=np.ones(n),options={'time_limit':tl,'disp':False,'mip_rel_gap':1e-4})
out=dict(case=f'{split}/{case_id}',n_cand=n,edges=g.stats.edge_count,trans_edges=len(g.reason_edges['transition']),prep_s=round(tg,1),milp_s=round(time.time()-t,1),status=ip.message[:50],
         inc_WCR=round(-ip.fun/W,4) if ip.x is not None else None, dual_WCR=round(-ip.mip_dual_bound/W,4))
if ip.x is not None:
    sel=[cands[i] for i in np.where(ip.x>0.5)[0]]
    od=Path(WORK)/'aeossp'/'milp'/split/case_id; od.mkdir(parents=True,exist_ok=True)
    write_solution(od/'solution.json',sel) if 'solution' not in str(write_solution.__code__.co_varnames[:1]) else write_solution(od,sel)
    out['n_sel']=len(sel)
print(json.dumps(out))
