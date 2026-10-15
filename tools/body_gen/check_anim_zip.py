"""Which of a monster's motions are missing from a Tripo animation export (no Blender needed).

  python tools/body_gen/check_anim_zip.py <monster id> <export.zip>

Tripo stores each action under the first ~60 characters of its prompt, so a clip is present when
the first 52 characters of its prompt (art/characters/body_p2_v1/mon_v3/anim/motion_prompts.json)
occur in the FBX bytes. With several Tripo animate pages open, a finished motion can be applied to
another page's model instead, so check every export before building.
"""
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = os.path.join(ROOT, 'art', 'characters', 'body_p2_v1', 'mon_v3', 'anim', 'motion_prompts.json')

mid, zpath = sys.argv[1], sys.argv[2]
cfg = json.load(open(os.path.join(os.path.dirname(P), 'game_build.json'), encoding='utf-8'))['monsters'][mid]
with zipfile.ZipFile(zpath) as z:
    fbx = [n for n in z.namelist() if n.lower().endswith('.fbx')]
    data = z.read(fbx[0])
missing = []
for clip, spec in cfg['clips'].items():
    text = spec if isinstance(spec, str) else spec['match']
    if text.encode() not in data:
        missing.append(clip)
print(json.dumps({'id': mid, 'missing': missing, 'ok': not missing}))
