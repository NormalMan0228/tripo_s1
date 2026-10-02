"""Three explicitly requested low-cost furniture generations; no automatic retry."""
import argparse,json,sys,time,struct
from pathlib import Path
from urllib.parse import urlparse
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.config import read_tripo_key
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/furniture/paint-test-01'
BASE='https://openapi.tripo3d.ai/v3'
PROMPTS={
 'chair':'One stylized cozy game wooden dining chair, full object, four sturdy straight legs, thick gently rounded square seat, solid rounded rectangular backrest with one small circular cutout. Stable functional furniture, clean simple silhouette, chunky beveled edges, no cushion, no arms, no ornaments, no other objects, no floor or scenery. Neutral unpainted solid geometry, suitable for a player to paint.',
 'table':'One stylized cozy game round wooden dining table, full object, a thick perfectly circular flat tabletop with softly beveled edge, four short sturdy evenly spaced legs with open space beneath. Simple clean functional furniture, stable silhouette, no cloth, no dishes, no other objects, no floor or scenery. Neutral unpainted solid geometry, suitable for a player to paint.',
 'bookshelf':'One stylized cozy game low empty wooden bookshelf, full object, two wide open shelf compartments stacked vertically, solid side panels and back panel, thick rounded top, four short block feet. Clean chunky furniture silhouette, shelves completely empty, no books or decorations, no other objects, no floor or scenery. Neutral unpainted solid geometry, suitable for a player to paint.'
}
def save(name,d):
 (OUT/name).write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('op',choices=['submit','poll','download','balance']);p.add_argument('--item',choices=PROMPTS);p.add_argument('--key-file',type=Path,required=True);a=p.parse_args()
 OUT.mkdir(parents=True,exist_ok=True)
 with httpx.Client(headers={'Authorization':'Bearer '+read_tripo_key(a.key_file)},timeout=90,follow_redirects=False) as c:
  def req(method,path,**kw):
   r=c.request(method,BASE+path,**kw)
   if r.status_code!=200:raise RuntimeError('http_'+str(r.status_code))
   if 'application/json' not in r.headers.get('content-type',''):raise RuntimeError('non_json')
   d=r.json()
   if d.get('code')!=0:raise RuntimeError('provider_code_'+str(d.get('code')))
   return d['data']
  if a.op=='balance':
   d=req('GET','/account/balance');safe={k:d.get(k) for k in ['balance','frozen']};save('balance-latest.json',safe);print(json.dumps(safe));return
  if not a.item:raise RuntimeError('item_required')
  taskfile=OUT/(a.item+'-task.json')
  if a.op=='submit':
   if taskfile.exists():print(json.dumps({'existing_task':a.item}));return
   balance=req('GET','/account/balance');save(a.item+'-balance-before.json',{k:balance.get(k) for k in ['balance','frozen']})
   if balance['balance']<30:raise RuntimeError('low_balance')
   payload={'model':'v3.1-20260211','prompt':PROMPTS[a.item],'texture':False,'pbr':False,'export_uv':True,'face_limit':6000,'quad':False,'smart_low_poly':False,'generate_parts':False,'geometry_quality':'standard'}
   with (OUT/(a.item+'-intent.json')).open('x') as f:json.dump({'time':time.time(),'automatic_retry':False},f)
   save(a.item+'-request.json',payload)
   d=req('POST','/generation/text-to-model',json=payload)
   save(a.item+'-task.json',{'task_id':d['task_id']});print(json.dumps({'submitted':a.item,'task_id':d['task_id']}));return
  task=json.loads(taskfile.read_text())['task_id']
  if '/' in task:raise RuntimeError('invalid_task')
  d=req('GET','/tasks/'+task)
  safe={k:d.get(k) for k in ['status','progress','credits_consumed','error_code'] if k in d};safe['item']=a.item;safe['output_fields']=list(d.get('output',{}));save(a.item+'-status.json',safe);print(json.dumps(safe))
  if a.op=='download':
   if d.get('status')!='success':raise RuntimeError('not_complete')
   url=d['output']['model_url'];u=urlparse(url)
   if u.scheme!='https' or u.username or u.password or u.port not in (None,443) or u.hostname not in ('tripo-data.rg1.data.tripo3d.com','cdn.tripo3d.ai'):raise RuntimeError('unapproved_host')
   with httpx.Client(timeout=90,follow_redirects=False) as dl:
    with dl.stream('GET',url) as response:
     if response.status_code!=200:raise RuntimeError('download_http_'+str(response.status_code))
     blob=bytearray()
     for chunk in response.iter_bytes():
      blob.extend(chunk)
      if len(blob)>50*1024*1024:raise RuntimeError('oversized_asset')
   if blob[:4]!=b'glTF' or struct.unpack_from('<I',blob,8)[0]!=len(blob):raise RuntimeError('invalid_glb')
   (OUT/(a.item+'-original.glb')).write_bytes(blob);print(json.dumps({'saved':a.item+'-original.glb','bytes':len(blob)}))
if __name__=='__main__':
 try:main()
 except Exception as e:
  print(json.dumps({'error':str(e) if isinstance(e,RuntimeError) else type(e).__name__,'automatic_resubmit':False}));sys.exit(1)
