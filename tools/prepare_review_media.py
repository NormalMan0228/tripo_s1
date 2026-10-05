"""Produce browser-friendly copies of existing recordings without paid API calls."""
from pathlib import Path
import subprocess
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/production-lab-20261003'
DEST = OUT / 'review'
FFMPEG = ROOT / '.tools/art-venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'

for name in ('gameplay-motion', 'current-game-motion'):
    source = OUT / f'{name}.mp4'
    for extension, codec in (
        ('mp4', ['-c:v', 'libx264', '-profile:v', 'baseline', '-level:v', '3.1',
                 '-crf', '20', '-movflags', '+faststart']),
        ('webm', ['-c:v', 'libvpx-vp9', '-crf', '30', '-b:v', '0', '-row-mt', '1']),
    ):
        target = OUT / f'{name}-browser.{extension}'
        subprocess.run([str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-y',
                        '-i', str(source), '-an', '-vf',
                        'scale=1152:720:in_range=auto:out_range=tv,format=yuv420p',
                        '-color_range', 'tv', '-r', '30', *codec, str(target)], check=True)
        shutil.copy2(target, DEST / target.name)
    poster = OUT / f'{name}-poster.jpg'
    subprocess.run([str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-y',
                    '-ss', '2.5', '-i', str(source), '-frames:v', '1',
                    '-vf', 'scale=1152:720', '-update', '1', str(poster)], check=True)
    shutil.copy2(poster, DEST / poster.name)
    print('MEDIA_READY', name, flush=True)
