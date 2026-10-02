"""Re-grade all saved trials by requested behavior, not merely syntax success."""
import csv,html,json,math,statistics,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.asset_contract import parse_design
from server.asset_vm import AssetVM
OUT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'artifacts/model-benchmark'
RATES={'gpt-6-luna':(.1,.01,.5),'gpt-5.6-luna':(.2,.02,1.2),'gpt-5.6-terra':(2,.2,12),'gpt-5.6-sol':(4,.4,20),'gpt-6-sol':(2,.2,10),'gpt-6-astra':(10,1,50)}

def semantic(plan,program,case):
    vm=AssetVM(program,[p['id'] for p in plan['parts']]);poses={};time=0.;near=False
    def event(name):
        nonlocal near
        if name=='near':near=True
        elif name=='leave':near=False
        for c in vm.run(name,{'time':time,'near':int(near)}):poses[(c['target'],c['op'])]=c['value']
    def tick(seconds):
        nonlocal time
        for _ in range(round(seconds*60)):
            time+=1/60
            for c in vm.run('tick',{'dt':1/60,'time':time,'near':int(near)}):poses[(c['target'],c['op'])]=c['value']
        return poses.copy()
    def difference(a,b):return abs((a-b+180)%360-180)
    checks={};event('spawn');baseline=tick(.1)
    checks['custom_api']=len(program['functions'])>0
    if case=='chest':
        lids=[p for p in plan['parts'] if 'lid' in p['id'].lower()]
        checks['separate_lid']=len(lids)==1 and len(plan['parts'])>=2
        if not lids:return checks
        lid=lids[0];key=(lid['id'],'rotate_x')
        checks['rear_pivot']=abs(lid['pivot'][2]+.5)<.01
        event('click');early=tick(1/60);opened=tick(2)
        checks['smooth_open']=.01<abs(early.get(key,0))<94.9
        checks['open_95_degrees']=abs(opened.get(key,0)+95)<2
        event('click');closed=tick(2)
        checks['closes']=abs(closed.get(key,100))<2
    elif case=='clock':
        minutes=[p['id'] for p in plan['parts'] if 'minute' in p['id'].lower()]
        hours=[p['id'] for p in plan['parts'] if 'hour' in p['id'].lower()]
        checks['separate_hands']=len(minutes)==1 and len(hours)==1
        if not minutes or not hours:return checks
        keys=[(minutes[0],'rotate_z'),(hours[0],'rotate_z')]
        start=tick(1);end=tick(10)
        checks['minute_period_60s']=abs(difference(end.get(keys[0],0),start.get(keys[0],0))-60)<1
        checks['hour_period_720s']=abs(difference(end.get(keys[1],0),start.get(keys[1],0))-5)<.2
        event('click');pause_start=tick(.1);pause_end=tick(2)
        checks['pause_both']=all(k in pause_end and difference(pause_end[k],pause_start[k])<.01 for k in keys)
        event('click');resumed=tick(1/60)
        checks['resume_without_jump']=all(difference(resumed.get(k,0),pause_end.get(k,0))<.5 for k in keys)
    elif case=='flower':
        petals=[p['id'] for p in plan['parts'] if 'petal' in p['id'].lower()]
        checks['six_petals']=len(petals)==6
        event('near');early=tick(1/60);opened=tick(2)
        changed=lambda snapshot,p:any(abs(snapshot.get((p,op),0)-baseline.get((p,op),0))>5 for op in ('rotate_x','rotate_y','rotate_z'))
        checks['all_open']=len(petals)==6 and all(changed(opened,p) for p in petals)
        checks['smooth_open']=any(0<abs(early.get(k,0)-baseline.get(k,0))<abs(v-baseline.get(k,0)) for k,v in opened.items() if k[0] in petals)
        event('leave');closed=tick(3)
        checks['close_on_leave']=all(abs(closed.get(k,0)-baseline.get(k,0))<2 for k in opened if k[0] in petals)
        hues=[]
        for _ in range(4):
            event('click');tick(.1);hues.append(tuple((k,v) for k,v in sorted(poses.items()) if k[1]=='hue'))
        checks['three_color_cycle']=bool(hues[0]) and len(set(hues[:3]))==3 and hues[0]==hues[3]
    elif case=='static_vase':
        checks.pop('custom_api')
        checks['one_static_part']=len(plan['parts'])==1 and plan['parts'][0]['id']=='vase'
        event('near');event('click');tick(2);event('leave');tick(2)
        checks['no_visual_motion']=poses==baseline
    elif case=='windmill':
        parts={p['id']:p for p in plan['parts']}
        checks['separate_rotor']=set(parts)=={'body','rotor'} and parts['rotor']['parent']=='body'
        key=('rotor','rotate_z');start=tick(.5);end=tick(1)
        checks['four_second_period']=key in end and abs(difference(end[key],start.get(key,0))-90)<1
        checks['stationary_body']=not any(k[0]=='body' and k[1].startswith('rotate') and abs(v)>.01 for k,v in poses.items())
        event('click');stopped=tick(.1);later=tick(2)
        checks['pause']=key in stopped and difference(stopped[key],later.get(key,0))<.01
        event('click');resumed=tick(1/60)
        checks['resume_without_jump']=key in stopped and difference(resumed.get(key,0),stopped[key])<2
    elif case=='lantern':
        checks['two_parts']={p['id'] for p in plan['parts']}=={'base','lamp'}
        key=('lamp','emission');event('near');early=tick(1/60);bright=tick(2)
        checks['smooth_brightness']=0<early.get(key,0)<2
        checks['target_brightness']=abs(bright.get(key,0)-2)<.05
        event('leave');dark=tick(2);checks['off_after_leave']=abs(dark.get(key,100))<.05
        hues=[]
        for _ in range(4):event('click');tick(.1);hues.append(poses.get(('lamp','hue')))
        checks['three_color_cycle']=None not in hues and len(set(hues[:3]))==3 and hues[0]==hues[3]
        checks['stationary_geometry']=not any(k[1].startswith('rotate') or k[1]=='offset_y' for k in poses)
    elif case=='mobile':
        parts={p['id']:p for p in plan['parts']};pendants=['pendant_'+str(i) for i in range(1,4)]
        checks['four_parts']=set(parts)=={'beam',*pendants}
        checks['hanging_pivots']=all(p in parts and parts[p]['parent']=='beam' and abs(parts[p]['pivot'][1]-.5)<.001 for p in pendants)
        snapshots=[tick(.2) for _ in range(20)];keys=[(p,'rotate_z') for p in pendants]
        checks['all_sway']=all(len({round(s.get(k,0),2) for s in snapshots})>4 for k in keys)
        checks['bounded_amplitude']=all(abs(s.get(k,0))<=20.01 for s in snapshots for k in keys)
        checks['different_phases']=any(len({round(s.get(k,0),2) for k in keys})==3 for s in snapshots)
        event('click');stopped=tick(.1);later=tick(2)
        checks['pause_all']=all(k in stopped and abs(stopped[k]-later.get(k,100))<.01 for k in keys)
        event('click');resumed=tick(1/60)
        checks['resume_without_jump']=all(abs(resumed.get(k,100)-stopped.get(k,0))<2 for k in keys)
    else:
        checks['known_test_case']=False
    # A longer time input probes wrap behavior separately from ordinary frames.
    for timestamp in (59.99,60,719.99,720,99999.99,100000,1000000):vm.run('tick',{'dt':.1,'time':timestamp})
    checks['large_time_safe']=True
    return checks

def report():
    rows=[]
    for path in sorted(OUT.glob('*/result.json')):
        value=json.loads(path.read_text(encoding='utf-8'));checks={}
        if value['status']=='validated':
            try:
                plan,program,_=parse_design((path.parent/'output.json').read_text(encoding='utf-8'))
                checks=semantic(plan,program,value['case'])
            except Exception:checks['semantic_execution']=False
        value['semantic_checks']=checks
        value['semantic_pass']=bool(checks) and all(checks.values())
        inp,cache,out=RATES[value['model']];usage=value.get('usage') or {}
        input_tokens=usage.get('input_tokens',0);cached=usage.get('cached_input_tokens',0)
        # CLI output_tokens already includes reasoning_output_tokens; don't add twice.
        output_tokens=usage.get('output_tokens',0)
        value['usage_reported']='input_tokens' in usage and 'output_tokens' in usage
        value['api_equivalent_usd']=(max(0,input_tokens-cached)*inp+cached*cache+output_tokens*out)/1e6 if value['usage_reported'] else None
        value['api_uncached_usd']=(input_tokens*inp+output_tokens*out)/1e6 if value['usage_reported'] else None
        prompt=path.parent/'prompt.txt'
        value['prompt_sha256']=hashlib.sha256(prompt.read_bytes()).hexdigest() if prompt.exists() else None
        value['cost_note']='Counterfactual API cost of CLI token counts including Codex context overhead; NOT a bill, nor a measured direct API request.'
        (path.parent/'graded.json').write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8');rows.append(value)
    summary=[]
    for model in RATES:
        for effort in ('low','medium','high','xhigh','max','ultra'):
            group=[r for r in rows if r['model']==model and r['effort']==effort]
            if not group:continue
            known=[r for r in group if r['usage_reported']]
            summary.append({'model':model,'effort':effort,'trials':len(group),
                'runtime_pass':sum(r['status']=='validated' for r in group),'semantic_pass':sum(r['semantic_pass'] for r in group),
                'mean_seconds':round(statistics.mean(r['seconds'] for r in group),1),
                'mean_api_equivalent_krw':round(statistics.mean(r['api_equivalent_usd'] for r in known)*1400,2) if known else None,
                'mean_uncached_krw':round(statistics.mean(r['api_uncached_usd'] for r in known)*1400,2) if known else None,
                'usage_reported':len(known)})
    (OUT/'summary.json').write_text(json.dumps({'assumed_krw_per_usd':1400,'rates_date':'2026-10-02','summary':summary,'results':rows},indent=2,ensure_ascii=False),encoding='utf-8')
    with (OUT/'summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        if summary:w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    table=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in r)+'</tr>' for r in summary)
    detail=''
    for r in rows:
        relative=r['model']+'_'+r['effort']+'_'+r['case']+'/output.json'
        result_link=('<a href="'+html.escape(relative)+'">생성 결과 JSON</a>') if (OUT/relative).is_file() else '<p>공개 검사를 통과한 저장 결과가 없습니다.</p>'
        detail+='<details><summary>'+html.escape(r['model']+' / '+r['effort']+' / '+r['case']+' — '+('PASS' if r['semantic_pass'] else 'REVIEW'))+'</summary><pre>'+html.escape(json.dumps(r.get('semantic_checks') or r.get('validation_error'),ensure_ascii=False,indent=2))+'</pre>'+result_link+'</details>'
    doc='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Tripothon · 모델 비교 실험</title><style>body{font:16px/1.6 system-ui;background:#172f31;color:#e9e4d5;max-width:1200px;margin:40px auto;padding:20px}h1{color:#e6bc71}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:12px;text-align:left;border-bottom:1px solid #49635e}th{background:#304d49}details{padding:14px;border-bottom:1px solid #49635e}a{color:#c9dba1}pre{white-space:pre-wrap}.note{background:#304d49;padding:20px;border-radius:14px}.scroll{overflow:auto}</style><h1>작은 가구, 같은 과제, 다른 모델</h1><p>Codex 구독으로 실제 실행한 결과 · Blender / 유료 GPT API 호출 없음</p><div class="note">모델별 동일 프롬프트로 상자·꽃 조명·시계를 생성했습니다. 실행 통과와 요구 동작 충족은 별도 점수입니다. 설정당 3개 과제의 소규모 실험이며 생산 환경 신뢰도의 통계적 증거가 아닙니다.<br>API 환산 금액은 CLI가 보고한 입력·캐시·추론 포함 출력 토큰을 공식 단가에 대입한 참고치입니다. Codex의 약 1만 토큰 맥락이 포함되어 순수 API 호출보다 클 수 있습니다. 실제 API 결제액 0원. 환율은 1,400원 가정, 세금 제외. 사용량이 누락된 실행은 무료로 계산하지 않고 비용 평균에서 제외합니다. 부품 이름을 이용한 행동 검사에는 정답을 놓치는 경우도 있으므로 시각 품질 점수로 해석하면 안 됩니다.</div><h2>설정별 결과</h2><div class="scroll"><table><tr><th>모델</th><th>effort</th><th>과제</th><th>실행 통과</th><th>동작 충족</th><th>평균 초</th><th>API 환산 원</th><th>캐시 없이 원</th><th>사용량 확인</th></tr>'''+table+'''</table></div><h2>실패도 그대로 보관</h2>'''+detail+'''<p>단가 출처: <a href="https://developers.openai.com/api/docs/pricing">OpenAI pricing</a> · <a href="https://developers.openai.com/api/docs/models/gpt-6-sol">Sol</a> · <a href="https://developers.openai.com/api/docs/models/gpt-5.6-terra">Terra</a></p></html>'''
    if any(r.get('experiment')=='one_repair_of_failed_design' for r in rows):
        doc=doc.replace('모델별 동일 프롬프트로 상자·꽃 조명·시계를 생성했습니다.', '이 보고서는 최초 생성에서 실패한 사례만 모아 동일 모델에 한 번 수정 요청한 실험입니다. 전체 생성 성공률이 아니라 실패 후 회복 결과입니다. 시간과 API 환산 비용은 최초 요청과 수정 요청의 합계입니다. 각 수정 프롬프트에는 해당 오류와 이전 출력이 포함됩니다.').replace('설정당 3개 과제의 소규모 실험이며','선택된 실패 사례의 소규모 실험이며')
    if any(r['case'] not in ('chest','flower','clock') for r in rows) and not any(r.get('experiment')=='image_reference_publication_v2' for r in rows):
        doc=doc.replace('모델별 동일 프롬프트로 상자·꽃 조명·시계를 생성했습니다.', '추가 실험은 정적 꽃병·풍차·근접 조명·흔들리는 모빌을 동일한 요청으로 생성합니다. 기존 세 과제와 별도로 해석해야 합니다.').replace('설정당 3개 과제의 소규모 실험이며','설정당 4개 추가 과제의 소규모 실험이며')
    if any(r.get('experiment')=='structured_wire_format' for r in rows):
        doc=doc.replace('모델별 동일 프롬프트로 상자·꽃 조명·시계를 생성했습니다.', '이 코호트는 JSON Schema로 응답 형식을 지정한 별도 실험입니다. 함수·상태·이벤트 이름을 배열로 받아 기존 엔진 형식으로 정규화한 뒤 동일한 동작 검사를 합니다. 원본은 각 실행의 wire-output.json, 정규화된 결과는 output.json입니다. 일반 프롬프트 실험과 조건이 달라 합산하지 않습니다.')
        links=''.join('<li><a href="'+html.escape(r['model']+'_'+r['effort']+'_'+r['case']+'/wire-output.json')+'">'+html.escape(r['model']+' / '+r['effort']+' / '+r['case'])+'</a></li>' for r in rows if (OUT/(r['model']+'_'+r['effort']+'_'+r['case'])/'wire-output.json').exists())
        doc=doc.replace('</html>','<h2>변환 전 응답 원본</h2><ul>'+links+'</ul></html>')
    if any(r.get('experiment')=='publication_v2_one_repair' for r in rows):
        doc=doc.replace('모델별 동일 프롬프트로 상자·꽃 조명·시계를 생성했습니다.', '이 실험은 실제 서버의 강화된 공개 검사(60초 누적·반복 클릭·시간 경계)와 최대 1회 수정 정책을 적용합니다. 시간과 사용량은 수정까지 합산한 값입니다. 기존 짧은 검사 실험과 조건이 달라 합산하지 않습니다.')
    if any(r.get('experiment')=='structured_publication_v2' for r in rows):
        doc=doc.replace('모델별 동일 프롬프트로 상자·꽃 조명·시계를 생성했습니다.', '이 실험은 JSON Schema로 출력 형식을 강제하고, 강화 공개 검사(60초 누적·반복 클릭·시간 경계) 및 최대 1회 수정 정책까지 적용합니다. 시간·비용은 수정까지 합산합니다. 저장된 output.json은 엔진용으로 정규화한 결과입니다. 최초 출력만 비교한 structured-v3와 구분합니다.')
    if any(r.get('experiment')=='publication_v3_feedback' for r in rows):
        doc=doc.replace('모델별 동일 프롬프트로 상자·꽃 조명·시계를 생성했습니다.', '회전 범위와 명령 수 오류를 분리하고 수정 요청에 해당 회전축의 허용 범위를 설명한 후속 실험입니다. 강화 공개 검사의 허용 기준은 같지만 수정 프롬프트가 달라 기존 실험과 합산하지 않습니다. 최대 1회 수정의 시간·토큰을 포함합니다.')
    if any(r.get('experiment')=='image_reference_publication_v2' for r in rows):
        doc=doc.replace('모델별 동일 프롬프트로 상자·꽃 조명·시계를 생성했습니다.', '모델별 동일 프롬프트와 참고 이미지로 화병·풍차·상자를 생성했습니다.')
        doc=doc.replace('<h2>설정별 결과</h2>','<p>이 코호트는 기존 Tripo 결과의 게임 렌더 이미지를 함께 입력했습니다. 화병·풍차·상자 3과제이며 강화 공개 검사와 최대 1회 수정 정책을 사용합니다. 점수는 동작 검사이며 이미지 외형 재현 점수가 아닙니다. 추가 Tripo 생성은 수행하지 않았습니다.</p><p><a href="references/static_vase.png">화병 참고</a> · <a href="references/windmill.png">풍차 참고</a> · <a href="references/chest.png">상자 참고</a></p><h2>설정별 결과</h2>')
    (OUT/'index.html').write_text(doc,encoding='utf-8');print(json.dumps(summary,ensure_ascii=True))
if __name__=='__main__':report()
