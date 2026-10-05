"""Prepare editable Material Maker graphs and Krita-compatible layered texture sources."""
import json, zipfile, io
from pathlib import Path
from PIL import Image
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/source/village_materials'
MM=ROOT/'.tools/material-maker-1.7/material_maker_1_7_windows'
OUT.mkdir(parents=True,exist_ok=True)
graph=json.loads((MM/'examples/wood.ptex').read_text())
for index,n in enumerate(graph['nodes']):
 if n['type']=='material':
  current=json.loads((MM/'nodes/material.mmg').read_text())
  current.update(name=n['name'],node_position=n['node_position'])
  current['parameters'].update(size=9,normal=.24,metallic=0,roughness=.82)
  graph['nodes'][index]=current
 if n['name']=='colorize_2':
  for p in n['parameters']['gradient']['points']:
   bright=p['r']>.4
   p.update(r=.42 if bright else .24,g=.26 if bright else .13,b=.13 if bright else .062)
 if n['type']=='normal_map':n['parameters']['param0']=8
(OUT/'village_timber.ptex').write_text(json.dumps(graph,indent=2))
print('MATERIAL_GRAPH',OUT/'village_timber.ptex')
n=512
x,y=np.meshgrid(np.linspace(0,1,n,endpoint=False),np.linspace(0,1,n,endpoint=False))
grain=(np.sin((x+.008*np.sin(y*19))*180)+np.sin(x*55+y*3))*.5
rgb=np.clip(np.array([112,73,41])+grain[:,:,None]*np.array([13,10,6]),0,255).astype('uint8')
base=Image.fromarray(rgb).convert('RGBA');paint=Image.new('RGBA',(n,n),(0,0,0,0))
buf=io.BytesIO();base.save(buf,format='PNG');b2=io.BytesIO();paint.save(b2,format='PNG')
with zipfile.ZipFile(OUT/'timber_touchup.ora','w') as z:
 z.writestr('mimetype','image/openraster',compress_type=zipfile.ZIP_STORED)
 z.writestr('stack.xml','<image w="512" h="512" name="Village timber touchup"><stack><layer name="Hand paint corrections" src="data/paint.png" opacity="1.0" visibility="visible" composite-op="svg:src-over" x="0" y="0"/><layer name="Procedural oak base" src="data/base.png" opacity="1.0" visibility="visible" composite-op="svg:src-over" x="0" y="0"/></stack></image>')
 z.writestr('data/base.png',buf.getvalue());z.writestr('data/paint.png',b2.getvalue());z.writestr('mergedimage.png',buf.getvalue())
if __name__=='__main__':
 ledger=ROOT/'artifacts/detail-map-20261003/budget.json'
 if ledger.exists():
  d=json.loads(ledger.read_text());events=d['buckets']['character_detail']['scenario']
  if not any(e['name']=='hair-reference' for e in events):events.append({'name':'hair-reference','model':'model_openai-gpt-image-2','quoted_cu':12,'state':'submitted','reference':'art/references/explorer_b_v5/front.png','quality':'Auto','count':1})
  ledger.write_text(json.dumps(d,ensure_ascii=False,indent=2))
