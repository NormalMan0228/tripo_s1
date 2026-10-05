"""Collect generated 2D part references without editing the image contents."""
from pathlib import Path
import hashlib
import json
import shutil

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/references/explorer_b_modular_v1/02_parts'
GENERATED = Path.home() / '.codex/generated_images'


def main():
    path = BASE / 'generation-manifest-v1.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    for item in manifest['assets']:
        record_path = BASE / (item['id'] + '-generation-v1.json')
        if not record_path.is_file():
            continue
        record = json.loads(record_path.read_text(encoding='utf-8'))
        source = Path(record['generated_source']).resolve()
        if not source.is_file() or not source.is_relative_to(GENERATED.resolve()):
            raise ValueError('invalid_generated_source')
        target = (BASE / item['file']).resolve()
        if not target.is_relative_to(BASE.resolve()) or target.suffix != '.png':
            raise ValueError('invalid_reference_target')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError('preserve_existing_reference_create_new_revision')
        else:
            shutil.copy2(source, target)
        with Image.open(target) as image:
            image.verify()
        with Image.open(target) as image:
            item['pixels'] = list(image.size)
        item.update(state='saved', sha256=digest,
                    generation_record=record_path.name,
                    review_status='awaiting_user_review')
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    saved = [a for a in manifest['assets'] if a['state'] == 'saved']
    print(json.dumps({'saved_images': len(saved), 'planned_images': len(manifest['assets']),
                      'new_tripo_calls': 0, 'new_scenario_calls': 0}))


if __name__ == '__main__':
    main()
