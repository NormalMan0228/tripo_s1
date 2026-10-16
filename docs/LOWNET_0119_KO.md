# 0.11.9 약한 인터넷 대응

이 작업은 네트워크 전송량과 재시도 동작을 개선한다. 그래픽 품질·렌더링 설정과 `project.godot`은 변경하지 않았다. 서버의 기존 JSON 구조, 인증, 소유권 및 방문 권한 계약은 유지한다. 기존 클라이언트는 계속 동작하며 조건부 조회와 저용량 모델은 헤더·쿼리로 선택한다.

## 측정 방법과 결과

`tools/loadtest`는 요청한 `codex14` 작업 트리의 부하 도구 소스를 복사한 것이다. 여기에 `slow_proxy.py`와 `run_lownet.py`를 추가했다. 변경 전에 서버 소스를 별도로 보존하여 기준 서버와 수정 서버를 각각 실행한다. 실제 소켓 연결은 모두 `127.0.0.1`로 제한하고 외부 서비스 키를 상속하지 않는다.

- 양방향 각각 1.5 Mbit/s, 왕복 지연 300 ms, 1% 손실에 대한 재전송 비용을 모사한다. 실제 커널 패킷 손실이 아니라 1,460바이트 구간 단위의 재전송 바이트·지연 모델이다.
- HTTP 헤더와 전송 본문을 프록시에서 집계한다. 압축 해제된 JSON 크기와 실제 전송량을 혼동하지 않는다. TCP/IP·TLS 헤더는 포함하지 않는다.
- 한 방문자의 presence·채팅 수신/귓속말 요청·소셜 목록·제작 상태 조회를 측정한다. 호스트의 연결 유지는 별도 로컬 연결로 수행한다.
- 정상 서버 계약은 **GLB 한 파일 최대 20 MiB, 조립품 전체 최대 48 MiB**다. 큰 객체는 한 파일에 48 MiB를 넣지 않고 여러 부품을 가진 유효한 조립품으로 측정한다.
- “나타나기까지”는 배치 요청부터 방문자가 객체를 발견하고 필요한 GLB를 모두 받은 시점까지다. Godot의 GLB import·노드 생성·GPU 업로드 및 실제 첫 화면 렌더 시간은 제외한다.

실측 원자료와 재실행 명령은 [측정 보고서](LOWNET_MEASUREMENTS_KO.md)에 기록한다.

| 폴링 구분 | 변경 전 B/분 | 동일 호출 주기 + 압축·ETag B/분 | 유휴 정책 포함 B/분 | 변경 전 → 개선 요청/분 |
| --- | ---: | ---: | ---: | ---: |
| presence | 2,169,916 | 405,850 | 137,814 | 134.91 → 175.80 |
| chat: 귓속말 요청 | 7,525 | 11,013 | 11,025 | 14.99 → 14.98 |
| social: 사람 목록 | 38,566 | 9,384 | 9,396 | 11.99 → 11.99 |
| studio: 목록·제작 작업 | 89,375 | 21,861 | 21,885 | 28.98 → 28.97 |
| **합계** | **2,305,382** | **448,107** | **180,120** | **190.87 → 231.74** |

같은 호출 주기에서 전송량이 **80.6% 감소**했고, 15초 이상 입력이 없는 안정된 유휴 상태(이후 presence 최소 1초)를 포함하면 **92.2% 감소**했다. 압축으로 응답이 빨라져 대기 중 중복 호출을 막는 클라이언트에서도 실제 presence 완료 횟수가 늘었다. 유휴 조건의 요청 수는 presence 60회/분, 나머지 세 항목은 각각 15·12·29회/분이다.

| 새 조립품: 고유 GLB 3부품 | 원본 | `?lod=low` | 변화 |
| --- | ---: | ---: | ---: |
| 다운로드 본문 합계 | 49,971,684 B | 6,126,960 B | −87.7% |
| 배치 → 다운로드 완료 | 312.202초 | 36.630초 | −88.3% |
| 에셋 HTTP 전송량 합계 | 49,975,468 B | 6,130,278 B | −87.7% |
| 다운로드 구간의 에셋 B/분 | 9,604,463 | 10,041,326 | 포화 링크 전송률 |
| 에셋 GET 수 / 구간 정규화 요청·분 | 4 / 0.77 | 4 / 6.55 | assembly 1회 + part 3회 |

세 부품은 서로 다른 원본·low 해시를 사용하여 동일 콘텐츠 캐시의 중복 제거 효과를 배제했다. 다운로드 중에도 같은 약한 회선에서 폴링을 유지했다. 이 저용량 수치는 **선택형 서버 계약을 사용한 전체 파일 GET 측정**이며, 아래 문서의 게임 로더 연결이나 512 KiB Range 호출을 이미 실행한 수치가 아니다.

원본의 개별 부품은 각각 103.893·103.618·103.571초가 걸렸다. 기존 게임의 part별 90초 제한을 모두 초과하므로 실제 구버전 게임에서는 재시도 후 실패할 수 있다. 기준 측정은 전송 완료 시점을 관측하려고 HTTPX에 600초 제한을 사용했다.

## 서버 변경

### JSON 압축

`server/low_network.py`의 ASGI 미들웨어는 HTTP 200 JSON 응답 중 1,024바이트 이상을 gzip 또는 deflate로 전송한다. 클라이언트의 `Accept-Encoding`과 품질값(`q=0` 포함)을 확인하며 압축 후 더 작아질 때만 사용한다. 압축 수준은 5다. 파일 응답은 압축하지 않으며 JSON 버퍼는 최대 4 MiB다. 이보다 큰 응답은 기존 방식으로 흘려보낸다.

`Vary: Accept-Encoding`과 정확한 `Content-Length`를 제공한다. presence 본문의 중복된 `village`/`space` 구조도 그대로 유지한다. 기존 HTTPRequest는 압축을 자동 해제하며, kept HTTPClient는 새 클라이언트 훅으로 명시적으로 해제한다.

### 폴링 ETag

다음 GET 경로에서 실제 JSON 바이트의 SHA-256에 기반한 약한 ETag를 제공한다.

- `/v1/social`, `/v1/social/people`, `/v1/social/whispers/requests`
- `/v1/studio`, `/v1/studio/library`, `/v1/studio/jobs/{id}`
- `/v1/generations/{id}`

`If-None-Match`가 일치하면 본문 없는 304를 반환한다. 기존 헤더 없는 요청은 계속 200이고 기본 `Cache-Control: no-store`도 유지된다. `X-Villagen-Cache: 1` 또는 `If-None-Match`를 보낸 클라이언트만 `private, no-cache`로 조건부 재검증을 사용한다. 압축 방식이 달라도 같은 JSON은 같은 약한 ETag를 가진다.

서버 응답 캐시를 만들거나 DB 조회를 건너뛰지 않는다. **인증·권한·요청 제한과 현재 상태 계산을 수행한 뒤** 비교하므로 로그아웃, 작업 상태 변경, 초대 변경이 즉시 반영된다. 시각 필드를 제거하거나 TTL로 오래된 본문을 반환하지 않는다. 시간에 따라 본문이 달라지면 정상적으로 200을 반환한다.

presence는 위치·방문·채팅 상태를 갱신하는 **POST**이므로 304를 반환하지 않는다. 압축으로 전송량을 줄이고 클라이언트의 폴링 간격으로 호출 수를 줄인다.

### 모델 다운로드·이어받기

`server/asset_delivery.py`를 소유자·방문자의 `/model`, `/parts/{part_id}` 네 경로에 적용했다.

```http
GET /v1/social/village/objects/{object_id}/parts/{part_id}?lod=low&cache=1
Authorization: Bearer …
Range: bytes=524288-1048575
If-Range: "이전에 받은 강한 SHA-256 ETag"
Accept-Encoding: identity
```

- 단일 범위의 206, `Content-Range`, `Accept-Ranges: bytes`를 지원한다. 열린 범위와 접미 범위도 가능하다.
- 만족할 수 없는 단일 범위는 416과 `Content-Range: bytes */전체크기`를 반환한다. 다중 범위와 알 수 없는 단위는 무시하고 선택된 표현의 전체 본문을 200으로 반환한다(low를 선택했다면 low 전체).
- `If-Range`는 정확한 강한 ETag가 같을 때만 이어받는다. 변경된 ETag, 약한 ETag 또는 날짜는 전체 200을 반환한다. 클라이언트는 이때 기존 조각에 덧붙이지 않고 교체해야 한다.
- `If-None-Match` 일치 시 304이며 Range보다 먼저 처리한다.
- 기본 캐시 정책은 기존 `no-store`다. `cache=1`, `lod=low`, Range 또는 조건부 요청이면 `private, max-age=0, must-revalidate`와 강한 SHA-256 ETag를 사용한다. 공개 CDN 캐싱이나 권한 확인 없는 장기 캐싱은 하지 않는다.
- 모든 요청에서 기존 소유권·방문 권한과 원본 파일 해시 검사를 거친다. 방문 종료 후 캐시 검증을 시도해도 접근할 수 없다.

### 저용량 GLB

제작 작업/부품을 ready로 공개하기 전에 `prepare_low_variant()`를 워커 스레드에서 한 번 실행한다. 임베디드 PNG/JPEG 텍스처를 최대 512×512 안으로 축소하고 메시·스킨·애니메이션 데이터는 보존한다. 알파도 보존한다. 원본보다 작고 **파일당 최대 4 MiB**인 변형만 저장한다.

`원본이름.low.{원본 SHA-256}.glb`와 해시·크기 메타데이터를 원본 옆에 원자적으로 기록한다. 원본을 교체하면 다른 해시의 변형이 선택되어 오래된 파일이 섞이지 않는다. `?lod=low`를 요청하면 저장된 변형을 반환하고, 실제 선택은 `X-Asset-Lod: low|original`로 알린다. 미지원 이미지·너무 큰 메시·생성 실패·손상·변형 누락이면 검증된 원본으로 돌아간다. 요청 처리 중 즉석으로 변형을 생성하지 않는다.

## 클라이언트 적용

새 파일 `game/scripts/net/net_policy.gd`에 정책을 모았고 기존 파일은 `api.gd`의 `LOWNET hook` 표시 줄만 수정했다. `main.gd`, `studio.gd`, `project.godot`은 수정하지 않았다.

적용된 경로는 GET 폴링의 ETag/304 본문 복원, 세션별 캐시 격리, presence 유휴·최소화·오류 간격 조절, jitter, kept HTTPClient 압축 해제, 약한 연결 표시다. 실패한 제작·구매 등 변경 POST를 자동 재전송하지 않는다.

```gdscript
# api.gd: Node 초기화와 기존 네트워크 함수의 LOWNET hook 위치
@onready var net_policy = preload("res://scripts/net/net_policy.gd").install(self)
# request()의 HTTPRequest 생성 전
if net_policy.handles_poll(path, method, binary):
    return await net_policy.poll_json(self, path, timeout)
# post_kept()의 전송 전
if not await net_policy.before_presence(self, path, payload):
    return {"ok": false, "error": "session_changed"}
# _headers(): HTTPClient가 지원 여부를 알림
headers.append("Accept-Encoding: gzip")
# _kept_request(): 응답 코드 확인 직후 헤더는 한 번만 읽어 저장
var response_headers := kept.get_response_headers()
_seen(response_headers)
# _kept_request(): 수신 완료 후 parse_body() 직전
bytes = net_policy.decode_json(bytes, response_headers)
```

타인 모델의 low 우선 다운로드와 중단 후 이어받기는 새 헬퍼의 `download_model()`에 구현했다. 기존 모델 로더의 캐시 키와 본인/방문자 경로까지 변경하는 연결 작업은 제한된 기존 파일 수정 범위 때문에 **정확한 호출부 변경안을 문서로 제공**한다. 따라서 아래 저용량 모델 측정 결과는 서버의 선택형 기능과 해당 클라이언트 호출안을 사용한 결과이며, 기존 게임 로더에 자동으로 적용됐다는 의미가 아니다.

실제 훅 전체, 안전한 재시도 규칙, 다운로드 호출부와 검증 방법은 [클라이언트 계약 및 코드](LOWNET_CLIENT_KO.md)를 따른다.

## 남은 위험과 범위

- 압축·304는 전송량 최적화다. 인증·DB·JSON 생성 비용은 남는다. 응답마다 달라지는 필드가 있으면 ETag는 304를 만들 수 없다.
- 본문이 아주 작은 응답에서는 ETag와 조건부 요청 헤더가 절약되는 본문보다 크다. 이번 빈 귓속말 요청 목록 측정에서도 그 결과로 바이트 수가 늘었다.
- 저용량 변형은 텍스처 중심 최적화다. 메시가 큰 모델은 줄어들지 않으며, 작은 텍스처나 미지원 파일도 원본으로 반환될 수 있다. 4 MiB는 변형 파일당 한도이지 원본 fallback의 한도가 아니다.
- 기존 ready 자산과 기존 백업 복원본에는 변형이 없을 수 있다. 현재 백업은 DB가 참조하는 원본만 포함한다. 이 경우 원본을 제공하며 기존 데이터의 일괄 변형 생성 작업은 추가로 필요하다.
- Range/304에서도 원본 무결성 검사를 위해 최대 20 MiB 파일 전체를 읽는다. 네트워크 절약과 별개로 디스크·해시 계산 비용이 남는다.
- 큰 다운로드와 presence는 하나의 회선을 공유한다. 실제 Wi-Fi 손실, TCP 혼잡제어, TLS, 운영 서버 지연 및 기기 성능에 따라 결과가 달라진다. 이 결과는 한 번의 로컬 재현 측정이며 성능 보장이 아니다.
- 이어받기는 강한 ETag·범위·전체 크기를 확인해야 한다. 재로그인, 서버 변경, 자산 변경 또는 권한 철회 시 다른 세션의 캐시를 재사용해서는 안 된다.
- 배치 후 실제 화면이 완성되기까지의 import/render 지연은 별도의 엔진 측정이 필요하다.

## 검증

요청한 테스트 명령은 다음과 같다. 시스템 임시 폴더나 pytest 캐시를 사용하지 않는다.

```powershell
& 'C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe' -m pytest server/tests -q --basetemp=.codex-tmppytest -p no:cacheprovider
```

개별 검증은 gzip/deflate 협상과 바이트 복원, 304 이전 인증·상태 변경, POST heartbeat 보존, Range/If-Range/416, 방문 종료, 변형 크기·텍스처·알파·메시·애니메이션 보존, 원본 변경·손상 fallback을 포함한다.

전체 검사에서 기준 커밋에도 있던 두 테스트의 오래된 기대값을 확인해 수정했다. 파티 멤버 응답은 이미 `display_name`을 포함하므로 해당 필드와 이름 fallback을 검증한다. 클라이언트 장면에는 `boni`·`sol`이 있지만 고정된 0.11.9 요청·편지팩에는 없으므로 두 목록의 차이를 명시하고 콘텐츠팩의 기존 60개 요청·40개 편지 검증은 유지한다. 서버 응답이나 게임 콘텐츠는 이 테스트 수정을 위해 변경하지 않았다.

- 서버 전체 재검증: **1,718 passed, 5 skipped, 9 xfailed, 실패 0건**, 1,624.52초, 종료 코드 0. 위 명령에 출력용 `--durations=5`를 추가해 실행했다. 기존 Starlette TestClient/httpx 사용 중단 예정 경고 1건이 있다.
- Godot 4.7.2 정책·이어받기 회귀 검사: **33개 통과**. 여러 API의 다운로드 잠금·소멸한 소유자·슬롯 대기 중 세션 변경과 입력 이벤트 없이 계속되는 이동도 검증했다.
- 실제 `127.0.0.1` HTTP 전송 검사: **5개 통과**, presence TCP 연결 재사용 확인. 이 검사에서 HTTPClient가 헤더를 소비하는 문제를 발견해 헤더를 한 번만 읽어 저장하도록 수정했다.
- 부하 측정 도구 검사: **18 passed, 40 subtests passed**.
