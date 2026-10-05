# 무료 얼굴 제작 도구 설치·시험 결과

**2026-10-04 · Blender 4.5.3 LTS · MPFB 2.0.17 · Rigify 0.6.10**

MPFB와 Blender에 포함된 Rigify를 별도 제작 프로필에 설치·활성화했습니다. 기본 사람 모델에 공식 눈·눈썹·속눈썹·치아·혀를 붙이고, 얼굴 표정과 Rigify 조작이 작동하는 것을 확인했습니다. **기본 도구 연결 시험은 통과했습니다. 기존 Explorer B 디자인으로의 변형과 Godot 반영은 다음 작업입니다.**

## 바로 열기

- [Face_Tools_Blender.cmd](../Face_Tools_Blender.cmd)를 실행하면 애드온이 활성화된 별도 프로필로 시험 파일이 열립니다.
- 원본: [mpfb_template_face_test.blend](../art/characters/explorer_b_pipeline_v3/01_template_test/mpfb_template_face_test.blend)
- Blender 화면에서 **Space**로 22초 시험 동작을 재생·정지합니다. **1프레임은 기본 표정**입니다.
- 오른쪽 오브젝트 목록의 `Template_Face_Body`를 선택하고 Object Data Properties의 Shape Keys에서 얼굴 변형을 볼 수 있습니다. 수동 슬라이더 검사는 애니메이션 재생을 멈춘 상태에서 합니다. 프레임을 바꾸면 키프레임 값으로 돌아갑니다.
- MPFB 도구는 3D 화면의 **N 패널 → MPFB**에서 사용할 수 있습니다.

애드온은 프로젝트의 별도 프로필에 설치했습니다. 평소 Blender 아이콘이나 `.blend` 더블클릭으로 여는 환경과 다를 수 있으므로 위 실행기를 사용하세요. 다른 캐릭터 원본을 덮어쓰지 않았습니다.

## 설치한 구성

| 구성 | 결과 |
|---|---|
| MPFB 2.0.17 | 공식 Blender Extensions 배포 ZIP 설치. 배포처 SHA-256과 일치 확인 |
| Rigify 0.6.10 | Blender 4.5.3에 포함된 공식 애드온 활성화 |
| MakeHuman system assets | 기본 눈·눈썹·속눈썹·치아·혀 등 설치 |
| Faceunits 01 | 52개 얼굴 표정 단위 설치·불러오기 |
| Visemes 01 / 02 | 발음별 입 모양 자산 설치·불러오기 |

다운로드 주소와 파일 해시는 [downloads.json](../.tools/face-tools/downloads.json)에 기록했습니다. 자산 팩은 공식 HTTPS 배포처에서 받았으며 ZIP 무결성과 로컬 해시를 기록했습니다. 자산 팩의 해시를 별도 공식 해시와 대조했다고 주장하지 않습니다.

설정 위치: `.tools/blender-profiles/face-v3/`. MPFB 사용자 자산은 이 프로필의 `extensions/.user/user_default/mpfb/data/`에 있습니다. MPFB 초기화 과정에서 기본 사용자 경로에 로그 설정 파일이 생성될 수 있으나, 기존 Blender 사용자 설정 파일을 덮어쓰지는 않았습니다.

## 실제 시험 범위

| 검사 | 결과 |
|---|---|
| 새 Blender 프로세스에서 애드온 활성화 유지 | 통과 |
| 저장한 `.blend` 다시 열기 | 통과 |
| 기본 사람 메시와 5종 얼굴 부품 불러오기 | 통과 |
| 52개 Faceunits와 입 모양 팩 불러오기 | 통과 |
| Rigify 실제 뼈대 생성 | 통과. 조작·보조·변형 뼈를 합쳐 930개. 게임용 최종 뼈 수가 아님 |
| 머리 조작기의 메시 변형 | 통과. 8도 시험 회전에서 메시 변화 확인 후 원위치 복원 |
| 눈 감기 0 / 25 / 50 / 75 / 100% | 렌더 확인 |
| 좌우 시선, 시선+깜빡임 | 렌더 확인 |
| 턱 열기·미소·입술 오므리기·AA 입 모양 | 렌더 확인 |
| 속눈썹 등 부품의 표정 추종 | 드라이버 연결 및 15개 프레임에서 본체 값과 일치 확인 |
| 중간 프레임의 연속적인 변화 | 0과 끝값 사이의 보간값 확인. Bézier / Auto Clamped 적용 |
| 평가된 메시의 비정상 수치 | 표본 프레임에서 NaN·무한대 없음 |
| 정면·사선·측면 | 총 16개 렌더 저장 |

기본 얼굴 형상은 직접 스컬프팅하거나 Explorer B 스타일로 바꾸지 않았습니다. 검토용 재질·조명·카메라만 설정했습니다. 얼굴은 셰이프 키가 표정을 담당하고, 얼굴 뼈는 기본 자세로 유지해 이중 변형을 피했습니다. 머리 조작은 별도로 확인했습니다.

![기본 얼굴의 표정 시험](../artifacts/face-stack-test-20261004/contact-sheet.jpg)

## 이번 결과가 뜻하는 것

**설치뿐 아니라 실제 메시 생성·부품 연결·표정 재생·저장 후 재열기까지 확인했습니다.** 다만 자연스러운 최종 캐릭터, 모든 표정 조합의 무충돌, 실시간 성능, 게임 내보내기까지 보장하는 결과는 아닙니다. 특히 기존 캐릭터의 큰 눈과 스타일로 비율을 바꾼 후 같은 검사를 다시 해야 합니다.

Blender 시험 파일을 GUI 프로세스로 열고 해당 파일명의 창을 확인했습니다. Windows 화면 캡처는 재시도 후에도 시간 초과되어 GUI 화면에서 직접 재생 버튼을 누르는 검증은 완료하지 못했습니다. 위의 동작 검증과 이미지는 실제 Blender 파일을 다시 연 별도 프로세스에서 평가·렌더한 결과입니다.

이번에는 Rhubarb, Audio2Face, AccuRIG 등 외부 프로그램은 설치하지 않았습니다. 음성 인식·한국어 립싱크 정확도 시험도 아직 하지 않았습니다. Faceit 구매 및 Tripo 유료 호출은 없으며 **추가 API 비용은 0**입니다.

다음 작업은 이 표준 얼굴을 기존 캐릭터 디자인에 맞춘 작은 시제품으로 만드는 것입니다. 새 참조 이미지가 필요하면 기존 결정대로 먼저 사용자 검토를 받습니다.

## 기록과 공식 출처

- [최신 캐릭터 파이프라인 상태](../art/characters/explorer_b_pipeline_v3/pipeline.json)
- [생성·표정 검사 결과](../artifacts/face-stack-test-20261004/test-results.json)
- [재열기·연속 동작 검사 결과](../artifacts/face-stack-test-20261004/reopen-verification.json)
- [MPFB 공식 배포](https://extensions.blender.org/add-ons/mpfb/) · [2.0.17 릴리스 기록](https://static.makehumancommunity.org/mpfb/releases/release_2017.html)
- [공식 자산 팩과 라이선스](https://static.makehumancommunity.org/assets/assetpacks.html)

MPFB 코드는 GPL-3.0-or-later, Rigify 코드는 GPL-2.0-or-later입니다. 이번에 선택한 공식 시스템·Faceunits·Visemes 팩은 CC0 자산으로 제공됩니다. 다른 외부 자산 팩까지 모두 같은 라이선스인 것은 아닙니다.
