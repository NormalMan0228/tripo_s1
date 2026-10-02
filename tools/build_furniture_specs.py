"""Public provenance catalog and private renderer input; no keys or accounts exported."""
import base64,csv,hashlib,json,shutil,sqlite3,struct,sys
from PIL import Image
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.provider import validate_glb
from server.stored_assets import read_glb
OUT=ROOT/'artifacts/picture-furniture-20261002';PUBLIC=OUT/'public';PUBLIC.mkdir(exist_ok=True)
rows=[];render=[]

def add(key,title,value,assets,reference='없음',notes='',requested_faces=3000,source=''):
    value=json.loads(json.dumps(value));value.pop('original_plan',None);value.pop('runtime',None)
    proof=value['provenance'];parts=[];blobs={};totals={'triangles':0,'vertices':0,'texture_pixels':0,'draw_calls':0,'bytes':0}
    for part in value['plan']['parts']:
        blob=read_glb(assets,part['file'],part['sha256']);stats={};doc=validate_glb(blob,allow_textures=proof.get('material')=='textured',stats=stats)
        triangles=sum(doc['accessors'][p.get('indices',p['attributes']['POSITION'])]['count']//3 for m in doc['meshes'] for p in m['primitives']);stats['triangles']=triangles
        for field in totals:totals[field]+=stats[field]
        parts.append({k:part.get(k) for k in ('id','parent','prompt','size','position','rotation','pivot','color')}|{'stats':stats,'embedded_images':len(doc.get('images',[])),'sha256':hashlib.sha256(blob).hexdigest()})
        blobs[part['id']]=base64.b64encode(blob).decode()
    llm=proof.get('model','게임 설계 LLM 호출 없음');effort=proof.get('effort','해당 없음')
    if key=='h3-repaired':
        llm='본체 보정: gpt-6-luna / 조립: 작성된 설계';effort='본체 medium';notes+=' 최초 20 + 본체 수정 25 = 누적45. 원본 동적 상자의 비용과 중복되므로 표의 비용을 단순 합산하지 않습니다.'
    tripo=proof.get('tripo_model')
    if not tripo:tripo='P2-20260801 (실험 설정으로 확인)'
    row={'id':key,'title':title,'llm':llm,'effort':effort,'tripo_model':tripo,'format':proof.get('format','classic' if proof.get('model') else '작성된 설계'),
         'input':reference,'motion':proof.get('motion','dynamic' if len(parts)>1 else 'static'),'material':proof.get('material','mesh'),'part_count':len(parts),
         'requested_face_limit_per_part':requested_faces,'quad':False,'pbr':proof.get('material')=='textured','export_uv_requested':proof.get('material')=='textured',
         'tripo_credits':proof.get('tripo_credits_consumed'),'image_refinement_credits':proof.get('image_refinement_credits',0),'usage':proof.get('usage'),
         'functions':list(value['program']['functions']),'events':list(value['program']['events']),'stats':totals,'parts':parts,'notes':notes,'evidence':source,'thumbnail':key+'.png'}
    if key=='h3-repaired':row['image_refinement_credits']=5
    rows.append(row);render.append({'id':key,'title':title,'spec':row,'manifest':value,'blobs':blobs})

data=ROOT/'artifacts/studio-review-data'
with sqlite3.connect((data/'world.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
    for aid,raw in conn.execute('SELECT asset_id,manifest FROM studio_assets WHERE asset_id IN (SELECT asset_id FROM objects WHERE owner_id=(SELECT id FROM users WHERE username=?)) ORDER BY asset_id',('workshop',)):
        if aid.startswith('picture-20261002-'):continue
        m=json.loads(raw)
        if m['provenance'].get('geometry')!='tripo':continue
        key=aid.removeprefix('review-')
        if not aid.startswith('review-'):key='llm-windmill' if len(m['plan']['parts'])>1 else 'llm-vase'
        reference='텍스트만'
        if key=='image-refinement':reference='그림 → Luna → Seedream v5 보정 → H3'
        if key=='h3-repaired':reference='기존 결과 그림 → 본체 보정 → H3 / 뚜껑 재사용'
        note='동작은 부품 회전 코드이며 Tripo 캐릭터 애니메이션 API를 사용하지 않았습니다.' if len(m['plan']['parts'])>1 else ''
        if key.startswith('h3-dynamic'):note+=' 본체에 고정 뚜껑이 함께 생성된 원본입니다.'
        if key=='llm-windmill':note+=' 본체에 고정 날개가 남아 있는 결과입니다.'
        add(key,m['plan']['title'],m,data/'assets',reference,note,source='기존 비교 기록 및 검토 공방 manifest')

for kind in ('static','dynamic'):
    path=OUT/kind/'assembly.json'
    if not path.exists():continue
    m=json.loads(path.read_text());add('picture-'+kind,'그림 입력 · '+('정적 상자' if kind=='static' else '열리는 상자'),m,OUT/'server-data/assets',
        '원본 그림 → Luna high + H3 직접 입력' if kind=='static' else '원본 그림 → Luna high → Seedream v5 부품별 보정 → H3',
        '이번 생성. 기존 텍스트 실험과 그림·프롬프트·effort가 달라 엄밀한 단일 변수 A/B 비교는 아닙니다.',source='picture-furniture-20261002/'+kind+'/request-spec.json + result.json')
    row=rows[-1];row['image_refiner']=None if kind=='static' else 'seedream_v5';row['refiner_resolution']=None if kind=='static' else '2K'
    row['animation_source']='없음' if kind=='static' else 'Luna가 생성한 제한된 숫자 함수·이벤트, Godot 런타임 부품 회전'
    row['blender_used']=False;row['render_engine']='Godot 4.7.2'
    usage=row.get('usage') or {};row['actual_gpt_api_charge']=0
    row['api_equivalent_krw']=round(((usage.get('input_tokens',0)-usage.get('cached_input_tokens',0))*.1+usage.get('cached_input_tokens',0)*.01+usage.get('output_tokens',0)*.5)/1000000*1400,2)
    row['cost_basis']='2026-10-02 기록 단가, gpt-6-luna 입력/캐시/출력 100만 토큰당 $0.10/$0.01/$0.50, 환율1400 가정. CLI 전체 맥락 포함 참고치, 실제 API 청구 아님.'
    if kind=='dynamic':
        row['refined_images']={part:{'file':'refined-'+part+'.png','actual_resolution':list(Image.open(PUBLIC/('refined-'+part+'.png')).size)} for part in ('body','lid')}

old=ROOT/'artifacts/furniture/paint-test-01'
for kind,title in [('chair','초기 의자'),('table','초기 원탁'),('bookshelf','초기 책장')]:
    req=json.loads((old/(kind+'-request.json')).read_text());result=json.loads((old/(kind+'-status.json')).read_text());stats=json.loads((old/'test-results.json').read_text())['items'][kind]['original']
    rows.append({'id':'initial-'+kind,'title':title,'llm':'게임 설계 LLM 호출 없음','effort':'해당 없음','tripo_model':req['model'],'format':'개발자가 작성한 프롬프트','input':'텍스트만','motion':'static','material':'mesh','part_count':1,'requested_face_limit_per_part':req['face_limit'],'quad':req['quad'],'pbr':req['pbr'],'export_uv_requested':req['export_uv'],'tripo_credits':result['credits_consumed'],'image_refinement_credits':0,'functions':[],'events':[],'stats':stats,'parts':[],'notes':'초기 개발자 에셋. Blender에서 색칠용 메시를 별도 준비한 실험이며 플레이어 런타임 경로와 다릅니다.','thumbnail':'initial-furniture.png','request':req})
shutil.copy2(old/'furniture-comparison.png',PUBLIC/'initial-furniture.png')
shutil.copy2(OUT/'reference.jpg',PUBLIC/'reference.jpg')
value={'rows':rows,'reference':json.loads((OUT/'reference-spec.json').read_text()),'notes':['LLM 명세는 게임 설계 호출 기준입니다. 개발 대화 자체의 모델과 다릅니다.','face_limit는 요청값이며 실제 삼각형 수와 같지 않을 수 있습니다. 삼각형은 파일 내 mesh primitive 기준, vertices/draw calls는 GLB 인스턴스 기준입니다.','기존 결과는 재생성하지 않았습니다. 키·계정·DB·signed URL은 공개 자료에 포함하지 않습니다.']}
(PUBLIC/'specs.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
template=ROOT/'tools/furniture_specs.html'
if template.exists():
    observation='정적: 목재·세이지색 뚜껑·잎 문양·잠금장식이 재현됐습니다. 동적: 빈 본체와 독립된 뚜껑, 열기/닫기는 생성됐지만 닫힘 상태에서 틈이 있고 잠금장식과 뚜껑 장식 일부가 빠졌습니다. 내부 텍스처도 얼룩이 보입니다. 자동 조립 원본을 보존했으며 맞춤 보정은 적용하지 않았습니다. 실제 삼각형은 정적 2,537개 / 동적 합계 4,848개입니다. 이번 실측은 30+70=100크레딧, 잔액 23,655입니다.'
    (PUBLIC/'index.html').write_text(template.read_text(encoding='utf-8').replace('__SPEC_DATA__',json.dumps(value,ensure_ascii=False).replace('<','\\u003c')).replace('__OBSERVATION__',observation),encoding='utf-8')
(OUT/'render-input.json').write_text(json.dumps(render,ensure_ascii=False),encoding='utf-8')
fields=['id','title','llm','effort','tripo_model','input','motion','material','part_count','requested_face_limit_per_part','tripo_credits','image_refinement_credits','notes']
with (PUBLIC/'specs.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
print(json.dumps({'catalog_rows':len(rows),'renderable':len(render),'new_ready':sum(r['id'].startswith('picture-') for r in rows)}))
