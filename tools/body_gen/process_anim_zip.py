"""One Tripo animation export (zip) -> game GLB + review sheet + GIF.

  python tools/body_gen/process_anim_zip.py <monster id> <export.zip> [--no-gif]

1. extracts the zip into a fresh scratch folder (downloads are untrusted data);
2. copies the FBX (as mon_<id>_anim.fbx) and its .fbm texture folder to
   art/characters/body_p2_v1/mon_v3/anim/src/<id>/ (the FBX references the texture by that folder);
3. builds anim/game/<id>.glb with build_game_monster.py (config anim/game_build.json);
4. renders 6 frames per clip -> anim/sheets/<id>_clips.png, and a 12 fps GIF -> anim/sheets/<id>_clips.gif;
5. prints a one-line summary per clip (seconds, loop window, no-pop numbers, warnings).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLENDER = os.path.join(ROOT, '.tools', 'blender-portable', 'blender-4.5.3-windows-x64', 'blender.exe')
ANIM = os.path.join(ROOT, 'art', 'characters', 'body_p2_v1', 'mon_v3', 'anim')
TOOLS = os.path.join(ROOT, 'tools', 'body_gen')
KO = {'goblin': '고블린', 'werewolf': '늑대인간', 'troll': '트롤', 'cyclops': '사이클롭스', 'treant': '고목 거인',
      'skeleton': '해골 기사', 'lizardman': '리자드맨', 'minotaur': '미노타우로스', 'mummy_king': '미라 왕',
      'ghoul': '구울', 'ice_shardling': '얼음 정령', 'draugr': '얼어붙은 전사', 'yeti': '예티', 'wendigo': '웬디고',
      'frost_hag': '서리 마녀', 'frost_knight': '서리 망령 기사', 'ice_golem': '얼음 골렘', 'glacier_giant': '빙하 거인',
      'boni': '보니', 'sol': '솔'}


def run(args):
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    lines = (r.stdout + r.stderr).splitlines()
    tail = '\n'.join(l for l in lines if 'Error' in l or 'Traceback' in l or 'line ' in l or 'matched' in l)
    if r.returncode or 'Traceback' in tail:
        raise SystemExit('FAILED %s\n%s\n%s' % (' '.join(args[:5]), tail[-2000:], '\n'.join(lines[-6:])))
    return r.stdout


def main():
    mid, zpath = sys.argv[1], sys.argv[2]
    CFG = os.environ.get('GAME_BUILD') or os.path.join(ANIM, 'game_build.json')  # e.g. game_build_flyers.json
    gif = '--no-gif' not in sys.argv
    scratch = os.environ.get('BODY_SCRATCH') or tempfile.gettempdir()
    work = tempfile.mkdtemp(prefix='anim_%s_' % mid, dir=scratch)
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():  # no absolute paths or '..' out of the folder
            if n.startswith(('/', '\\')) or '..' in n.replace('\\', '/').split('/'):
                raise SystemExit('unsafe path in zip: %s' % n)
        z.extractall(work)
    fbx = [f for f in os.listdir(work) if f.lower().endswith('.fbx')]
    fbm = [f for f in os.listdir(work) if f.lower().endswith('.fbm')]
    if len(fbx) != 1:
        raise SystemExit('expected one FBX in the zip, found %s' % fbx)
    dst = os.path.join(ANIM, 'src', mid)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    src_fbx = os.path.join(dst, 'mon_%s_anim.fbx' % mid)
    shutil.copy2(os.path.join(work, fbx[0]), src_fbx)
    for d in fbm:
        shutil.copytree(os.path.join(work, d), os.path.join(dst, d))

    os.makedirs(os.path.join(ANIM, 'game'), exist_ok=True)
    os.makedirs(os.path.join(ANIM, 'sheets'), exist_ok=True)
    glb = os.path.join(ANIM, 'game', mid + '.glb')
    rep = os.path.join(ANIM, 'game', mid + '_report.json')
    run([BLENDER, '-b', '--factory-startup', '-P', os.path.join(TOOLS, 'build_game_monster.py'), '--',
         src_fbx, glb, CFG, mid, rep])
    frames = os.path.join(work, 'frames')
    run([BLENDER, '-b', '--factory-startup', '-P', os.path.join(TOOLS, 'render_clips.py'), '--', glb, frames, '6'])
    py = sys.executable
    nclips = len(json.load(open(CFG, encoding='utf-8'))['monsters'][mid]['clips'])
    title = '%s (%s) — 게임 클립 %d개, 모두 AI 생성' % (KO.get(mid, mid), mid, nclips)
    run([py, os.path.join(TOOLS, 'clip_sheet.py'), frames, os.path.join(ANIM, 'sheets', mid + '_clips.png'), title, rep])
    if gif:
        gframes = os.path.join(work, 'gif')
        run([BLENDER, '-b', '--factory-startup', '-P', os.path.join(TOOLS, 'render_clips.py'), '--', glb, gframes, '-12', '3q', '300'])
        run([py, os.path.join(TOOLS, 'clip_gif.py'), gframes, os.path.join(ANIM, 'sheets', mid + '_clips.gif'),
             '%s — 실제 재생 속도' % KO.get(mid, mid), '12', '3.0'])
    r = json.load(open(rep, encoding='utf-8'))
    print('GLB', glb, os.path.getsize(glb), 'tris', r.get('triangles'), 'impact', r.get('attack_impact_seconds'))
    for k, v in r['clips'].items():
        print(' %-6s %5.2fs loopwin=%s pop=%s hips=%s seam=%s/%s sink=%s' % (
            k, v['seconds'], v.get('loop_window_seconds'), v['max_bone_deg_per_frame'], v['max_hips_move_per_frame_ratio'],
            v.get('seam_pose_deg'), v.get('seam_speed_jump_deg'), v.get('ground_sink_left_ratio')))
    print('WARN', r['warnings'])
    shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
