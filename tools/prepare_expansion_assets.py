import json
from pathlib import Path
from tools.merge_character_clips import merge_clips
from tools.merge_explorer_animations import unpack
p=Path('artifacts/scenario-06')
m=json.loads((p/'metadata.json').read_text())
characters={'ranger':'asset_jahwUGLY12LTpZqhcemqVhMJ','tinker':'asset_fDyyKQCqNBDcJB6tngQSd27U','brute':'asset_s1FsXdYe2LyJMHNQpMVTcWhJ','explorer':'asset_2jK74GPGLGSpb9myyxXvyEUb'}
for name,parent in characters.items():
    clips=[]
    for a in m['assets']:
        if a.get('parentAsset')==parent and a['generator']['name'].startswith('Tripo Rigging'):
            path=p/a['path'];d,b=unpack(path.read_bytes())
            if d.get('animations'): clips.append((d['animations'][0]['name'],path))
    clips.sort(key=lambda x:['walk','idle','run','slash'].index(x[0]))
    result=merge_clips(clips)
    (p/(name+'-animated.glb')).write_bytes(result)
    print(name,len(result),[x[0] for x in clips])
