"""Publishes school builds to S3 instead of GitHub Releases (GitHub keeps code and history only).

Bucket, region, key profile and prefix live in tools/download_host.json. Players get one stable page:
  https://<bucket>.s3.<region>.amazonaws.com/<prefix>/index.html
which always shows the newest version; files sit under <prefix>/<version>/.

  .tools\\art-venv\\Scripts\\python.exe tools/publish_school_build.py setup           # once: bucket + public read on <prefix>/
  .tools\\art-venv\\Scripts\\python.exe tools/publish_school_build.py upload [0.11.4] # builds/release -> S3, page, latest.json
  .tools\\art-venv\\Scripts\\python.exe tools/publish_school_build.py check [--full]  # download as a stranger would
  .tools\\art-venv\\Scripts\\python.exe tools/publish_school_build.py docs            # refresh records + page only
  .tools\\art-venv\\Scripts\\python.exe tools/publish_school_build.py prune 2         # keep the newest 2 versions

Next to the installers go Notepad-friendly records (while GitHub is unavailable they are the public history):
  <prefix>/CHANGES_KO.txt  from docs/releases/school_changes_KO.txt (add the new "== x.y.z (date)" section on top first)
  <prefix>/ROADMAP_KO.txt  plan and progress from docs/roadmap/roadmap.json, plus <prefix>/roadmap.png
The page lists the newest version's lines from CHANGES; upload --notes FILE overrides them.
The upload key comes from tools/aws_upload_login.ps1 (profile in %USERPROFILE%\\.aws\\credentials); nothing secret is
read from or written to the repository.
"""
import datetime
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "tools" / "download_host.json").read_text(encoding="utf-8"))
BUCKET, REGION, PREFIX = CFG["bucket"], CFG["region"], CFG["prefix"].strip("/")
BASE = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{PREFIX}"
PAGE = f"{BASE}/index.html"
OUT = ROOT / "builds" / "release"
SETUP, ZIP, SUMS = "Villagen_School_Setup.exe", "Villagen_School_Windows.zip", "SHA256SUMS_School.txt"
TYPES = {SETUP: "application/vnd.microsoft.portable-executable", ZIP: "application/zip", SUMS: "text/plain; charset=utf-8"}
KST = datetime.timezone(datetime.timedelta(hours=9))
NO_CACHE = "no-cache, max-age=0"
CHANGES = ROOT / "docs" / "releases" / "school_changes_KO.txt"
ROADMAP = ROOT / "docs" / "roadmap"
MARK = {"done": "[완료]", "in_progress": "[진행]", "next": "[다음]", "later": "[이후]", "hold": "[보류]"}


def s3():
    import boto3
    from botocore.config import Config
    return boto3.Session(profile_name=CFG["profile"], region_name=REGION).client(
        "s3", config=Config(retries={"max_attempts": 8, "mode": "adaptive"}))


def game_version() -> str:
    text = (ROOT / "game" / "project.godot").read_text(encoding="utf-8")
    return re.search(r'config/version="([^"]+)"', text).group(1)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def setup() -> None:
    from botocore.exceptions import ClientError
    c = s3()
    try:
        c.head_bucket(Bucket=BUCKET)
        print("bucket exists:", BUCKET)
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("404", "NoSuchBucket", "NotFound"):
            raise
        c.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})
        print("bucket created:", BUCKET)
    # Only bucket policies may grant public read (object ACLs stay blocked), and only for <prefix>/.
    c.put_public_access_block(Bucket=BUCKET, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": False, "RestrictPublicBuckets": False})
    policy = {"Version": "2012-10-17", "Statement": [{
        "Sid": "PublicReadDownloads", "Effect": "Allow", "Principal": "*",
        "Action": "s3:GetObject", "Resource": f"arn:aws:s3:::{BUCKET}/{PREFIX}/*"}]}
    try:
        c.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps(policy))
    except ClientError as e:
        if e.response["Error"]["Code"] == "AccessDenied":
            raise SystemExit("Public read was refused. In the AWS console: S3 > 'Block Public Access settings for this "
                             "account' > Edit > turn off the two 'bucket policies' options, then run setup again.")
        raise
    print("public read on", f"{BUCKET}/{PREFIX}/*")


def local_files() -> dict:
    sums = {}
    for line in (OUT / SUMS).read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            sums[name.strip().lstrip("*")] = digest.lower()
    files = {}
    for name in (SETUP, ZIP):
        path = OUT / name
        if not path.is_file():
            raise SystemExit(f"{path} is missing; run package_release.py --school first")
        print(f"checking {name} ...", flush=True)
        if sha256(path) != sums.get(name):
            raise SystemExit(f"{name} does not match {SUMS}; rebuild or re-run packaging")
        files[name] = {"size": path.stat().st_size, "sha256": sums[name]}
    files[SUMS] = {"size": (OUT / SUMS).stat().st_size, "sha256": sha256(OUT / SUMS)}
    return files


def page(info: dict) -> str:
    ver, files = info["version"], info["files"]
    gb = lambda name: f"{files[name]['size'] / 1024 ** 3:.2f}GB"
    url = lambda name: html.escape(files[name]["url"])
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in info.get("notes", []))
    notes_block = f"<h2>이번 버전에서 바뀐 점</h2><ul>{notes}</ul>" if notes else ""
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Villagen 학교판 내려받기</title>
<style>
:root{{color-scheme:light dark;--bg:#f6f4ef;--fg:#1f2328;--muted:#5b6370;--card:#fff;--line:#d9d4c7;--accent:#2f6f4f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#15181c;--fg:#e8e6e1;--muted:#a0a7b1;--card:#1d2127;--line:#323842;--accent:#6fc095}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,"Malgun Gothic",sans-serif}}
main{{max-width:640px;margin:0 auto;padding:32px 16px}}
h1{{font-size:26px;margin:0 0 4px}} .sub{{color:var(--muted);margin:0 0 24px}}
.btn{{display:block;text-align:center;background:var(--accent);color:#fff;text-decoration:none;font-weight:700;
padding:16px;border-radius:10px;font-size:18px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:16px 0}}
a{{color:var(--accent)}} code{{font-size:13px;word-break:break-all}} small{{color:var(--muted)}}
</style></head><body><main>
<h1>Villagen 학교판 {html.escape(ver)}</h1>
<p class="sub">{html.escape(info["date"])} 공개</p>
<a class="btn" href="{url(SETUP)}">▶ 설치 파일 받기 ({gb(SETUP)})</a>
<div class="card">받은 <b>{SETUP}</b>을 실행 → 설치 위치 선택 → 바탕화면·시작 메뉴에 <b>Villagen</b> 아이콘이 생깁니다.
이전 버전 위에 그대로 설치하면 됩니다.<br>처음 실행할 때 Windows "PC 보호" 창이 뜨면 <b>추가 정보 → 실행</b>을 누르세요.
로그인 화면의 <b>학교 월드</b>에서 계정을 만듭니다.</div>
<div class="card">설치 없이 쓰기: <a href="{url(ZIP)}">{ZIP} ({gb(ZIP)})</a> → 압축 풀고 <code>Villagen\\Villagen.exe</code><br>
<a href="{url(SUMS)}">체크섬(SHA-256)</a><br><small>설치 파일 <code>{files[SETUP]['sha256']}</code></small></div>
{notes_block}
<div class="card"><b>기록</b> <small>(메모장으로 열림)</small><br>
<a href="CHANGES_KO.txt">버전별 바뀐 점·고친 점</a> · <a href="ROADMAP_KO.txt">계획과 진행 상황</a> · <a href="roadmap.png">로드맵 그림</a></div>
<p><small>Install (Windows): download {SETUP} above and run it. 安装：下载上面的 {SETUP} 并运行。</small></p>
</main></body></html>
"""


def upload(ver: str, notes: list) -> None:
    from boto3.s3.transfer import TransferConfig
    files = local_files()
    c, cfg = s3(), TransferConfig(multipart_chunksize=64 << 20, max_concurrency=8)
    for name, meta in files.items():
        path, key = OUT / name, f"{PREFIX}/{ver}/{name}"
        done, step = [0], [0]

        def progress(n, total=meta["size"], name=name):
            done[0] += n
            if done[0] * 10 // total > step[0]:
                step[0] = done[0] * 10 // total
                print(f"  {name} {step[0] * 10}%", flush=True)
        extra = {"ContentType": TYPES[name], "Metadata": {"sha256": meta["sha256"]}}
        if name != SUMS:
            extra["ContentDisposition"] = f'attachment; filename="{name}"'
        print("uploading", key, flush=True)
        c.upload_file(str(path), BUCKET, key, ExtraArgs=extra, Config=cfg, Callback=progress)
        meta["url"] = f"{BASE}/{ver}/{name}"
    info = {"version": ver, "date": datetime.datetime.now(KST).strftime("%Y-%m-%d"), "page": PAGE,
            "files": files, "notes": notes or notes_for(ver)}
    publish_docs(c, info)
    check(full=False)


def notes_for(ver: str) -> list:
    """The "- " lines under "== <ver>" in CHANGES."""
    lines, inside = [], False
    for line in CHANGES.read_text(encoding="utf-8").splitlines():
        if line.startswith("== "):
            inside = line[3:].split()[0] == ver
        elif inside and line.startswith("- "):
            lines.append(line[2:].strip())
    return lines


def roadmap_text() -> str:
    d = json.loads((ROADMAP / "roadmap.json").read_text(encoding="utf-8"))
    out = [f"{d['title']} (버전 {d['version']})", d.get("subtitle", ""), "=" * 40, ""]
    for ph in d["phases"]:
        out.append(f"{MARK.get(ph['status'], '')} {ph['name']}  ({ph.get('period', '')})")
        for it in ph["items"]:
            date = f"  ({it['date']})" if it.get("date") else ""
            out.append(f"   {MARK.get(it['status'], '')} {it['title']}{date}")
        out.append("")
    out += ["로드맵 갱신 기록", "-" * 40]
    out += [f"{h['version']}  {h['note']}" for h in reversed(d.get("history", []))]
    return "\n".join(out) + "\n"


def text_body(text: str) -> bytes:
    """UTF-8 with BOM and CRLF, so Notepad and browsers both open it cleanly."""
    return ("﻿" + text.replace("\r\n", "\n").replace("\n", "\r\n")).encode("utf-8")


def publish_docs(c, info: dict) -> None:
    """Records next to the installers, then latest.json and the page that links them."""
    plain = "text/plain; charset=utf-8"
    c.put_object(Bucket=BUCKET, Key=f"{PREFIX}/CHANGES_KO.txt", Body=text_body(CHANGES.read_text(encoding="utf-8")),
                 ContentType=plain, CacheControl=NO_CACHE)
    c.put_object(Bucket=BUCKET, Key=f"{PREFIX}/ROADMAP_KO.txt", Body=text_body(roadmap_text()),
                 ContentType=plain, CacheControl=NO_CACHE)
    c.put_object(Bucket=BUCKET, Key=f"{PREFIX}/roadmap.png", Body=(ROADMAP / "roadmap.png").read_bytes(),
                 ContentType="image/png", CacheControl=NO_CACHE)
    c.put_object(Bucket=BUCKET, Key=f"{PREFIX}/latest.json", Body=json.dumps(info, ensure_ascii=False, indent=2).encode(),
                 ContentType="application/json; charset=utf-8", CacheControl=NO_CACHE)
    c.put_object(Bucket=BUCKET, Key=f"{PREFIX}/index.html", Body=page(info).encode(),
                 ContentType="text/html; charset=utf-8", CacheControl=NO_CACHE)
    print("records: CHANGES_KO.txt, ROADMAP_KO.txt, roadmap.png; page:", PAGE)


def docs() -> None:
    """Refreshes the records, notes and page without re-uploading the build."""
    info = json.loads(fetch(f"{BASE}/latest.json")[2])
    info["notes"] = notes_for(info["version"]) or info.get("notes", [])
    publish_docs(s3(), info)


def fetch(url: str, rng: str = "", sink=None) -> tuple:
    """Status, headers and body; with sink, the body is streamed into sink(chunk) instead."""
    req = urllib.request.Request(url, headers={"Range": rng} if rng else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        if sink is None:
            return r.status, r.headers, r.read()
        for chunk in iter(lambda: r.read(8 << 20), b""):
            sink(chunk)
        return r.status, r.headers, b""


def check(full: bool) -> None:
    """Fetches everything with no credentials, exactly like a player's browser."""
    try:
        info = json.loads(fetch(f"{BASE}/latest.json")[2])
        status, _, body = fetch(PAGE)
        body = body.decode("utf-8")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"not public yet: {e.code} {e.url}")
    ok = status == 200 and info["files"][SETUP]["url"] in body
    print(f"page {status} {'links newest ' + info['version'] if ok else 'STALE'}")
    for name, meta in info["files"].items():
        status, headers, head = fetch(meta["url"], "bytes=0-1")
        size = int(headers["Content-Range"].rsplit("/", 1)[1])
        good = status == 206 and size == meta["size"] and (name != SETUP or head == b"MZ")
        ok &= good
        print(f"{name}: {status} {size / 1024 ** 2:.0f}MB {'OK' if good else 'MISMATCH'}")
    if full:
        print(f"downloading {SETUP} in full ...", flush=True)
        h, got = hashlib.sha256(), [0]

        def sink(chunk):
            h.update(chunk)
            got[0] += len(chunk)
        fetch(info["files"][SETUP]["url"], sink=sink)
        got = got[0]
        same = h.hexdigest() == info["files"][SETUP]["sha256"]
        ok &= same
        print(f"{SETUP}: {got / 1024 ** 2:.0f}MB sha256 {'matches' if same else 'DIFFERS'}")
    print("download check:", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)


def prune(keep: int) -> None:
    c = s3()
    versions = set()
    for page_ in c.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=f"{PREFIX}/", Delimiter="/"):
        for p in page_.get("CommonPrefixes", []):
            versions.add(p["Prefix"].rstrip("/").rsplit("/", 1)[1])
    key = lambda v: [int(x) if x.isdigit() else x for x in re.split(r"[.\-]", v)]
    old = sorted(versions, key=key)[:-keep] if keep > 0 else []
    for ver in old:
        objs = [{"Key": o["Key"]} for o in c.list_objects_v2(Bucket=BUCKET, Prefix=f"{PREFIX}/{ver}/").get("Contents", [])]
        if objs:
            c.delete_objects(Bucket=BUCKET, Delete={"Objects": objs})
        print("removed", ver)
    print("kept", sorted(set(versions) - set(old), key=key))


def main() -> None:
    args = sys.argv[1:]
    cmd = args.pop(0) if args else ""
    if cmd == "setup":
        setup()
    elif cmd == "upload":
        notes = []
        if "--notes" in args:
            i = args.index("--notes")
            notes = [l.strip().lstrip("-• ").strip() for l in Path(args[i + 1]).read_text(encoding="utf-8").splitlines() if l.strip()]
            del args[i:i + 2]
        upload(args[0] if args else game_version(), notes)
    elif cmd == "docs":
        docs()
    elif cmd == "check":
        check(full="--full" in args)
    elif cmd == "prune":
        prune(int(args[0]) if args else 2)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
