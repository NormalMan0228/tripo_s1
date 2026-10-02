"""Audit finished ZIPs without printing secret values or private file contents."""
import argparse,hashlib,json,sys
import certifi
from pathlib import Path,PurePosixPath
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.config import read_tripo_key

def main():
    parser=argparse.ArgumentParser();parser.add_argument('archives',type=Path,nargs='+')
    parser.add_argument('--key-file',type=Path);args=parser.parse_args()
    secret=read_tripo_key(args.key_file) if args.key_file else ''
    needles=[secret.encode(),secret.encode('utf-16-le')] if secret else []
    results=[];failed=False
    for path in args.archives:
        issues=[]
        with ZipFile(path) as archive:
            bad=archive.testzip()
            if bad:issues.append({'file':bad,'reason':'crc'})
            for info in archive.infolist():
                name=PurePosixPath(info.filename);parts={p.casefold() for p in name.parts}
                if name.is_absolute() or '..' in name.parts:issues.append({'file':info.filename,'reason':'unsafe_path'})
                trusted_ca=info.filename.endswith('/certifi/cacert.pem') and archive.read(info)==Path(certifi.where()).read_bytes()
                if (name.suffix.casefold() in ('.db','.sqlite','.sqlite3','.pem','.key') and not trusted_ca) or name.name in ('.env','tripo_key.txt') or parts&{'server-data','.codex','.tools','.git'}:
                    issues.append({'file':info.filename,'reason':'private_or_runtime_content'})
                if needles:
                    tail=b''
                    with archive.open(info) as source:
                        while chunk:=source.read(1024*1024):
                            data=tail+chunk
                            if any(needle in data for needle in needles):
                                issues.append({'file':info.filename,'reason':'known_secret_match'});break
                            tail=data[-max(map(len,needles)):]
            result={'archive':path.name,'files':len(archive.infolist()),'bytes':path.stat().st_size,'issues':issues,'known_key_checked':bool(secret)}
        with path.open('rb') as source:result['sha256']=hashlib.file_digest(source,'sha256').hexdigest()
        results.append(result);failed=failed or bool(issues)
    out=ROOT/'artifacts/release-audit.json';out.write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results));return int(failed)
if __name__=='__main__':raise SystemExit(main())
