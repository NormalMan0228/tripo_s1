# 캐릭터 리깅·애니메이션 제작 API

## 범위와 활성화

서버의 기존 제작 API에 `animate: true`를 추가한다. 기본값은 `false`다.
`TRIPOTHON_RIG_ANIM_ENABLED=true`일 때만 새 요청을 허용하며,
꺼져 있으면 `GET /v1/studio` 응답에서 `rigging` 항목 자체를 생략한다.
실제 유료 API 사용은 별도 사용자 크레딧 승인 뒤에 활성화한다.
이번 구현·시험은 가짜 transport만 사용하며 배포나 실제 API 호출은 하지 않는다.

지원 대상은 글로 요청한 **사람형(biped) 캐릭터**다. 캐릭터·사람·로봇·몬스터·기사·마법사 등의
한국어 명칭 또는 character, humanoid, robot, monster, knight 등의 영어 명칭을 요구한다.
이는 보수적인 키워드 검사이며 자연어 의미를 완전히 판별하는 분류기는 아니다.
사진, 네 발 리그, 사용자 지정 클립, 아바타 제작은 이번 계약에 포함하지 않는다.
`motion`은 서버가 `static`으로 정규화한다. 이는 한 덩어리 메시와 빈 제작 프로그램을
사용한다는 뜻이며, 최종 GLB의 뼈대 애니메이션은 별도로 포함한다.

필요한 기존 설정도 유지된다.

| 환경 변수 | 역할 |
|---|---|
| `TRIPOTHON_RIG_ANIM_ENABLED` | 기본 `false`. 애니 제작 광고·접수·진행 허용 |
| `TRIPOTHON_MAX_CREDITS_PER_CRAFT` | 운영 설정의 1회 크레딧 상한(현재 200). 메시와 리그·클립·그림 합산 |
| `TRIPOTHON_TRIPO_CREDIT_BUDGET` | 서버 누적 사용량과 확정 예약량의 상한 |
| `TRIPOTHON_MAX_STARS_PER_CRAFT` | 게임 별씨의 1회 상한. 기본 200 |
| `TRIPOTHON_TESTER_CREDIT_BUDGET` | 테스터 합계 예산. 기본 10,000 |
| `TRIPOTHON_STARS_PER_CREDIT` | 크레딧 견적을 게임 별씨로 환산하는 기존 비율 |
| `TRIPOTHON_STUDIO_PART_DEADLINE` | 각 작업 단계의 대기 제한. 기본 1,200초 |
| `TRIPOTHON_FAKE_TRIPO` | 개발용 가짜 Tripo. 실제 키 없이 사용하며 실제 크레딧은 0 |

크레딧 상한과 서버 예산의 `0`은 기존 설정처럼 제한 없음이다. 운영에서는 승인된
상한을 반드시 설정한다. 기존 유료 생성 허용 설정과 공급자 키 조건도 계속 적용한다.
기능 플래그를 진행 중 끄면 새 유료 단계를 보내지 않고 작업·예약을 보존한다.
다시 켜면 저장된 단계부터 이어 간다. 이미 접수된 외부 작업을 취소하는 기능은 아니다.

## 요청과 단계

```json
POST /v1/studio/jobs
{
  "request_id": "고유 UUID",
  "prompt": "친근한 사람형 로봇 캐릭터",
  "animate": true,
  "geometry": "tripo",
  "designer": "simple",
  "mesh_model": "v3.1-20260211",
  "material": "mesh",
  "concept": false
}
```

기존 인증·멱등성 규칙을 그대로 사용한다. `designer: llm`도 기존 설정이 허용하면 가능하다.
`concept: true`면 정면 전신 A포즈 그림을 먼저 그린다. 기존
`POST /v1/studio/jobs/{id}/confirm`에서 합산 견적을 확인한 뒤 제작을 시작한다.

1. 설계를 한 부품과 빈 프로그램으로 제한한다. 기존 가구 행동은 붙이지 않는다.
2. 메시 생성 문장 끝에 팔 45도·다리 벌림·손을 편 A포즈와 단독 전신 지시를 강제한다.
   그림을 승인했다면 같은 포즈로 생성한 그림을 image-to-model 입력으로 사용한다.
3. 정적 메시 다운로드와 기존 정적 GLB 검사를 통과한다.
4. `/animations/rig`에 메시 task ID, biped, 모델 `v1.0-20240301`을 제출한다.
5. 같은 rig task ID로 `/animations/retarget`을 두 번 호출한다.
   각각 `preset:biped:idle`, `preset:biped:walk` 하나씩만 제출한다.
   `bake_animation`, `export_with_geometry`, `animate_in_place`는 모두 `true`다.
6. 각 클립 GLB를 검사하고 동일한 이름·휴지 자세·계층·바인드 행렬의 뼈대인지 확인한 뒤 합친다.
   최종 클립 이름을 `idle`, `walk`로 정규화하고 다시 검증한다.
7. 검증된 최종 GLB와 메타데이터를 객체에 저장하고 `ready`로 완료한다.

외부 rig-check 단계와 실패 시 정적 대체 완성은 설계 초안의 후보이며 이번 구현에는 없다.
현재 계약은 리그·클립 중 하나라도 실패하면 기존 제작과 같이 전체 실패·게임 재화 전액 환불이다.

| 위치 | 상태 |
|---|---|
| 작업 `state` | `queued → planning → awaiting_confirmation → building → ready` |
| 유료 제출 경계 | 요청 전 `submitting`을 DB에 기록, task ID 저장 뒤 `building` |
| 부품 상태 | `pending → generating → rig_pending → rigging → animation_pending → animating → animation_pending → animating → animation_merge → ready` |
| 화면 `stage` | `design`, 선택적 `concept`, `confirm`, `mesh`, `rig`, 최종 작업 상태 |
| 화면 `stages` | `["design", ("concept"), "mesh", "rig", "done"]` |
| 실패 | 확정 실패 `failed`, 접수 여부 불명 `unknown` |

한 worker 처리에서 한 제출·조회 단계를 진행한다. task ID, 공급자 키 식별자,
단계 시작 시각, 보고된 크레딧과 클립 파일 해시를 DB에 저장한다.
`parts.{part}.rig` 및 `parts.{part}.anims.{idle|walk}`가 내부 하위 작업 기록이다.
외부 상태 응답의 `parts`에는 기존 방식대로 상태 문자열만 노출한다.

일시적 조회·다운로드 장애는 저장된 task ID로 다시 조회하며 유료 작업을 재제출하지 않는다.
POST 접수 여부가 불명확하거나 `submitting` 중 재시작했다면 `unknown`으로 보류한다.
이 경우 자동 환불·재제출 없이 기존 운영자 확인 절차가 필요하다.
알려진 task ID를 저장한 뒤 재시작하면 조회를 이어 간다.

## 비용과 환불

합산 견적은 **메시 + 리그 25 + idle 10 + walk 10 + 선택적 그림 비용**이다.
예를 들어 v3.1 텍스트 무색 메시 10이면 합계 55, 그림 5와 image-to-model 무색 메시 20이면 70이다.
P2 텍스처 메시 110이면 두 클립을 포함해 155다.

접수 시 합산 최소 견적을 검사하고, 확인 시 최종 합산 견적 전체를 기존 서버 예산과
테스터 예산에 예약한다. 메시 제출 전부터 리그·애니 비용이 포함된다.
확인 단계와 이후 유료 제출 직전에도 상한을 재검사한다. 공급자 키도 처음부터
전체 체인을 감당할 수 있는 잔액을 기준으로 선택하며 같은 키를 계속 사용한다.
테스터 예약은 기존 정책대로 실패 뒤에도 보수적으로 유지한다.

`known_tripo_credits`, `tripo_credits_consumed`, `billing_complete`는 메시·그림에
리그와 두 클립의 실제 보고 크레딧을 더한다. 청구 보고가 누락되거나 접수 여부가
불명확하면 서버 예산에서 적어도 확정 견적을 계속 점유한다.
리그·클립 작업은 계정의 제작 횟수를 추가로 소모하지 않는다.

실패 환불은 **게임 별씨의 미환불 차감액**을 한 번만 반환한다.
이미 공급자가 소비한 실제 크레딧은 환불됐다고 표시하지 않으며 예산에 남긴다.
완료되지 않은 캐릭터는 객체로 공개하지 않는다.

## 객체·클라이언트 계약

`GET /v1/studio/jobs/{id}`와 `GET /v1/objects/{object_id}/assembly`에서
`provenance.rig`를 제공한다. 객체의 영속 매니페스트에 저장되므로 재시작 후에도 유지된다.

```json
{
  "status": "ok",
  "rig_type": "biped",
  "rig_model": "v1.0-20240301",
  "pose": "A",
  "clips": ["idle", "walk"],
  "default_clip": "idle",
  "moves": true,
  "bones": 64,
  "seconds": {"idle": 2.0, "walk": 1.0}
}
```

`GET /v1/studio`의 `objects[]`에도 `moves`, `clips`를 노출한다.
정적 객체는 `moves: false`, `clips: []`다. 부품의 `file`, `sha256` 계약은 그대로다.
기존 부품 다운로드 경로에서 두 클립을 포함한 GLB를 가져온다.
방 배치 시에도 서버 매니페스트의 `rig.moves`가 있는 객체에만 리그 검사를 허용한다.
사용자 입력으로 이 마커를 설정하는 API는 없다.

`moves: true`는 **서버가 가중치가 연결된 뼈 또는 그 조상의 유효한 키프레임 변화를
확인했다는 뜻**이다. 클라이언트에서 실제 재생됐다는 뜻은 아니다.
클라이언트는 `AnimationPlayer`·`Skeleton3D`를 찾아 `idle`을 반복 재생하고,
배치 후 약 0.5초 동안 뼈 변환이 바뀌는지 확인해야 한다.
클라이언트 재생·배치 확인 구현은 후속 N1 작업이며 이번 서버 변경에는 포함하지 않는다.

## GLB 검사 한도

기존 20 MiB·노드 256·접근자 2,048·전체 접근자 원소 600,000 및
정점·드로콜·텍스처 제한을 그대로 적용한다.
추가로 skin 1개, 뼈 1~128개, 클립 1~8개, 전체 채널 512개 이하,
클립 시간 0~60초를 허용한다. 제작 결과의 클립은 항상 idle·walk 두 개다.

- JOINTS_0 번호가 실제 관절 범위 안이고 WEIGHTS_0 합이 1±0.02인지 검사한다.
- inverseBindMatrices는 관절 수와 같은 개수의 float MAT4여야 한다.
- 키 시간은 유한한 float SCALAR, 엄격한 증가 순서, 2~18,000개여야 한다.
- 채널은 translation·rotation·scale만, 보간은 LINEAR·STEP만 허용한다.
- 회전 길이 0.5~1.5, 스케일 각 성분 0.01~100을 요구한다.
- 가중치가 연결된 뼈 또는 그 조상에서 회전 0.02 rad 초과,
  이동·스케일 성분 0.001 초과의 변화가 각 클립에 있어야 한다.
- URI, 확장, sparse accessor, 모프 targets와 weights 애니메이션은 계속 거부한다.
- 정적 제작과 일반 다운로드는 skins·animations를 계속 거부한다.

서로 다른 휴지 뼈대를 자동 변환하지 않는다. 서로 다른 뼈대, 이름 없는 노드,
중복 노드 이름, 복수 클립이 들어온 단일 retarget 결과는 안전하게 거부한다.
실제 Tripo 출력의 호환성·최종 크기·게임 재생은 승인 후 별도 검증 대상이다.

## 오류 코드

| 코드 | 의미 |
|---|---|
| `rigging_disabled` | 기능 꺼짐. 새 요청·확인은 503, 진행 중 작업은 보존 |
| `animate_requires_character` | 허용된 캐릭터 명칭이 없는 요청(422) |
| `animate_requires_text` | 사진 입력은 지원하지 않음(422) |
| `animate_requires_tripo` | 애니 제작은 Tripo geometry만 허용(422) |
| `craft_over_trial_limit` | 메시·리그·애니 합계가 1회 크레딧 상한 초과 |
| `craft_star_limit_exceeded` | 게임 별씨의 1회 한도 초과 |
| `tripo_budget_exhausted` | 서버 누적 크레딧 예산 부족 |
| `tester_credit_budget_exhausted` | 테스터 합계 예산 부족 |
| `insufficient_provider_credit` | 같은 키에서 전체 체인을 시작할 잔액 부족 |
| `rig_failed` / `animation_failed` | 해당 외부 작업의 확정 실패, 게임 별씨 환불 |
| `generation_timeout` | 해당 단계의 대기 제한 초과, 게임 별씨 환불 |
| `invalid_model` / `asset_too_large` | GLB 구조·값·크기 검사 실패 |
| `animation_static` | 실제 가중치에 영향을 주는 변화가 없는 클립 |
| `animation_clip_mismatch` | 단일 retarget 결과의 클립 개수 불일치 |
| `animation_skeleton_mismatch` | 클립 간 뼈대 이름·휴지 자세·계층·바인드 불일치 |
| `submission_interrupted` / `worker_lease_expired` | 유료 제출 도중 중단, unknown 보류 |

기존 공급자 오류·인증·소유권·다운로드 해시 검사도 그대로 적용된다.
개발 검증은 `server/tests/test_rigging.py`와 기존 서버 전체 테스트로 수행한다.
