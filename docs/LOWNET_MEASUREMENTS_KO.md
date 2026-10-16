# 0.11.9 약한 네트워크 실측 노트

2026-10-16, Windows 로컬 환경에서 변경 전 `5f7c6c1`과 현재 변경 서버를 비교했다.
실행 도구는 `tools/loadtest/run_lownet.py`, 원시 결과는
`tools/loadtest/results/lownet-before.json`, `lownet-after.json`, `lownet-policy.json`이다.

## 측정 조건과 해석 범위

- 모든 서버·클라이언트·프록시는 `127.0.0.1`만 사용한다. 기존 load tool의 소켓 감사 훅과 환경변수 allowlist를 재사용하여 DNS/외부 주소/실제 제작 제공자 자격증명을 차단했다.
- 각 실험은 독립 Uvicorn 1 worker와 임시 SQLite DB를 쓴다. 시계는 실제 wall clock이며 응답의 `server_time`·온라인 상태 변화를 고정하지 않았다.
- 방향별 1.5 Mbit/s, RTT 300 ms(편도 150 ms), 1460바이트 가상 segment의 손실 확률 1%, 난수 seed119. 모든 폴링과 다운로드가 같은 방향별 링크 큐를 공유한다.
- 손실은 실제 OS packet drop이 아니다. 해당 데이터의 재전송 바이트를 대역폭에서 차감하고 추가 RTT를 부과하는 Python TCP proxy 모델이다. TCP 혼잡제어·ACK·TLS handshake는 재현하지 않는다.
- 표의 **HTTP wire bytes**는 프록시가 실제 전달한 HTTP 요청/응답 헤더와 본문 합계다. gzip 해제 전의 값을 센다. TCP/IP/TLS 헤더 및 모델상 재전송 바이트는 합산하지 않았으며, 재전송 비용은 JSON 별도 필드에 남겼다.
- 예열 뒤 약 60초를 관측하고 실제 관측시간으로 분당값을 정규화했다. 시드: 계정 6개, 계정당 배치 가구 24개, 친구 관계, 과거 채팅 30줄, 초대 방문, 생성중 작업 1개. 직접 DB 시드는 기존 `tools/test_multiplayer_load.py`를 재사용한다. 실제 생성 제공자는 호출하지 않고 `planning` 상태와 worker lease를 시드하여 상태가 변하지 않는 생성 대기 구간을 재현했다.
- host는 별도 정상 링크에서 3초마다 heartbeat를 보낸다. visitor는 자산 다운로드 중에도 같은 약한 링크로 presence/chat/social/studio 폴링을 계속하여 60초 방문자 실종 판정에 걸리지 않게 했다.
- presence0.25초는 기존 pending guard처럼 이전 응답이 완료된 뒤 다음 요청을 허용한다. chat은 `/v1/social/whispers/requests` 4초, social은 `/v1/social/people` 5초, studio는 `/v1/studio` 20초와 `/v1/studio/jobs/{id}` 응답 후 2초를 합산했다. 일반 채팅 수신은 presence의 chat cursor에 포함된다. 채팅 송신은 이 정적 폴링 구간에 없다.
- 서버 개선 열은 같은 정상 cadence에서 gzip과 GET ETag를 요청한 신규 HTTP 계약 측정이다. idle 열은 입력이 15초 이상 없는 안정된 상태에서 presence만 1초로 낮춘 실제 신규 helper 정책이다. 나머지 GET cadence는 바꾸지 않았다. 최소화 3초/오류 backoff는 이 성공 응답 실험에 포함하지 않았다.
- `after` 자산 결과는 방문자 URL에 `?lod=low`를 직접 붙인 **서버 opt-in 계약 실측**이다. 현재 게임의 모든 방문자 로더 호출부에 low/resume 경로가 연결된 것으로 해석하면 안 된다.

## 폴링: 요청 수와 HTTP 전송량

| 구분 | 변경 전 요청/분 | 서버 개선 요청/분 | 변경 전 B/분 | 서버 개선 B/분 | idle 정책 B/분 |
|---|---:|---:|---:|---:|---:|
| presence | 134.91 | 175.80 | 2,169,916 | 405,850 | 137,814 |
| chat (귓속말 요청) | 14.99 | 14.98 | 7,525 | 11,013 | 11,025 |
| social (사람 목록) | 11.99 | 11.99 | 38,566 | 9,384 | 9,396 |
| studio (목록+작업) | 28.98 | 28.97 | 89,375 | 21,861 | 21,885 |
| **합계** | **190.87** | **231.74** | **2,305,382** | **448,107** | **180,120** |

동일 cadence에서 총 HTTP 전송량은 **80.6% 감소**, 안정된 idle 정책을 함께 적용하면 **92.2% 감소**했다.
서버 응답이 작아지며 presence 대기시간이 줄어 실제 완료 요청수는 늘었다. 따라서 고정 요청수당 압축률과 이 표의 분당 감소율은 다르다.
chat의 빈 목록은 본문 15바이트라서 ETag 요청/응답 헤더 비용이 본문 절약보다 크다. 모든 endpoint의 304가 항상 대역폭을 절약하는 것은 아니다.

서버 개선 후 상태코드는 presence176회 모두 200, chat15회 모두 304, social12회 중 11회 304·1회 200, studio29회 모두 304였다.
idle 실험의 요청수는 presence60, chat15, social12, studio29회였다. 실패 응답이나 transport retry를 성공 요청수에 포함하지 않았다.

| 60초 관측 구간의 디코딩된 응답 본문 | 변경 전 B | 서버 개선 B | idle 정책 B |
|---|---:|---:|---:|
| presence | 2,084,041 | 2,716,972 | 926,216 |
| chat | 225 | 0 | 0 |
| social | 32,856 | 2,734 | 2,738 |
| studio | 74,707 | 0 | 0 |

디코딩 본문은 wire와 다르다. after presence의 값이 큰 것은 실제 응답 횟수가 늘었기 때문이고,304 응답 본문 0은 정상적으로 기존 JSON 캐시를 재사용했음을 뜻한다.

## 약 48MiB 제작물: 방문자에게 표시할 데이터가 준비되는 시간

원본은 **49,971,684바이트(47.66MiB)**이며 **16,657,228바이트인 GLB 3부품**으로 이루어졌다.
3부품의 UV 좌표와 SHA-256은 서로 달라 실제 게임의 hash 캐시가 다운로드를 1개로 합치지 않는다.
각 부품은 1360×1360 RGB PNG 텍스처 3장과 작은 메시를 갖는다. PNG는 고정 seed 고엔트로피 데이터이므로 텍스처 축소의 영향을 측정한다.
기존 검증의 개별 이미지 8MiB, GLB20MiB, 조립품 48MiB 및 픽셀 제한을 통과한 fixture다.
단일 48MiB GLB는 기존 서버에서도 허용되지 않으므로 시험에 쓰지 않았다.

소유자의 실제 배치 API 호출 직전부터 측정하여, 방문자의 presence에서 객체 발견 → assembly 조회 → 모든 part 다운로드 완료까지 센다.
엔진의 GLB 파싱·텍스처 업로드·GPU 렌더 시간은 제외한다. 새 객체의 실제 화면 표시를 보장하는 end-to-end 게임 측정이 아닌 **network-ready 지연**이다.

| 측정 | 변경 전 원본 | 서버 low opt-in |
|---|---:|---:|
| GLB 3부품 본문 합계 | 49,971,684 B | 6,126,960 B |
| assembly+GLB HTTP wire 합계 | 49,975,468 B | 6,130,278 B |
| 자산 구간 HTTP wire B/분 | 9,604,463 | 10,041,326 |
| 자산 GET 수 (assembly1+part3) | 4 | 4 |
| 자산 구간 요청/분 | 0.77 | 6.55 |
| 배치 시작→presence 발견 | 0.768초 | 0.725초 |
| 배치 시작→모든 GLB 다운로드 완료 | **312.202초** | **36.630초** |
| part별 전체 GET 소요시간 | 103.893 / 103.618 / 103.571초 | 11.778 / 11.914 / 11.888초 |

GLB 본문은 **87.7% 감소**, network-ready 지연은 **88.3% 감소**했다.
원본은 각 부품의 SHA-256이 manifest와 일치했고, low는 3부품 모두 `X-Asset-Lod: low`와 서로 다른 SHA-256을 확인했다.
원본의 **세 부품 모두 실제 GET 시간이 90초를 넘었다**. 기존 게임 timeout 정책이면 이 링크에서 원본 전송이 완료되기 전에 중단될 수 있다.


다운로드 중의 바이트/분은 사용자별 평상시 월간 트래픽이 아니라 해당 포화 링크 구간의 전송률이다.
새 객체를 다시 읽지 않는 캐시 hit, 중단 후 Range 재개, 새 세션 cold start는 별도 회귀 테스트 대상이며 이 표에 섞지 않았다.

기존 Godot `asset_assembly.gd`는 part별 timeout90초를 사용한다. 이 harness는 원본의 전송완료시간을 얻으려고 HTTPX timeout600초를 사용했다.
따라서 원본 결과를 기존 게임이 90초 제한 안에서 성공한다고 해석하면 안 된다. 원본 part당 16.657MB는 이상적인 1.5Mbit/s에서도 약 88.84초이고 재전송·다른 폴링이 시간을 더한다.
신규 helper의 512KiB Range 조각/20초 제한과도 다른, 전체 part GET의 서버 계약 측정이다. 실제 helper 조각 요청은 추가 RTT/헤더 비용이 발생한다.

## 재현·검증·남은 한계

실행 명령은 `tools/loadtest/README.md`에 있다. 변경 전 서버 snapshot은 변경 시작 전에 복사했고 72개 Python 파일 모두 `5f7c6c1`과 개행 정규화 후 동일함을 확인했다.
파일별 SHA-256은 `tools/loadtest/results/baseline-sources.json`, 각 실험의 서버 소스 묶음 SHA-256은 결과 JSON에 남겼다.
`.baseline/`에는 원본 서버, server/data, sample_stool.glb, project.godot 복사본만 있으며 원래 project.godot은 수정하지 않았다.

도구 검증: `python -m pytest tools/loadtest -q --basetemp=.codex-tmppytest -p no:cacheprovider` → **18 passed, 40 subtests passed**.
새 테스트는 공유 큐의 속도 제한, 재전송의 대역폭/RTT 비용, 실제 전달 바이트 합계 및 데이터 무손상을 확인한다.

초기 진단에서 5초 keep-alive 경합, 기존 다인원 시드 40개의 배치 cap30 초과, 동일 SHA 부품을 게임 캐시가 합치는 문제가 발견되었다.
최종 실험은 클라이언트 keep-alive expiry3초, 배치 24개, 부품별 고유 UV/SHA로 수정한 뒤 전부 재실행했으며 초기 실패/짧은 smoke 결과는 표에서 제외했다.

단일 PC의 합성 시드 및 각 조건 1회 관측이다. 실험 중 별도 독립 링크 실험과 테스트가 같은 PC의 CPU를 공유했다.
링크 pacing이 주 병목이지만 CPU 스케줄링·서버 지연의 영향을 완전히 분리하지 않았다. 모바일망의 버스트 손실·가변 RTT·재연결·실제 TLS 비용과 전체 게임 렌더 지연은 추가 실기기 검증이 필요하다.
메시 위주의 큰 GLB는 텍스처 축소만으로 줄지 않으며 cap을 만족하는 low 파일을 만들지 못하면 원본 fallback이 발생한다.
