"""Conservative biped craft contract; one retarget task per clip."""
import re

RIG_MODEL = 'v1.0-20240301'
CLIPS = ('idle', 'walk')
RIG_CREDITS = 25
CLIP_CREDITS = 10
POSE = ('Full-body biped character in a neutral A-pose, arms spread 45 degrees, '
        'legs apart, hands open. Single character, no ground, no base, no other parts.')


def character_like(prompt):
    # An explicit character noun is required; unknown subjects fail closed.
    words = prompt.casefold()
    return bool(re.search(r'\b(character|humanoid|person|robot|monster|knight|wizard|warrior|elf|goblin|doll|mascot)\b', words)
                or any(word in words for word in ('캐릭터', '사람', '인간', '로봇', '몬스터', '기사', '마법사', '전사', '요정', '인형', '마스코트')))


def credits(animate):
    return RIG_CREDITS + len(CLIPS) * CLIP_CREDITS if animate else 0


def rig_payload(task):
    return {'input': task, 'model': RIG_MODEL, 'rig_type': 'biped', 'spec': 'tripo', 'out_format': 'glb'}


def animation_payload(task, clip):
    if clip not in CLIPS:
        raise ValueError('unsupported_clip')
    return {'input': task, 'animation': 'preset:biped:' + clip, 'out_format': 'glb',
            'bake_animation': True, 'export_with_geometry': True, 'animate_in_place': True}
