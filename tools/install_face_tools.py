"""Download pinned official face tools; do not change existing Blender preferences."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / '.tools/face-tools'
LOCAL = Path(__file__).with_name("third_party_downloads.local.json")


def _local(key):
    """Download addresses live in a git-ignored local file: the repository keeps no archive links."""
    if not LOCAL.exists():
        raise SystemExit(f"{LOCAL.name} is missing; put the official download addresses there (see its _note).")
    return json.loads(LOCAL.read_text(encoding="utf-8"))[key]


PACKAGES = [tuple(entry) for entry in _local("face_tools")]


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
