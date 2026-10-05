import json
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
sheet = Image.new('RGB', (1200, 1600), '#e9edf0')
draw = ImageDraw.Draw(sheet)
for row, name in enumerate(['sora', 'moru', 'naru', 'haeru']):
    record = root / 'art/references/npc_cast_closed_v2' / name / 'image-generation.json'
    data = json.loads(record.read_text(encoding='utf-8'))
    proportions = 'Preserve adult tall 6.5-head proportions and long torso and limbs, square sheet.' if name == 'haeru' else 'Preserve existing tall stylized proportions and landscape 3:2 sheet.'
    data['prompt'] = f'Precise minimal edit of the supplied {name} character turnaround reference. Preserve the SAME character identity, eyes, brows, nose, chin, hairstyle, outfit, accessories, skin tone, body proportions, hand pose, full body A pose, view orientation, backdrop, lighting, and three-column layout exactly. Change ONLY the mouth in FRONT and RIGHT PROFILE views: naturally relaxed CLOSED lips with a very slight friendly smile, no visible teeth, tongue, dark mouth gap, or exaggerated upturned corners. Preserve jaw and chin shape and face length, do not reshape the whole face or make younger. Back view unchanged. Output the complete same three-view full-body modeling reference sheet: FRONT, RIGHT (profile facing screen right), BACK, same character and scale across views. Keep all hair and boots and hands fully inside frame, ample margins, soft white studio background. {proportions} This is a mouth-closing edit, not a redesign. No additional figures or inset portraits.'
    record.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    for col, view in enumerate(['front', 'angle', 'back']):
        im = Image.open(root / 'art/characters/npc_cast_closed_v2' / name / (view + '.png'))
        im.thumbnail((320, 375))
        sheet.paste(im, (col * 400 + 40, row * 400 + 20))
        draw.text((col * 400 + 10, row * 400 + 3), name + ' ' + view, fill='black')
sheet.save(root / 'art/characters/npc_cast_closed_v2/review-contact-sheet.png')
