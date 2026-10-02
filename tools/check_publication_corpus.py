"""Recheck saved designs against the newer gate without rewriting historical scores."""
import collections,html,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.asset_contract import parse_design
from server.asset_vm import exercise_extended

def main():
    rows=[]
    for path in sorted((ROOT/'artifacts').glob('model-benchmark*/*/output.json')):
        try:plan,program,_=parse_design(path.read_text(encoding='utf-8'))
        except Exception:continue
        row={'cohort':path.parent.parent.name,'trial':path.parent.name}
        start=time.monotonic()
        try:
            row['validation']=exercise_extended(program,{part['id'] for part in plan['parts']})
            row['passed']=True
        except Exception as error:row.update(passed=False,error=str(error)[:250])
        row['seconds']=round(time.monotonic()-start,4);rows.append(row)
    dest=ROOT/'artifacts/publication-gate';dest.mkdir(exist_ok=True)
    (dest/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    failures=[r for r in rows if not r['passed']]
    body=''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(k,'')))+'</td>' for k in ('cohort','trial','error'))+'</tr>' for r in failures)
    (dest/'index.html').write_text(f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>장시간 동작 검사</title><style>body{{font:16px system-ui;background:#f5f1e7;color:#223c37;margin:40px;line-height:1.7}}table{{border-collapse:collapse}}td,th{{border:1px solid #aaa;padding:8px}}</style><h1>생성 가구의 추가 공개 검사</h1><p>기존 문법·2초 검사를 통과한 {len(rows)}개 저장 결과 중 추가 검사 {len(rows)-len(failures)}개 통과, {len(failures)}개 거부.</p><p>60초의 누적 상태, 124회 클릭, 접근·이탈, 1시간/24시간/100000초 시계 경계를 검사했습니다. 시간 입력을 건너뛰는 검사는 실제 하루 분량 상태 누적을 시뮬레이션하지 않습니다. 이 검사는 모든 입력의 안전성이나 요청 동작·외형의 정확성을 증명하지 않습니다.</p><p>기존 모델 비교의 점수·응답·비용은 수정하지 않았습니다. 아래는 동일한 저장 결과에 새 공개 기준을 적용한 별도 결과입니다.</p><table><tr><th>실험</th><th>설정</th><th>거부 원인</th></tr>{body}</table></html>''',encoding='utf-8')
    print(json.dumps({'checked':len(rows),'passed':len(rows)-len(failures),'failed':len(failures)}))
if __name__=='__main__':main()
