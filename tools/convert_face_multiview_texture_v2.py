import argparse,asyncio,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R),str(R/'tools')]
import convert_integrated_face_texture_payload_v1 as convert
from generate_modular_character_parts import single_batch
from server.provider import ProviderError
convert.O=R/'art/characters/explorer_b_face_multiview_meshhair_v2/head/texture_payload'
convert.NAME='face_multiview_meshhair_v2_head_export_gltf'
result=json.loads((convert.O.parent/'generation-result.json').read_text(encoding='utf-8-sig'));assert result['status']=='success'
convert.INPUT_TASK=result['task_id']
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['submit','poll']);a=p.parse_args()
 try:
  with single_batch():asyncio.run(convert.run(a.operation))
 except Exception as e:print(json.dumps({'error':e.code if isinstance(e,ProviderError) else type(e).__name__,'automatic_resubmit':False}));sys.exit(1)
