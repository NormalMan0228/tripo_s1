"""Compare saved like-for-like trials without silently dropping failed attempts."""
import csv,html,json,math,statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts'
OUT=BASE/'model-comparison'
COHORTS=['model-benchmark-v2','model-benchmark-repeat-1','model-benchmark-repeat-2',
         'model-benchmark-v2-extra','model-benchmark-v2-ultra']

def interval(success,total):
    z=1.96;p=success/total;d=1+z*z/total
    mid=(p+z*z/(2*total))/d
    half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [round(100*(mid-half),1),round(100*(mid+half),1)]

def main():
    OUT.mkdir(exist_ok=True)
    repairs={}
    for file in BASE.glob('model-benchmark-repairs*/*/graded.json'):
        row=json.loads(file.read_text(encoding='utf-8'))
        origin=row.get('original_result')
        if origin:repairs[str(Path(origin).resolve())]=row
    rows=[];prompts={}
    for name in COHORTS:
        for file in (BASE/name).glob('*/graded.json'):
            row=json.loads(file.read_text(encoding='utf-8'))
            case=row['case'];checksum=row.get('prompt_sha256')
            if case not in ('chest','flower','clock'):continue
            if checksum:
                if case in prompts and prompts[case]!=checksum:
                    raise RuntimeError('Unlike prompt contracts cannot be pooled: '+name+'/'+case)
                prompts[case]=checksum
            row['cohort']=name
            row['repair']=repairs.get(str((file.parent/'result.json').resolve()))
            rows.append(row)
    summary=[]
    models=['gpt-6-luna','gpt-5.6-luna','gpt-5.6-terra','gpt-5.6-sol','gpt-6-sol','gpt-6-astra']
    for model in models:
        for effort in ('low','medium','high','xhigh','max','ultra'):
            group=[r for r in rows if (r['model'],r['effort'])==(model,effort)]
            if not group:continue
            effective=[r['repair'] or r for r in group]
            eligible=sum(r['status']=='invalid_design' for r in group)
            attempted=sum(bool(r['repair']) for r in group)
            passed=sum(r['semantic_pass'] for r in group)
            recovered=sum(r['semantic_pass'] for r in effective)
            known=[r for r in effective if r.get('api_equivalent_usd') is not None]
            costs=[r['api_equivalent_usd']*1400 for r in known]
            summary.append({'model':model,'effort':effort,'trials':len(group),
                'first_runtime_pass':sum(r['status']=='validated' for r in group),
                'first_semantic_pass':passed,'first_pass_wilson95_percent':interval(passed,len(group)),
                'repair_eligible':eligible,'repair_tested':attempted,'measured_after_repair_pass':recovered,
                'repair_experiment_complete':attempted==eligible,
                'mean_total_seconds':round(statistics.mean(r['seconds'] for r in effective),1),
                'mean_api_equivalent_krw':round(statistics.mean(costs),2) if costs else None,
                'observed_cost_per_pass_krw':round(sum(costs)/recovered,2) if recovered and len(known)==len(group) else None,
                'usage_reported':len(known)})
    value={'cohorts':COHORTS,'trials':len(rows),'prompt_sha256_by_case':prompts,'summary':summary,
           'note':'Same three requests only. v1, extra object types and repair-only subsets are not pooled as new first attempts. Costs include failures and completed repairs, CLI context, assumed 1400 KRW/USD. No actual paid GPT API requests.'}
    (OUT/'summary.json').write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    with (OUT/'summary.csv').open('w',encoding='utf-8-sig',newline='') as target:
        if summary:
            writer=csv.DictWriter(target,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    body=[]
    for row in summary:
        values=[row['model'],row['effort'],row['trials'],row['first_runtime_pass'],row['first_semantic_pass'],
            f"{row['first_pass_wilson95_percent'][0]}–{row['first_pass_wilson95_percent'][1]}%",
            f"{row['measured_after_repair_pass']}/{row['trials']}"+(' · 일부 수정 미측정' if not row['repair_experiment_complete'] else ''),
            f"{row['repair_tested']}/{row['repair_eligible']}",row['mean_total_seconds'],row['mean_api_equivalent_krw'],row['observed_cost_per_pass_krw']]
        body.append('<tr>'+''.join('<td>'+html.escape(str(v) if v is not None else '미확인')+'</td>' for v in values)+'</tr>')
    document='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Tripothon 모델 종합 비교</title><style>body{max-width:1450px;margin:40px auto;padding:20px;background:#18342f;color:#f0ecdd;font:15px/1.65 system-ui}h1,h2,th{color:#e7bd73}table{border-collapse:collapse;width:100%}td,th{padding:12px;border-bottom:1px solid #49695f;text-align:left;white-space:nowrap}.scroll{overflow:auto}.note{padding:20px;background:#28483f;border-radius:12px}a{color:#e7bd73}li{margin:10px 0}</style><h1>실패와 수정 비용을 포함한 모델 비교</h1><p>동일한 상자·꽃 조명·시계 요청. 프롬프트 해시를 확인한 최초 실험만 합쳤습니다.</p><div class="note"><ul><li>문법/실행 통과와 요청 동작 충족은 다릅니다. 부품명 기반 자동 검사이므로 시각 품질이나 사람의 만족도를 뜻하지 않습니다.</li><li>같은 세 과제를 반복한 작은 실험입니다. 95% 구간도 해당 과제의 변동 폭을 보는 참고치이며 모든 가구 프롬프트의 성공 확률이 아닙니다.</li><li>수정 후 점수는 문법/실행 검증 실패에 한 번 수정 요청한 결과를 포함합니다. 아직 수정하지 않은 실패를 제외하거나 성공으로 바꾸지 않습니다.</li><li>환산 비용은 실패 및 실제 수행한 수정까지 합칩니다. 성공 1건당 비용은 관측된 전체 비용÷통과 건수입니다. 사용량이 하나라도 없으면 계산하지 않습니다.</li><li>Codex 구독 실행이며 유료 GPT API 결제액은 0입니다. 약 1만 토큰의 CLI 맥락이 포함된 환산치, 환율 1,400원 가정입니다. 시간은 서버·렌더링 작업이 함께 실행된 개발 PC의 관측값입니다.</li></ul></div><h2>모델·effort별 결과</h2><div class="scroll"><table><tr><th>모델</th><th>effort</th><th>최초 시도</th><th>실행 통과</th><th>동작 충족</th><th>동작 충족 95% 구간</th><th>측정된 수정 후</th><th>수정 측정/대상</th><th>평균 합계 초</th><th>평균 환산 원</th><th>성공당 관측 원</th></tr>'''+''.join(body)+'''</table></div><p>높은 effort 또는 더 비싼 모델이 항상 통과하는 것은 아닙니다. 비용을 줄이려면 저가 모델, 검증, 제한된 재설계, 유료 메시 생성 전 도형 미리보기를 함께 사용해야 합니다.</p><p><a href="summary.csv">CSV</a> · <a href="https://developers.openai.com/api/docs/pricing">공식 단가</a></p></html>'''
    (OUT/'index.html').write_text(document,encoding='utf-8')
    print(json.dumps({'trials':len(rows),'settings':len(summary),'repairs':len(repairs)}))

if __name__=='__main__':main()
