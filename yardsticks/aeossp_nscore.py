"""Paper reporting score N_AEOSSP (AstroAgentBench appendix 9)."""
import yaml, json, sys
from datetime import datetime
def case_consts(case_dir):
    sats=yaml.safe_load(open(f'{case_dir}/satellites.yaml'))['satellites']
    m=yaml.safe_load(open(f'{case_dir}/mission.yaml'))['mission']
    f=lambda s: datetime.fromisoformat(s.replace('Z','+00:00'))
    H=(f(m['horizon_end'])-f(m['horizon_start'])).total_seconds()
    E=sum(s['resource_model']['battery_capacity_wh'] for s in sats)
    return H,E
def nscore(metrics, case_dir, valid=True):
    if not valid or metrics.get('TAT') is None: return 0.0
    H,E=case_consts(case_dir); c=lambda x:min(1,max(0,x))
    return 100*(0.45*metrics['WCR']+0.20*metrics['CR']+0.20*c(1-metrics['TAT']/H)+0.15*c(1-metrics['PC']/E))
if __name__=='__main__':
    d='AstroAgentBench/benchmarks/aeossp_standard/dataset/cases/test/case_0001'
    print(case_consts(d))
    print(round(nscore({'WCR':3669/5353,'CR':1415/1947,'TAT':1071.23,'PC':18621.35},d),2))
