"""Download pinned official face tools; do not change existing Blender preferences."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / '.tools/face-tools'
PACKAGES = [
    ('mpfb-2.0.17.zip', 'https://extensions.blender.org/download/sha256:4f0a879d64a39bf646fbf5f53601ac678855da329d650617dca5737548239a87/add-on-mpfb-v2.0.17.zip', '4f0a879d64a39bf646fbf5f53601ac678855da329d650617dca5737548239a87'),
    ('makehuman_system_assets_cc0.zip', 'https://files2.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip', None),
    ('faceunits01.zip', 'https://files2.makehumancommunity.org/functional/faceunits01.zip', None),
    ('visemes01.zip', 'https://files2.makehumancommunity.org/functional/visemes01.zip', None),
    ('visemes02.zip', 'https://files2.makehumancommunity.org/functional/visemes02.zip', None),
]

def download(entry):
    name, url, expected = entry
    path = DEST / name
    if not path.exists():
        request = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        temporary = path.with_suffix('.partial')
        with urllib.request.urlopen(request, timeout=60) as source, temporary.open('wb') as target:
            while chunk := source.read(1024*1024): target.write(chunk)
        temporary.replace(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected and expected != digest: raise RuntimeError('Digest mismatch: ' + name)
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad: raise RuntimeError('Invalid archive: ' + bad)
        print(json.dumps({'package':name,'bytes':path.stat().st_size,'first_members':archive.namelist()[:5]}),flush=True)
    return {'file':name,'url':url,'sha256':digest,'official_hash_verified':bool(expected),'bytes':path.stat().st_size}

if __name__ == '__main__':
    DEST.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(download, PACKAGES))
    (DEST/'downloads.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
