"""Make a source handoff without secrets, saved accounts, generated private props, or runtimes."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib

root=Path(__file__).resolve().parents[1]
out=root/'artifacts'/'Tripothon_Source_20261002.zip'
out.parent.mkdir(exist_ok=True)
files=[]
for base in ['game','server','tools','docs']:
    for path in (root/base).rglob('*'):
        if not path.is_file() or any(part in ('.godot','__pycache__','.pytest_cache') for part in path.parts): continue
        if path.suffix=='.pyc': continue
        files.append(path)
files.extend(root/name for name in ['README.md','.gitignore','.dockerignore','.env.example','Play.cmd','Open_Studio.cmd'])
with ZipFile(out,'w',ZIP_DEFLATED) as archive:
    for path in sorted(files): archive.write(path,path.relative_to(root))
print(str(out))
print('files:',len(files),'bytes:',out.stat().st_size)
print('sha256:',hashlib.sha256(out.read_bytes()).hexdigest())
