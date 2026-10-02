"""Deterministic numeric boundary and rollback parity corpus for both runtimes."""
import json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.asset_vm import AssetVM,ProgramError
cases=[]
def add(label,expression,inputs=None,event='tick'):
    p={'version':1,'state':{'value':17},'functions':{},'events':{'tick':[['store','value',expression]]}}
    vm=AssetVM(p,[])
    try:commands=vm.run(event,inputs);ok=True
    except ProgramError:commands=[];ok=False
    cases.append({'label':label,'program':p,'event':event,'inputs':inputs or {},'ok':ok,'state':vm.state,'commands':commands})
values=[-1000000,-360,-1,-.1,-1e-100,0,1e-100,.1,1,360,1000000]
for a in values:
    for b in values:add(f'mod({a},{b})',['mod',a,b])
for op in ['add','sub','mul','div','min','max','lt','gt','eq']:
    for a,b in [(-1e6,1e6),(.1,.3),(1,0),(-.5,-.25),(1e-100,1e-100)]:add(f'{op}({a},{b})',[op,a,b])
for t in [-1e6,-100000,-.1,0,99999.99,100000,1e6]:add('time wrap '+str(t),['input','time'],{'time':t})
for inputs in [{'dt':True},{'near':'1'},{'bad':1},{'time':1e6+1}]:add('bad input '+str(inputs),1,inputs)
add('unknown event',1,event='purchase')
rng=random.Random(811)
def expression(depth):
    if depth==0:return rng.choice([-.1,.1,.3,-1,0,1,6,24,360])
    return [rng.choice(['add','sub','mul','div','mod','min','max']),expression(depth-1),expression(depth-1)]
for i in range(200):add('expression '+str(i),expression(3))
(ROOT/'artifacts/vm-edges.json').write_text(json.dumps(cases),encoding='utf-8')
print('Prepared',len(cases),'numeric and rejection cases')
