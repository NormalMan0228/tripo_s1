"""Submit/resume one prop within the user-authorized review batch."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.config import Settings, read_tripo_key
from server.provider import TripoProvider, ProviderError
from tools.generate_dev_character import upload, quarantine_download, save
from tools.archipelago_queue import assert_authorized, set_status, locked_queue

BASE = ROOT / 'art/maps/archipelago_objects_v1'

async def run(args):
    queue_path = BASE / 'queue.json'
    queue = json.loads(queue_path.read_text(encoding='utf-8'))
    position = next(i for i,item in enumerate(queue['items']) if item['id'] == args.asset)
    item = queue['items'][position]
    assert_authorized(queue,args.asset)
    out = BASE / args.asset
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / 'generation-result.json'
    if result_path.exists() and (out / 'tripo-original.glb').exists():
        print('EXISTING_OBJECT_PRESERVED no_new_task_submitted')
        return
    provider = TripoProvider(Settings(tripo_key=read_tripo_key(args.key_file)))
    task_path, intent_path = out / 'generation-task.json', out / 'generation-intent.json'
    if not task_path.exists():
        if intent_path.exists():
            raise ProviderError('ambiguous_generation_intent_no_resubmit')
        while True:
            with locked_queue() as current:
                active=[entry['id'] for entry in current['items']
                        if entry['review_status'] in ('generating','submitting')]
                reserved=len(active)<3
                if reserved:
                    next(entry for entry in current['items'] if entry['id']==args.asset)['review_status']='submitting'
                    batch=current.get('active_batch',{})
                    batch['max_observed_concurrent']=max(batch.get('max_observed_concurrent',0),len(active)+1)
            if reserved:
                break
            await asyncio.sleep(3)
        before = await provider.balance()
        prompt_file = getattr(args, 'prompt_file', None)
        if prompt_file:
            prompt = prompt_file.read_text(encoding='utf-8').strip()
            assert 0 < len(prompt) <= 1024
            generation_input = {'prompt':prompt, 'negative_prompt':'ground plane, terrain, scenery, water, humans, text, broken rails, thin paper surfaces, jagged low poly, flat billboard foliage, holes, missing supports'}
            route = '/generation/text-to-model'
            source_info = {'prompt':prompt, 'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}
        else:
            token = await upload(provider, args.reference)
            generation_input = {'input':token}
            route = '/generation/image-to-model'
            source_info = {'reference_file':str(args.reference.resolve().relative_to(ROOT)), 'reference_sha256':hashlib.sha256(args.reference.read_bytes()).hexdigest()}
        payload = {**generation_input, 'model':'P2-20260801', 'face_limit':item.get('face_limit',40000),
                   'texture':True, 'pbr':True, 'texture_quality':'extreme',
                   'texture_version':'v3.5-20260815', 'delight':True,
                   }
        if not prompt_file:
            payload.update(texture_alignment='original_image', orientation='align_image')
        save(out / 'generation-request.json', {**{k:v for k,v in payload.items() if k != 'input'},
             **source_info,
             'documentation':'https://developers.tripo3d.ai/en/docs'+route.replace('/generation/','/generation-')+'/p'})
        # The persisted intent makes an uncertain paid submission non-repeatable.
        save(intent_path, {'time':time.time(), 'balance_before':before, 'automatic_resubmit':False})
        response = await provider.request('POST',route,payload)
        task_id = response.get('task_id','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,200}',task_id):
            raise ProviderError('upstream_schema')
        save(task_path, {'task_id':task_id})
        set_status(args.asset,'generating')
        print(json.dumps({'submitted':args.asset,'task_id':task_id}),flush=True)
    task_id = json.loads(task_path.read_text(encoding='utf-8'))['task_id']
    last_progress = None
    for _ in range(720):
        task = await provider.task(task_id)
        state = task.get('status')
        progress = task.get('progress')
        if (state,progress) != last_progress:
            print(json.dumps({'asset':args.asset,'state':state,'progress':progress}),flush=True)
            last_progress = (state,progress)
        if state in ('success','failed','cancelled'):
            break
        await asyncio.sleep(5)
    else:
        raise ProviderError('task_still_running_resume_same_object')
    before = json.loads(intent_path.read_text(encoding='utf-8'))['balance_before']
    after = await provider.balance()
    result = {'asset':args.asset,'task_id':task_id,'status':state,
              'credits_consumed':task.get('credits_consumed'),
              'balance_before':before,'balance_after':after,'balance_delta':before-after}
    if state == 'success':
        result['glb_bytes'] = await quarantine_download(task.get('output',{}).get('model_url',''),out/'tripo-original.glb')
        set_status(args.asset,'needs_local_review')
    else:
        set_status(args.asset,state)
    save(result_path,result)
    print(json.dumps(result),flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset',required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--key-file',type=Path,default=Path.home()/'Desktop/tripo_key.txt')
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (ProviderError, ValueError, AssertionError) as error:
        print(json.dumps({'error':error.code if isinstance(error,ProviderError) else 'invalid_configuration', 'automatic_resubmit':False}),flush=True)
        sys.exit(1)
