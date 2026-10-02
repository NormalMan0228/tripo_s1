import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.asset_contract import parse_design
from server.asset_assembly import demo_design
from server.asset_vm import AssetVM
cases=[]
designs=[demo_design(p) for p in ('flower','chest','clock')]
for file in (ROOT/'artifacts').glob('model-benchmark*/*/output.json'):
    try:
        plan,program,_=parse_design(file.read_text(encoding='utf-8'));designs.append((plan,program))
    except Exception:pass
for plan,program in designs:
    ids=[p['id'] for p in plan['parts']];vm=AssetVM(program,ids);trace=[]
    for i in range(120):
        event='spawn' if i==0 else 'click' if i in (1,70) else 'near' if i==5 else 'leave' if i==90 else 'tick'
        inputs={'dt':1/60,'time':i*0.1,'near':int(5<=i<90)}
        try:commands=vm.run(event,inputs)
        except Exception:break
        trace.append({'event':event,'inputs':inputs,'commands':commands,'state':vm.state.copy()})
    cases.append({'program':program,'targets':ids,'trace':trace})
(ROOT/'artifacts/vm-parity.json').write_text(json.dumps(cases),encoding='utf-8')
print('Prepared',len(cases),'programs')
