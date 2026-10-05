"""Encode the actual close-camera gameplay capture and add it to the local review."""
from pathlib import Path
import json
import shutil
import subprocess
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'artifacts/detail-map-20261003/playtest/closeup'
REVIEW = ROOT / 'artifacts/production-lab-20261003/review'
MEDIA = REVIEW / 'art-slice/closeup'
FFMPEG = ROOT / '.tools/art-venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'
audit = json.loads((SOURCE / 'closeup-audit.json').read_text(encoding='utf-8'))
if not audit['passed'] or audit['frames'] < 1:
    raise SystemExit('Closeup gameplay acceptance failed')
movie = SOURCE / 'village-closeup-play.mp4'
with Image.open(SOURCE / 'map-frames/frame-0000.jpg') as first_frame:
    width, height = first_frame.size
subprocess.run([
    str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-y',
    '-framerate', str(audit['fps']), '-i', str(SOURCE / 'map-frames/frame-%04d.jpg'),
    '-frames:v', str(audit['frames']), '-an',
    '-vf', 'scale=iw:ih:in_range=auto:out_range=tv,format=yuv420p',
    '-color_range', 'tv', '-c:v', 'libx264', '-profile:v', 'baseline',
    '-crf', '18', '-movflags', '+faststart', str(movie),
], check=True)
# A full decode catches truncated output before the user opens the video.
subprocess.run([str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-i', str(movie),
                '-f', 'null', '-'], check=True)
MEDIA.mkdir(parents=True, exist_ok=True)
for filename in ['village-closeup-play.mp4', 'closeup-audit.json',
                 'closeup-start.png', 'closeup-npc.png', 'closeup-interior.png']:
    shutil.copy2(SOURCE / filename, MEDIA / filename)
page = '''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tripothon · 근접 카메라 플레이 영상</title><style>
*{box-sizing:border-box}body{margin:0;background:#f6f1e7;color:#294b3d;font-family:"Malgun Gothic",system-ui,sans-serif;line-height:1.7}
main{max-width:1160px;margin:auto;padding:24px 24px 60px}h1{font-size:27px;margin:10px 0 8px}p{margin:8px 0;color:#69796c}
video{display:block;width:100%;max-height:70vh;background:#172e25;border-radius:15px;margin:20px 0 14px}
a{color:#316a52}.meta{display:flex;flex-wrap:wrap;gap:10px;margin:15px 0}.meta span{background:#e3eadb;padding:4px 12px;border-radius:30px;font-size:14px}
.stills{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:24px 0}figure{margin:0}img{width:100%;border-radius:10px}figcaption{font-size:14px;color:#69796c}
@media(max-width:700px){main{padding:16px}.stills{grid-template-columns:1fr}h1{font-size:23px}}
</style><main><a href="art-slice.html">← 전체 제작 결과</a>
<h1>근접 카메라 · 실제 플레이 영상</h1>
<p>캐릭터를 따라 걷기·달리기 → 해루와 대화 → 집 안으로 들어갔다가 마을로 돌아오기.</p>
<video controls autoplay loop muted playsinline preload="auto" poster="art-slice/closeup/closeup-start.png" src="art-slice/closeup/village-closeup-play.mp4"></video>
'''
page += f'''<div class="meta"><span>{width} × {height} · {audit['fps']}fps</span><span>{audit['seconds']:.1f}초</span><span>기존 대비 약 {audit['original_camera_size_m']/audit['camera_size_m']:.2f}배 근접</span><span>고정 카메라 방향</span></div>
<p><a href="art-slice/closeup/village-closeup-play.mp4" download>MP4 저장</a> · <a href="art-slice/closeup/closeup-audit.json">실행 검사 기록</a></p>
<div class="stills"><figure><img src="art-slice/closeup/closeup-start.png" alt="탐험가의 정면 근접 화면"><figcaption>탐험가 정면</figcaption></figure><figure><img src="art-slice/closeup/closeup-npc.png" alt="해루 옆의 플레이어"><figcaption>해루에게 다가가기</figcaption></figure><figure><img src="art-slice/closeup/closeup-interior.png" alt="집 안의 탐험가"><figcaption>집 내부</figcaption></figure></div>
<p>Godot의 실제 이동·충돌·상호작용 코드에 자동 조작을 입력해 녹화했습니다. 집 출입은 페이드 전환을 사용하며, 산책 중 임의의 위치 변경이나 화면 확대 편집은 넣지 않았습니다.</p></main></html>'''
(REVIEW / 'closeup-play.html').write_text(page, encoding='utf-8')
existing = REVIEW / 'art-slice.html'
if existing.exists():
    original = existing.read_text(encoding='utf-8')
    if 'href="closeup-play.html"' not in original:
        existing.write_text(original.replace('<nav>', '<nav><a href="closeup-play.html">근접 플레이 영상</a>', 1), encoding='utf-8')
print('CLOSEUP_VIDEO', movie)
print('CLOSEUP_PAGE', 'http://127.0.0.1:8842/closeup-play.html')
