"""Package only public game art and a credential-free local demo server."""
from pathlib import Path
import hashlib
import shutil
import importlib.metadata
import sys
import argparse
from zipfile import ZipFile,ZIP_DEFLATED

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--package-dir',type=Path,default=root/'builds'/'Tripothon_Demo_081')
args=parser.parse_args()
package=args.package_dir.resolve()
package.mkdir(exist_ok=True)
for name in ('Villagen.exe','Villagen.pck'):
    shutil.copy2(root/'builds'/'windows'/name,package/name)
shutil.copytree(root/'builds'/'TripothonDemoServer',package/'server',dirs_exist_ok=True)
shutil.copy2(root/'tools'/'portable_start.ps1',package/'Start.ps1')
shutil.copy2(root/'tools'/'portable_stop.ps1',package/'Stop.ps1')
shutil.copytree(root/'docs'/'licenses',package/'licenses',dirs_exist_ok=True)
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.is_file(): shutil.copy2(python_license,package/'licenses'/'Python-LICENSE.txt')
for distribution in importlib.metadata.distributions():
    for entry in distribution.files or []:
        if not any(word in entry.name.upper() for word in ('LICENSE','COPYING','NOTICE')): continue
        source=Path(distribution.locate_file(entry))
        if source.is_file():
            name=distribution.metadata['Name'].replace('/','_').replace('\\','_')
            target=package/'licenses'/name/entry.name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
(package/'Play.cmd').write_text('@echo off\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start.ps1"\r\nif errorlevel 1 pause\r\n',encoding='ascii')
(package/'StopServer.cmd').write_text('@echo off\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Stop.ps1"\r\nif errorlevel 1 pause\r\n',encoding='ascii')
(package/'README.txt').write_text('''Tripothon — 일곱 밤, 나의 마을 (Windows x64 로컬 데모)

1. ZIP 전체를 쓰기 가능한 폴더에 풉니다. ZIP 안에서 바로 실행하지 마세요.
2. Play.cmd를 실행하면 로컬 서버와 게임이 열립니다. Python/Godot 설치는 필요 없습니다.
3. 영문/숫자/밑줄 3~24자의 이름, 10자 이상 비밀번호로 새 탐험가를 만드세요.
4. WASD 이동, Shift 달리기, E 채집/NPC 대화/탐험 지도, Q 먹기, F 모닥불, H 붕대, Space 공격.
   E/Space는 누르고 있어도 됩니다. I 가방·제작, M 음소거, 마우스 휠 확대/축소.
   생존 중 Esc는 일시 정지/저장 후 마을 귀환. 물건 배치 중 R 회전, Esc 취소.
5. 일곱 밤(약 7분) 생존 → 별씨 보상 → 샘플 물건 만들기 → 색칠/배치.
   낮에 목재와 열매를 모으고, 밤이 오면 중앙 야영지에서 F로 불을 피우세요.
   목재 2개로 불이 30초 유지됩니다. 불빛 밖에서는 빨간 공격 예고를 Shift로 피하세요.
   도끼(목재 3/돌 2)는 목재 채집량을 늘리고, 창(목재 4/돌 2)은 적을 강하게 공격합니다.
   Esc → 저장 후 마을로 → 숲 입장으로 같은 도전을 이어갈 수 있습니다.
   현재 우선순위는 맵·캐릭터·7일 생존이며, 거래 화면은 후속 개발로 미뤘습니다.
6. 마칠 때 게임을 닫고 StopServer.cmd로 이 패키지가 시작한 서버를 종료합니다.

이 패키지의 공방은 API 비용 없이 상자·꽃 조명·시계의 도형 예제를 만듭니다. 실제 AI 생성이 아닙니다.
실제 Tripo 정적/동적 가구와 이미지 보정 생성은 2026-10-02 개발 환경에서 검증했습니다.
이 배포본에는 개인 생성물/계정/키/비교 DB를 포함하지 않습니다.
공개 거래에는 별도 운영 서버와 HTTPS가 필요합니다. 실제 AI 생성에는 Tripo 크레딧도 필요합니다.
API 키·개인 계정·기존 DB·플레이어 생성 파일은 패키지에 포함하지 않았습니다.
Explorer B는 기존 제작 주인공이며, 이전 탐험가·NPC·공방에는 Scenario 생성 공용 아트를 사용합니다.

서버는 127.0.0.1:8765에만 연결합니다. 외부 인터넷에 공개되지 않습니다.
이미 같은 포트의 호환 Tripothon demo 서버(protocol 6)가 실행 중이면 그 서버에 연결합니다.
구버전 서버가 있으면 안내에 따라 종료하고 다시 실행하세요. 기존 DB를 삭제할 필요는 없습니다.
이 패키지가 새로 시작한 서버의 저장 위치: %LOCALAPPDATA%\\TripothonDemo\\server-data
게임 클라이언트는 개인 생성 GLB를 파일로 저장하지 않습니다.
로컬 데모 서버의 DB/샘플 GLB는 개발·시연용으로 이 PC에 저장됩니다.
공개 거래용 서버를 플레이어에게 배포하거나 이 로컬 DB를 신뢰하면 안 됩니다.

버전 0.8.1: Explorer B 원본 얼굴·hand-v4·전용 걷기를 기본 주인공으로 추가했습니다.
기존 플레이어 3명, NPC 5명, 생존 지역 3곳과 난이도 3단계도 유지합니다.
마을의 작은 집과 공방 앞에서 E로 들어가세요. 실내의 문에서 E로 마을에 돌아옵니다.
공방에서 꽃 조명·상자·시계의 검증용 도형을 만들고, 배치·회전·이동·색칠·회수합니다.
이는 고정 예제 설계이며 LLM/Tripo를 호출한 것으로 표시하지 않습니다.
부품 맞춤으로 위치/회전축/크기를 미리 보고 저장하거나 원래 설계로 복원합니다.
직접 색 선택과 원래 색 복원, 제작 비용 이력을 확인할 수 있습니다.
탐험 지도 → 이야기 수첩에서 세 장을 순서대로 진행합니다. 첫 완료 보너스와 집 앞 기념등은 한 번만 지급됩니다.
AI 설계/유료 생성은 운영자가 별도 서버에 제공사 연결을 설정해야 합니다.
마을 지형을 72×68로 넓히고 텃밭·과수원·강과 두 다리·언덕·호수·해변을 추가했습니다.
Tab으로 마을 지도를 열어 목적지를 고르고, B로 생활 창고를 확인하세요.
E로 가까운 텃밭·낚시터·채집물·NPC와 상호작용합니다.
텃밭 6칸에 순무(90초)와 호박(150초)을 심고 물을 한 번 준 뒤 2개씩 수확합니다.
성장은 서버 시간으로 저장되므로 게임을 꺼도 계속됩니다.
낚시터에서 미끼를 던지고 금빛 입질 신호가 오면 3.5초 안에 E로 챔질하세요.
씨앗 가게에서 수확물을 팔고 씨앗·미끼를 삽니다. 잎전은 별씨/API 크레딧과 다른 재화입니다.
순무 2개+강농어 1마리를 식탁에 배달하면 하루 한 번 20잎전을 받습니다(UTC 날짜 기준).
마을 보행은 로컬이며 서버는 생활 자산의 소유권·수량·시간·중복 지급을 검증합니다.
마을의 옷장에서 캐릭터·머리·상의·하의·신발·피부·모자·배낭을 고르고 저장하세요.
탐험 지도에서 지역과 난이도를 선택합니다. 진행 중 선택은 바뀌지 않습니다.
숲 1.0 / 채석장 1.15 / 서리 1.3 × 산책 0.7 / 탐험 1.0 / 개척 1.6의 보상 배율입니다.
Scenario Tripo로 만든 미라·테오·이끼 수호자, 원거리 불씨 도깨비를 추가했습니다.
플레이어 3명에 걷기·대기·달리기·도끼 뼈대 동작과 부위별 색칠을 적용했습니다.
창·맨손·식사·피격은 절차적 상체 동작이며, 임의 의상 메시 교체는 구현하지 않았습니다.
마을·숲의 반복 배경음과 효과음은 외부 샘플 없이 직접 합성했습니다. M으로 음소거합니다.
보관함은 I 또는 하단 버튼으로 엽니다. 선택한 물건은 3D 미리보기에서 색을 확인할 수 있습니다.
같은 마을에서 여러 캐릭터가 동시에 보이는 실시간 멀티플레이는 구현하지 않았습니다.
실행 파일은 별도 배포 인증서로 서명하지 않았습니다.
''',encoding='utf-8-sig')
out=root/'artifacts'/'Tripothon_Windows_Demo_20261002.zip'
with ZipFile(out,'w',ZIP_DEFLATED) as archive:
    for path in sorted(package.rglob('*')):
        if path.is_file(): archive.write(path,path.relative_to(package.parent))
print(str(out))
print('bytes:',out.stat().st_size,'sha256:',hashlib.sha256(out.read_bytes()).hexdigest())
