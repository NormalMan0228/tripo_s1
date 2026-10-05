"""Encode and inspect the actual Godot camera tour, without altering map assets."""
from pathlib import Path
import json
import subprocess
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/maps/archipelago_terrain_v6/video'
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FFPROBE = ROOT / '.tools/krita-5.3.4/krita-x64-5.3.4/bin/ffprobe.exe'
RAW = OUT / 'map_tour_1080p_raw.avi'
MOVIE = OUT / 'archipelago_map_tour_1080p.mp4'

recording = (OUT / 'recording_1080p.log').read_text(encoding='utf-8', errors='replace')
assert 'TERRAIN_MAP_TOUR_COMPLETE' in recording, 'Wait for the recording to finish'
errors = (OUT / 'recording_1080p_errors.log').read_text(encoding='utf-8', errors='replace')
assert not any(token in recording + errors for token in ['SCRIPT ERROR', 'SHADER ERROR', 'ERROR:', 'Parse Error'])
subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(RAW),
                '-vf', 'scale=in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709',
                '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-colorspace', 'bt709',
                '-color_primaries', 'bt709', '-color_trc', 'bt709',
                '-movflags', '+faststart', str(MOVIE)], check=True)
metadata = json.loads(subprocess.check_output([str(FFPROBE), '-v', 'error',
                        '-show_streams', '-show_format', '-of', 'json', str(MOVIE)], text=True))
stream = next(item for item in metadata['streams'] if item['codec_type'] == 'video')
assert (stream['width'], stream['height']) == (1920, 1080)
assert stream['codec_name'] == 'h264' and stream['pix_fmt'] == 'yuv420p'
assert stream['color_range'] == 'tv' and stream['color_space'] == 'bt709'
assert stream['avg_frame_rate'] == '30/1'
duration = float(metadata['format']['duration'])
assert 48.0 <= duration < 48.2
assert int(stream['nb_frames']) >= 1440

times = [0, 6, 12, 18.6, 23, 28, 33, 39, 44, 47]
sheet = Image.new('RGB', (384 * 5, 240 * 2), '#102635')
draw = ImageDraw.Draw(sheet)
checks = []
for i, time in enumerate(times):
    path = OUT / f'frame_{time:04.1f}s.png'
    subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(time),
                    '-i', str(MOVIE), '-frames:v', '1', str(path)], check=True)
    with Image.open(path) as frame:
        frame = frame.convert('RGB')
        values = np.asarray(frame)
        assert values.std() > 15 and values.mean() > 30, 'Missing rendered image'
        sheet.paste(frame.resize((384, 216)), ((i % 5) * 384, (i // 5) * 240))
        draw.text(((i % 5)*384 + 10, (i // 5)*240 + 219), f'{time:.1f}s', fill='white')
        checks.append({'time_s': time, 'brightness_mean': float(values.mean()), 'brightness_std': float(values.std())})
sheet.save(OUT / 'map_tour_contact_sheet.jpg', quality=92)
report = {'file': MOVIE.name, 'width': 1920, 'height': 1080, 'fps': 30,
          'duration_s': duration, 'frames': int(stream['nb_frames']),
          'codec': 'h264', 'pixel_format': 'yuv420p', 'bytes': MOVIE.stat().st_size,
          'rendered_camera_tour': True, 'runtime_errors': 0, 'sampled_frames': checks}
(OUT / 'video_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('MAP_TOUR_VIDEO_VERIFIED', json.dumps(report), flush=True)
