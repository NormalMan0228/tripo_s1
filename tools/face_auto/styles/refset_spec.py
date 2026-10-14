"""Expression reference set: the clips we generate per character and what each one is measured for.

One spec for every style; style-specific wording is added per clip (STYLE_HINT). The generator writes
styles/refset_<style>.json with, per clip: id, keys measured (ARKit names), duration, view (front / side), the prompt,
the negative prompt and model notes. The same file drives the measuring step (which keys to read from which clip).

Rules (2026-10-14, user): no human performance - every clip is generated from the character's own neutral image;
first and last frame = that neutral image (the clip starts and ends neutral, so onset / hold / release can be timed);
locked front camera; audio off; mid tier (720p). L/R pairs are made on one side and mirrored.
Usage: python refset_spec.py   -> styles/refset_cartoon.json, refset_anime.json, refset_semi.json, refset_realistic.json
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

CAMERA = ('Locked-off static camera on a tripod, no camera movement, no zoom, no cut. Head-and-shoulders shot, '
          'face centred and filling the frame. Even studio lighting, plain background. The character keeps the '
          'exact same design, proportions and rendering style as the input image for the whole clip. Silent, no speech.')
NEG = ('camera movement, zoom, head turning, extra people, hands in frame, text, subtitles, style change, '
       'realistic skin if the input is stylised, changing hair or clothes, morphing face, extra teeth')
TIMING = ('Timeline: 0-0.5 s neutral face as in the image; 0.5-1.0 s the expression forms; 1.0-3.0 s hold the '
          'expression at full strength without moving; 3.0-3.6 s relax; ends on the same neutral face as the start.')

# id, name, ARKit keys measured, seconds, views, action text
CLIPS = [
    ('E01', 'smile',     ['mouthSmileLeft', 'mouthSmileRight', 'cheekSquintLeft', 'cheekSquintRight', 'eyeSquintLeft', 'eyeSquintRight', 'mouthDimpleLeft', 'mouthDimpleRight'], 4, ['front'],
     'a warm closed-mouth smile: mouth corners rise, cheeks lift, eyes narrow slightly'),
    ('E02', 'big_smile', ['mouthSmileLeft', 'mouthSmileRight', 'jawOpen', 'mouthUpperUpLeft', 'mouthUpperUpRight', 'mouthLowerDownLeft', 'mouthLowerDownRight'], 4, ['front'],
     'a big open-mouth laugh-smile showing the upper teeth, without sound'),
    ('E03', 'surprise',  ['browInnerUp', 'browOuterUpLeft', 'browOuterUpRight', 'eyeWideLeft', 'eyeWideRight', 'jawOpen'], 4, ['front'],
     'surprise: eyebrows go high, eyes open wide, jaw drops into a round open mouth'),
    ('E04', 'anger',     ['browDownLeft', 'browDownRight', 'noseSneerLeft', 'noseSneerRight', 'mouthPressLeft', 'mouthPressRight', 'eyeSquintLeft', 'eyeSquintRight'], 4, ['front'],
     'anger: eyebrows pull down and together, nose wrinkles, lips press together, eyes narrow'),
    ('E05', 'sadness',   ['browInnerUp', 'mouthFrownLeft', 'mouthFrownRight', 'mouthShrugLower'], 4, ['front'],
     'sadness: inner eyebrows rise, mouth corners pull down, lower lip pushes up'),
    ('E06', 'disgust',   ['noseSneerLeft', 'noseSneerRight', 'mouthUpperUpLeft', 'mouthUpperUpRight', 'browDownLeft', 'browDownRight'], 4, ['front'],
     'disgust: nose wrinkles, upper lip curls up, eyebrows lower'),
    ('E07', 'fear',      ['eyeWideLeft', 'eyeWideRight', 'mouthStretchLeft', 'mouthStretchRight', 'browInnerUp'], 4, ['front'],
     'fear: eyes open wide, mouth stretches sideways, inner eyebrows rise'),
    ('Y08', 'blink',     ['eyeBlinkLeft', 'eyeBlinkRight'], 4, ['front'],
     'one slow full blink of both eyes (close fully at 1.0 s, hold 0.5 s, open), the rest of the face does not move'),
    ('Y09', 'wink_left', ['eyeBlinkLeft', 'cheekSquintLeft'], 4, ['front'],
     "a wink with the character's LEFT eye only (image right side); the other eye stays open"),
    ('Y10', 'look',      ['eyeLookUpLeft', 'eyeLookUpRight', 'eyeLookDownLeft', 'eyeLookDownRight', 'eyeLookInLeft', 'eyeLookInRight', 'eyeLookOutLeft', 'eyeLookOutRight'], 8, ['front'],
     'only the eyes move, the head stays still: look up (1-2 s), centre, look down (3-4 s), centre, look to image left (5-6 s), centre, look to image right (7-8 s)'),
    ('Y11', 'brow_left', ['browOuterUpLeft', 'browInnerUp'], 4, ['front'],
     "raise only the character's LEFT eyebrow (image right side), the other stays down"),
    ('M12', 'vowels',    ['jawOpen', 'mouthFunnel', 'mouthPucker', 'mouthStretchLeft', 'mouthStretchRight'], 6, ['front', 'side'],
     'silently mouth the vowels A, E, I, O, U slowly and clearly, one per second, with a neutral pause between them'),
    ('M13', 'lips',      ['mouthPucker', 'mouthRollUpper', 'mouthRollLower', 'mouthShrugUpper'], 4, ['front', 'side'],
     'push the lips forward into a kiss shape (1-2 s), then roll both lips inward so they disappear (2.5-3.5 s)'),
    ('M14', 'mouth_left', ['mouthLeft', 'mouthClose'], 4, ['front'],
     "with lips closed, slide the whole mouth to the character's LEFT side (image right)"),
    ('M15', 'cheek_puff', ['cheekPuff'], 4, ['front', 'side'],
     'puff both cheeks with air, lips sealed'),
    ('M16', 'jaw',       ['jawLeft', 'jawForward'], 4, ['front', 'side'],
     "move the lower jaw to the character's LEFT (1-2 s), back to centre, then push the jaw forward (2.5-3.5 s)"),
    ('M17', 'jaw_max',   ['jawOpen'], 4, ['front', 'side'],
     'open the mouth as wide as possible, relaxed (like at the dentist), then close'),
    ('M18', 'tongue',    ['tongueOut'], 4, ['front'],
     'stick the tongue out straight, then pull it back in'),
]
STYLE_HINT = {
    'cartoon':   'Style: stylised 3D cartoon (Pixar-like). Expressions are clear and a little exaggerated, squash and stretch allowed, but the face design must not change.',
    'anime':     'Style: anime character rendered in 3D with cel-like shading. Keep the anime look: simple mouth shapes, large eyes, flat shading. Do not make it realistic.',
    'semi':      'Style: semi-realistic game character. Natural expressions of moderate strength.',
    'realistic': 'Style: realistic human. Natural, anatomically correct expressions of moderate strength.',
}
MODEL_NOTES = {
    'first_last': 'Use the neutral front (or side) image as BOTH first and last frame where the model allows it '
                  '(Seedance 2.0, Gemini Omni, Kling Omni 3, Veo). Otherwise first frame only.',
    'settings': '720p (768p), audio off, duration as given (round up to the model minimum).',
}


def build(style):
    clips = []
    for cid, name, keys, sec, views, action in CLIPS:
        for v in views:
            prompt = ' '.join([STYLE_HINT[style], f'The character performs {action}.',
                               TIMING if sec == 4 else f'Total length {sec} s, start and end on the neutral face as in the image.',
                               CAMERA if v == 'front' else CAMERA.replace('Head-and-shoulders shot, face centred', 'Exact side profile view as in the image, head-and-shoulders, face')])
            clips.append({'id': f'{cid}_{v}', 'name': name, 'keys': keys, 'seconds': sec, 'view': v,
                          'first_last_frame': f'neutral_{v}', 'prompt': prompt, 'negative': NEG})
    out = {'style': style, 'clips': clips, 'notes': MODEL_NOTES,
           'count': len(clips), 'seconds_total': sum(c['seconds'] for c in clips)}
    json.dump(out, open(os.path.join(HERE, f'refset_{style}.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    return out


if __name__ == '__main__':
    for st in STYLE_HINT:
        o = build(st); print(st, o['count'], 'clips', o['seconds_total'], 's')
