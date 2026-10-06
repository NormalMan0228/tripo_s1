"""Make a versioned, credential-free baseline with both client modes."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import importlib.metadata
import json
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    version = re.search(r'config/version="([\d.]+)"', (ROOT / 'game/project.godot').read_text(encoding='utf-8-sig')).group(1)
    package = ROOT / 'builds' / ('Tripothon_Baseline_' + version.replace('.', ''))
    # Never reuse a played package directory: it may contain accounts or logs.
    if package.exists():
        raise SystemExit('Package directory already exists; choose a fresh version or preserve it separately.')
    package.mkdir(parents=True)
    hashes = {}
    for name in ('Villagen.exe', 'Villagen.pck', 'Villagen_Developer.exe', 'Villagen_Developer.pck'):
        source = ROOT / 'builds/windows' / name
        shutil.copy2(source, package / name)
        with source.open('rb') as stream:
            hashes[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    shutil.copytree(ROOT / 'builds/TripothonDemoServer', package / 'server')
    shutil.copytree(ROOT / 'docs/licenses', package / 'licenses')
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copy2(python_license, package / 'licenses/Python-LICENSE.txt')
    for distribution in importlib.metadata.distributions():
        for entry in distribution.files or []:
            if not any(word in entry.name.upper() for word in ('LICENSE', 'COPYING', 'NOTICE')):
                continue
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                name = distribution.metadata['Name'].replace('/', '_').replace('\\', '_')
                target = package / 'licenses' / name / entry.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    for source, target in (('portable_start.ps1', 'Start.ps1'), ('portable_stop.ps1', 'Stop.ps1')):
        shutil.copy2(ROOT / 'tools' / source, package / target)
    for name, flag, script in (('Play.cmd', '', 'Start.ps1'), ('Play_Developer.cmd', ' -Developer', 'Start.ps1'), ('StopServer.cmd', '', 'Stop.ps1')):
        command = f'@echo off\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0{script}"{flag}\r\nif errorlevel 1 pause\r\n'
        (package / name).write_text(command, encoding='ascii')
    (package / 'README.txt').write_text(f'''Tripothon {version} — Windows x64

ZIP 전체를 쓰기 가능한 폴더에 푼 뒤 실행하세요.
온라인 플레이: Villagen.exe (새 가입에는 초대 코드 필요)
비용 없는 로컬 체험: Play.cmd
개발 화면 포함 로컬 체험: Play_Developer.cmd
로컬 서버 종료: 게임을 닫고 StopServer.cmd

로컬 체험에는 Python/Godot 설치가 필요 없습니다.
이름: 영문·숫자·밑줄 3~24자 / 비밀번호: 10자 이상.
WASD 이동, Shift 달리기, E 상호작용, Tab 마을 지도, B 생활 창고.
I 가방·제작, Space 공격, Q 먹기, F 모닥불, H 붕대, M 음소거.
집·공방 입구에서 E. 가구 배치 중 R 회전 / Esc 취소.
생존 중 Esc에서 저장 후 귀환할 수 있습니다.

로컬 공방의 상자·조명·시계는 무료 검증 예제입니다.
온라인 데모의 유료 AI 생성은 현재 꺼져 있습니다.
계정은 온라인과 로컬에서 각각 관리됩니다.
로컬 저장 위치: %LOCALAPPDATA%\\TripothonDemo\\server-data
개발용 화면: F3 진단, 공방 모델·코드·부품 맞춤·기록.
플레이어 실행본은 개발용 실행 인자를 붙여도 개발 화면을 표시하지 않습니다.

키·개인 계정 DB는 패키지에 없습니다. 실행 파일은 서명하지 않았습니다.
''', encoding='utf-8-sig')
    manifest = {'version': version, 'server_protocol': 6, 'godot': '4.7.2', 'client_sha256': hashes}
    (package / 'baseline.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    out = ROOT / 'artifacts' / f'Tripothon_Baseline_{version}_Windows.zip'
    with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(package.parent))
    print(json.dumps({'package': str(package), 'archive': str(out), **manifest}, indent=2))


if __name__ == '__main__':
    main()
