"""Build private-data-free visual rehearsals from actual saved model outputs."""
import base64,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.asset_contract import parse_design
from server.asset_assembly import fixture_glb
reference='--reference' in sys.argv
name='reference-model-gallery' if reference else 'model-gallery'
cases=('static_vase','windmill','chest') if reference else ('chest','flower','clock')
settings=[(m,'high') for m in ('gpt-6-luna','gpt-5.6-terra','gpt-6-sol','gpt-6-astra')] if reference else [('gpt-6-luna','medium'),('gpt-5.6-terra','medium'),('gpt-6-sol','low'),('gpt-6-astra','high')]
rows=[]
for case in cases:
    for model,effort in settings:
        folder=ROOT/'artifacts'/('model-benchmark-image-reference' if reference else 'model-benchmark-v2')/f'{model}_{effort}_{case}'
        row={'model':model,'effort':effort,'case':case}
        try:
            plan,program,_=parse_design((folder/'output.json').read_text(encoding='utf-8'))
            row['payload']={'schema':1,'plan':plan,'program':program,'provenance':{'geometry':'procedural_proxy'},'runtime':{},
                'blobs':{p['id']:base64.b64encode(fixture_glb(p['shape'],False)).decode() for p in plan['parts']}}
        except Exception as exc:row['error']=type(exc).__name__
        rows.append(row)
(ROOT/'artifacts'/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
print('Prepared',len(rows),'actual saved designs; no new model/API calls')
