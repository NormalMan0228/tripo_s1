"""Private local study copies; retain originals and reject unsafe archive paths."""
import hashlib
import io
import json
import zipfile
from pathlib import Path, PurePosixPath

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/stefan-course-audit-20261004'
records = []
for course in ('character', 'environment'):
    with zipfile.ZipFile(Path('C:/Users/dd/Desktop') / f'stefan_{course}_files.zip') as outer:
        for archive in outer.infolist():
            if not archive.filename.lower().endswith('.zip'):
                continue
            dest = (out / 'assignment-assets' / course / Path(archive.filename).stem).resolve()
            with zipfile.ZipFile(io.BytesIO(outer.read(archive))) as inner:
                for info in inner.infolist():
                    if info.is_dir():
                        continue
                    relative = PurePosixPath(info.filename.replace('\\', '/'))
                    if relative.is_absolute() or '..' in relative.parts or any(':' in p for p in relative.parts):
                        raise ValueError('Unsafe archive member')
                    target = dest.joinpath(*relative.parts).resolve()
                    if not target.is_relative_to(dest):
                        raise ValueError('Archive member escapes study folder')
                    data = inner.read(info)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    records.append({'course': course, 'archive': archive.filename,
                                    'member': info.filename, 'path': str(target),
                                    'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            print(course, Path(archive.filename).name, flush=True)
(out / 'assignment-assets.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
print('files', len(records), 'blend', sum(Path(r['path']).suffix == '.blend' for r in records))
