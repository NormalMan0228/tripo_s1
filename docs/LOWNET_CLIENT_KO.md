# 0.11.9 저속 연결 클라이언트 계약

## 이번 변경에 실제 연결된 기능

새 파일 `game/scripts/net/net_policy.gd`를 `game/scripts/api.gd`의 `LOWNET hook` 8곳으로 연결했다. `main.gd`, `studio.gd`, `project.godot`은 수정하지 않았다. 기존 화면의 `pending` 플래그와 kept-alive 연결은 그대로 사용한다.

| 항목 | 실제 동작 |
| --- | --- |
| Presence 활성 상태 | 기존 0.25초 간격을 하한으로 사용. 기존 away/heartbeat 호출 자체가 더 느리면 그 간격을 유지 |
| 유휴 상태 | 마지막 키보드·마우스·게임패드 입력과 실제 이동이 모두 15초 이상 없으면 최소 1초. `vx/vz` 속도 또는 같은 scene의 `x/z` 변화를 관찰하므로 게임패드 stick을 계속 유지해 새 입력 이벤트가 없어도 이동 중에는 활성 간격 유지 |
| 창 최소화 | 최소 3초. 호스트 퇴장 판정 20초보다 충분히 짧게 유지 |
| 일시적 실패 | 다음 폴링 전에 `min(cap, 2^(실패횟수-1) × uniform(0.75, 1.25))`초 대기. Presence cap 5초, GET cap 30초 |
| 복구 | 정상 응답 시 해당 채널의 오류 backoff 해제. 입력으로 깨어나면 정상 idle 대기를 즉시 끝내고 다음 폴링에서 새 위치를 계산. 오류 backoff는 입력으로 해제하지 않음 |
| 약한 연결 표시 | 같은 채널에서 일시적 실패 2회 또는 RTT 1.8초 이상 3회면 우측 상단에 `연결이 약해요 · 다시 연결 중`. 해당 채널 정상 응답 3회면 해제 |
| GET 조건부 요청 | ETag 저장 후 `If-None-Match`. 304는 JSON 파싱하지 않고 이전 본문의 깊은 복사본 반환. 304인데 본문 캐시가 없으면 조건 없이 1회 복구 |
| JSON 캐시 격리 | API 인스턴스별·서버 URL별·로그인 토큰별. 최대 16개/원본 JSON 합계 8 MiB. 계정·서버 변경 시 초기화 |
| 압축 | kept `HTTPClient`에 `Accept-Encoding: gzip` 및 최대 20 MiB gzip/deflate 해제. 일반 `HTTPRequest`는 엔진의 자동 해제 사용 |

조건부 GET 대상은 `/v1/social`, `/v1/social/people`, `/v1/social/whispers/requests`, `/v1/studio`, `/v1/studio/library`, `/v1/studio/jobs/{id}`, `/v1/generations/{id}`이다. 조건부 요청에는 `X-Villagen-Cache: 1`도 보낸다. 동일 URL이어도 인증/권한 검증은 매번 서버에서 수행한다. Notice 헤더는 304에서도 처리한다. GET의 숫자형 `Retry-After`는 429/503에서 존중한다.

채팅 수신은 별도 `/chat` GET 폴링이 아니라 presence 응답에 포함된다. 따라서 idle/최소화 상태에서는 메시지 수신과 타인의 물건 발견도 각각 최대 약 1초/3초 간격에 네트워크 지연이 더해진다. 채팅 보내기, 가구 배치·제작 등 변경 POST는 자동 재전송하지 않는다. POST presence 자체에도 304를 사용하지 않는다.

`api.gd`의 실제 연결점은 다음과 같다. 다른 세션에서 병합할 때 이 8곳만 확인하면 된다.

```gdscript
# api.gd, extends Node 바로 다음
@onready var net_policy = preload("res://scripts/net/net_policy.gd").install(self)

# request() 첫 줄
if net_policy.handles_poll(path, method, binary):
    return await net_policy.poll_json(self, path, timeout)

# post_kept() 첫 줄
if not await net_policy.before_presence(self, path, payload):
    return {"ok": false, "error": "session_changed"}

# post_kept()의 기존 kept_busy fallback 한 줄 교체
if kept_busy:
    return await net_policy.kept_fallback(self, path, payload, timeout)

# post_kept(), round_trip_ms[path] 기록 직후
if path == net_policy.PRESENCE:
    net_policy.record(path, result, round_trip_ms[path])

# _headers(), headers 생성 직후
headers.append("Accept-Encoding: gzip")

# _kept_request(), 응답 code를 읽은 다음 기존 _seen(...)을 교체
# get_response_headers()는 읽으면서 소비되므로 반드시 한 번만 호출한다.
var response_headers := kept.get_response_headers()
_seen(response_headers)

# _kept_request(), 최종 parse_body(bytes) 직전
bytes = net_policy.decode_json(bytes, response_headers)
```

## 구현되어 있으나 호출부 연결은 문서로 남긴 GLB 다운로드

`net_policy.download_model(api, path, other_player)`는 동작하는 구현이며 오프라인 응답 fixture로 검증했다. 이번 작업에서는 `main.gd`와 `studio.gd` 수정 제한에 따라 **현재 모델 로딩 경로에 이 함수를 연결하지 않았다**. 서버의 low variant가 준비되어도 이 호출부를 병합하기 전의 실제 게임은 기존 원본 모델 요청을 사용한다. 저속 링크의 low variant 성능 측정값은 이 opt-in 계약을 적용한 클라이언트의 결과로 읽어야 한다.

타인의 crafted GLB는 `?lod=low&cache=1`을 먼저 요청한다. 서버는 최대 512 px 텍스처·4 MiB의 low variant를 준비하며 만들 수 없거나 크기를 초과하면 원본을 반환한다. 실제 선택은 `X-Asset-Lod: low` 또는 `original`이다. 원본 GLB 하나는 기존 한도 20 MiB이고 조립품 전체가 최대 48 MiB일 수 있다. 메시는 low에서도 동일하므로 모델 좌표·충돌 규약은 바뀌지 않는다.

다음 코드는 정확한 교체 위치와 교체 내용이다. **아래 두 교체는 문서 전용이며 아직 적용하지 않았다.**

```gdscript
# game/scripts/main.gd, load_object()에서 기존
# var response: Dictionary = await api.request(prefix+obj.id+"/model",{},HTTPClient.METHOD_GET,true)
# 한 줄을 다음으로 교체. 함수 안의 check(response), Loader.load_bytes 등은 유지한다.
var response: Dictionary = await api.net_policy.download_model(
    api, prefix + str(obj.id) + "/model",
    prefix.begins_with("/v1/social/village/objects/"))

# game/scripts/studio.gd, load_item()에서 기존
# var response: Dictionary=await api.request(prefix+obj.id+"/model",{},HTTPClient.METHOD_GET,true)
# 한 줄을 다음으로 교체. value 캐시 및 Loader.load_bytes는 유지한다.
var response: Dictionary = await api.net_policy.download_model(
    api, prefix + str(obj.id) + "/model",
    prefix.begins_with("/v1/social/village/objects/"))
```

헬퍼의 이어받기 규약은 다음과 같다.

1. `Range: bytes=N-(N+524287)`와 `Accept-Encoding: identity`로 최대 512 KiB씩 받는다. 완전히 도착한 청크만 `.part`에 저장한다. 실패한 청크의 일부만 다시 내려받으므로 끊어질 때 전체 파일을 버리지 않는다.
2. URL·토큰·low/original 구분을 해시한 파일명으로 `user://lownet`에 저장한다. 토큰 원문은 디스크에 기록하지 않는다. 이후 호출이나 프로그램 재시작에서 동일 로그인 세션이면 저장된 크기부터 재개한다.
3. 두 번째 청크부터 `If-Range: "<전체 파일 SHA256>"`를 보낸다. 206의 시작·끝·전체 크기·ETag를 검사한다. 최종 GLB 헤더와 전체 SHA256도 확인한다.
4. 200이 오면 If-Range 불일치 또는 Range 미지원으로 보고 부분 파일에 덧붙이지 않고 전체 응답으로 대체한다. 416이면 부분 파일을 제거하고 `range_changed`를 반환한다. 다음 명시적 로딩 시 처음부터 시작한다.
5. 네트워크 오류와 408/429/500/502/503/504는 최대 3회 시도한다. 인증 실패·권한 실패·일반 4xx는 재시도하지 않는다. 한 청크의 timeout은 20초이다.
6. 동일 Godot 프로세스의 모든 API 인스턴스가 정규화한 캐시 폴더별 잠금 레지스트리를 공유한다. 동일 파일의 동시 요청은 직렬화하고 폴더별 전체 전송은 최대 3개로 제한한다. 네 번째 요청은 실패시키지 않고 슬롯을 기다리며 대기 중 로그인 세션이 바뀌면 취소한다. 잠금은 소유자의 WeakRef와 요청 티켓으로 관리하여 scene/API가 해제되어도 영구적으로 남지 않는다. 완료 부분 파일은 삭제한다. 시작할 때 오래된 부분 파일(하루)과 초과 파일을 정리하며 다른 API 인스턴스의 진행 중 파일도 보호하고, 모든 활성 전송의 최대 크기를 합산해 저장공간 64 MiB 한도에 필요한 여유를 확보한다.
7. 현재 importer의 20 MiB/GLB 상한을 넘는 응답은 거절한다. 대형 조립품은 각 part를 따로 받는 기존 `asset_assembly.gd` 경로이므로 위 두 줄만으로 조립품 part 다운로드까지 Range/low가 적용되지는 않는다. 다음 교체를 함께 병합해야 한다.

48 MiB 조립품 전체를 단일 `PackedByteArray`로 받도록 상한을 늘리지 않는다. 서버와 downloader는 `/model`뿐 아니라 `/parts/{part_id}`에도 동일한 low/Range 계약을 지원한다. **다음은 `game/scripts/asset_assembly.gd`의 `static func part_blob(...)` 전체 교체 코드이며 문서 전용이다.** `fetch()`와 `build()`는 그대로 두고 원본 manifest의 `p.sha256`도 변경하지 않는다. `remember()`의 64 MiB 메모리 한도를 재사용한다.

```gdscript
static func part_blob(api: Node, route: String, digest: String) -> PackedByteArray:
    var prefer_low := route.begins_with("/v1/social/village/objects/")
    # The manifest hashes the original. The low representation has its own ETag hash.
    var scope: String = (str(api.base_url) + "\n" + str(api.token) + "\n"
        + route + "\n" + digest).sha256_text()
    var wanted := scope + (":low" if prefer_low else ":original")
    if part_cache.has(wanted): return part_cache[wanted]
    var fallback := scope + ":low-fallback-original"
    if prefer_low and part_cache.has(fallback): return part_cache[fallback]
    downloads += 1
    # The helper handles bounded retries; do not wrap it in the old retry loop.
    var response: Dictionary = await api.net_policy.download_model(api, route, prefer_low)
    if not response.ok: return PackedByteArray()
    var bytes: PackedByteArray = response.bytes
    var hashing := HashingContext.new()
    hashing.start(HashingContext.HASH_SHA256)
    hashing.update(bytes)
    var actual := hashing.finish().hex_encode()
    var selected_low := str(response.get("lod", "")) == "low"
    if selected_low:
        # A low file cannot match p.sha256; verify the exact selected representation.
        if not prefer_low or str(response.get("etag", "")) != "\"" + actual + "\"":
            return PackedByteArray()
    elif actual != digest:
        # Original fallback and old-server replies still match the manifest hash.
        return PackedByteArray()
    var cache_key := wanted if selected_low or not prefer_low else fallback
    # A concurrent fetch may have populated the cache while awaiting the helper.
    if not part_cache.has(cache_key): remember(cache_key, bytes)
    return bytes
```

위 캐시는 서버·로그인 토큰·part 경로·원본 digest·선택 표현별로 분리한다. low가 준비되지 않아 원본으로 fallback한 부품은 별도 키로 저장하며, 해당 메모리 항목이 유지되는 동안 그 원본을 재사용한다. 다음 로그인/서버 변경 또는 메모리 캐시 퇴출 후 다시 low를 요청한다. 이미 캐시된 원본을 수초마다 다시 내려받지는 않는다. `fetch()`의 합계 48 MiB 제한과 part별 20 MiB 제한은 유지한다.

## 남은 제약과 검증

- 기존 `pending` 처리와 TCP 연결을 유지했지만 GPU import·씬 생성 지연은 이 작업 범위가 아니다. low variant는 텍스처를 줄이며 메시 단순화는 하지 않는다.
- 입력은 대기를 깨우며 마지막 정지 상태 snapshot을 먼저 보낸 뒤 다음 폴링에서 새 위치를 보낸다. 입력 없이 코드로 순간 이동하거나 여러 scene 전환 요청이 겹치는 경우는 화면의 기존 epoch/pending 규약에 의존한다. 실제 두 클라이언트로 전환 중 위치/채팅/호스트 유지 확인을 추가해야 한다.
- GET은 정상 상태에서 기존 호출 주기를 유지한다. 단지 창 최소화를 이유로 수동 studio 새로고침까지 느리게 만들지 않는다.
- Retry-After의 HTTP-date 형식과 presence 응답의 Retry-After는 아직 별도로 해석하지 않는다. GET·모델 다운로드는 숫자형 Retry-After를 존중한다.
- 약한 연결 표시는 새 CanvasLayer로 구현했으며 headless에서는 생성하지 않는다. 기존 폰트 import 캐시가 없는 작업환경이므로 실제 HUD 위치·번역 및 화면 전환 시각 검증은 별도로 필요하다.
- 완료된 GLB는 기존 화면의 메모리 캐시가 맡는다. 디스크는 실패한 다운로드의 이어받기 용도이며 새 로그인 토큰의 이전 파일 재사용은 하지 않는다.

검증 명령:

```powershell
& C:\lsm26\triphthonS1\.tools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path game --check-only --script res://scripts/api.gd --log-file D:/lsm26/wt/codex31/.codex-tmp/lownet-parse.log
& C:\lsm26\triphthonS1\.tools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path game --script res://tests/net_policy_check.gd --log-file D:/lsm26/wt/codex31/.codex-tmp/lownet-check.log
& C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe tools/check_lownet_client.py --godot C:\lsm26\triphthonS1\.tools\godot\Godot_v4.7.2-stable_win64_console.exe
```

Godot 4.7.2 parser 통과, `NET_POLICY_RESULT passed=33 failed=0`. 테스트는 네트워크 호출 없이 조건부 GET·304 복구·세션 캐시 분리·변경 POST 제외·간격/복구 표시·Python gzip/zlib wire fixture를 포함한 gzip/deflate·Range/If-Range·low URL·중단 후 디스크 재개·200 교체·SHA256 오염 검출·416 정리·조립품 부품의 low 메타데이터를 검증한다. 서로 다른 API 인스턴스의 같은 파일 직렬화, 폴더별 3개 한도, 다른 API의 활성 파일 보존 및 용량 예약, 네 번째 요청의 슬롯 대기, 소멸한 잠금 소유자 복구, 대기 중 세션 취소와 새 입력 이벤트 없는 지속 이동도 검증한다.

추가로 임시 HTTP 서버를 **127.0.0.1에만** 열어 실제 Godot API를 실행했다. `NET_POLICY_HTTP_RESULT passed=5 failed=0`, `LOOPBACK_WIRE_RESULT requests=4 presence_reused=True`. custom Accept-Encoding을 가진 HTTPRequest의 gzip 자동 해제, 실제 304 빈 본문 복원 및 Notice 처리, kept HTTPClient의 gzip 수동 해제와 TCP 연결 재사용을 확인했다. 이 검증에서 `get_response_headers()`를 두 번 읽으면 두 번째 결과가 비어 있는 엔진 동작을 발견해 최초 헤더 복사본을 재사용하도록 수정했다.

기존 폰트 import 캐시와 sandbox 루트 인증서 접근 오류가 초기화 로그에 출력되지만 두 테스트의 종료코드는 0이고 오프라인 33개+실제 loopback 5개 검사가 통과했다. loopback 서버는 실행 종료 시 닫히며 외부 주소를 호출하지 않는다.
