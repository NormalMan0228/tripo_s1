# 로컬 부하 도구와 약한 네트워크 측정

`http_client.py`, `metrics.py`, `run_local.py`와 해당 회귀 테스트는
`D:\lsm26\wt\codex14\tools\loadtest`에서 복사한 기존 도구다.
`run_lownet.py`는 기존 도구의 안전한 환경 생성·127.0.0.1 전용 감사 훅·프로세스 정리와
`tools/test_multiplayer_load.py`의 SQLite 시드를 재사용한다.

```powershell
$python = 'C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe'
& $python -B -X utf8 tools/loadtest/run_lownet.py --mode before --seconds 60 --output tools/loadtest/results/lownet-before.json
& $python -B -X utf8 tools/loadtest/run_lownet.py --mode after --seconds 60 --output tools/loadtest/results/lownet-after.json
& $python -B -X utf8 tools/loadtest/run_lownet.py --mode policy --seconds 60 --skip-asset --output tools/loadtest/results/lownet-policy.json
& $python -B -X utf8 -m pytest tools/loadtest -q --basetemp=.codex-tmppytest -p no:cacheprovider
```

`before`는 변경 전 서버를 `tools/loadtest/.baseline/server`에 복사한 스냅샷을 실행한다.
스냅샷에는 같은 릴리스의 `game/assets/sample_stool.glb`, `game/project.godot` 복사본도 필요하다.
복원은 5f7c6c1 커밋의 `server/`, 위 두 파일을 이 디렉터리에 추출하면 된다.
실험 JSON에는 `server/*.py` 이름·파일내용을 정렬하여 계산한 SHA-256을 기록한다.
스냅샷·DB·GLB·로그는 `.baseline/`, `.tmp/` 아래에만 저장하며 Git에서 제외한다.

각 실험은 독립된 임시 DB, 소유한 Uvicorn 1 worker, 독립된 약한 링크를 쓴다.
사용자 계정 6개, 사용자마다 배치 가구 24개, 친구 관계, 과거 채팅 30줄,
3부품으로 된 약 48MiB 조립품, 변하지 않는 생성 진행상태를 시드한다.
실제 생성 중 상태의 폴링은 fixture worker lease로 유지하며 외부 제작 서비스를 호출하지 않는다.

`slow_proxy.py`는 모든 요청이 공유하는 방향별 1.5Mbit/s 큐, 150ms 편도 전파 지연,
1460byte segment의 1% 손실에 대한 재전송 byte와 추가 RTT를 모사한다.
실제 TCP packet을 버리거나 운영체제 혼잡제어를 재현하는 도구는 아니다.
`http_wire_bytes`는 프록시가 실제 전달한 HTTP header+body 바이트이며 gzip 해제 전이다.
모델상 재전송 비용은 별도 필드이고 TLS/TCP/IP header는 포함하지 않는다.

`after`의 JSON gzip/ETag는 신규 클라이언트 계약을 사용한다. 에셋은 `?lod=low`를
명시하여 요청한다. 실제 게임의 방문자 로더에 low 호출이 아직 연결되지 않았으면
이 에셋 결과는 **해당 호출부를 연결했을 때의 계약 실측**이다.
`policy`는 이미 15초 이상 idle인 상태의 presence1초 주기이며 나머지 GET 주기는 유지한다.

기존 다인원 도구는 다음과 같이 별도로 사용할 수 있다.

```powershell
& $python -B tools/loadtest/run_local.py --players 30 --seconds 90 --max-total-seconds 600 --output tools/loadtest/results/multiplayer
```
