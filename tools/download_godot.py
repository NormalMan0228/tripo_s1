"""Downloads the official Godot 4.7.2 editor and Windows export templates into .tools/.

    .tools/server-venv/Scripts/python.exe tools/download_godot.py            # editor
    .tools/server-venv/Scripts/python.exe tools/download_godot.py --templates  # + templates

The download addresses come from the git-ignored tools/third_party_downloads.local.json
(key "godot": editor, sums, templates): the repository holds no archive links. Without that
file, install Godot 4.7.2 by hand from godotengine.org (docs/SHARE_GUIDE_KO.md).
The editor archive is checked against the release's SHA512 list. The templates archive is
1.2 GB, so only the two Windows templates inside it are read (HTTP range requests, ~200 MB).
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = Path(__file__).with_name("third_party_downloads.local.json")
EDITOR_EXE = "Godot_v4.7.2-stable_win64_console.exe"


def addresses() -> dict:
    entry = json.loads(LOCAL.read_text(encoding="utf-8")).get("godot") if LOCAL.is_file() else None
    if not entry:
        raise SystemExit("No Godot download addresses (tools/third_party_downloads.local.json, key \"godot\"). "
                         "Install Godot 4.7.2 stable (Windows 64-bit, not .NET) from godotengine.org into .tools/godot "
                         "and its export templates into .tools/godot-templates.")
    return entry


def fetch(url: str, headers: dict | None = None) -> tuple[bytes, dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "villagen-setup", **(headers or {})})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read(), dict(response.headers)


class Remote(io.RawIOBase):
    """A seekable view of a remote file, so zipfile reads only the members it needs."""

    def __init__(self, url: str):
        self.url, self.pos = url, 0
        _, headers = fetch(url, {"Range": "bytes=0-0"})
        self.size = int(headers["Content-Range"].rsplit("/", 1)[1])

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def read(self, n=-1):
        end = self.size if n < 0 else min(self.size, self.pos + n)
        if end <= self.pos: return b""
        data, _ = fetch(self.url, {"Range": f"bytes={self.pos}-{end - 1}"})
        self.pos += len(data)
        return data


def editor(entry: dict) -> None:
    target = ROOT / ".tools" / "godot"
    if (target / EDITOR_EXE).is_file():
        print("Godot editor already in .tools/godot"); return
    name = entry["editor"].rsplit("/", 1)[1]
    sums, _ = fetch(entry["sums"])
    expected = next(line.split()[0] for line in sums.decode().splitlines() if line.endswith(name))
    print(f"Downloading {name} ...", flush=True)
    data, _ = fetch(entry["editor"])
    if hashlib.sha512(data).hexdigest() != expected: raise SystemExit("checksum mismatch; download again")
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in archive.infolist():
            exe = Path(member.filename).name
            if exe.endswith(".exe"): (target / exe).write_bytes(archive.read(member))
    print("Saved Godot editor to .tools/godot")


def templates(entry: dict) -> None:
    target = ROOT / ".tools" / "godot-templates"
    target.mkdir(parents=True, exist_ok=True)
    print("Reading the Windows export templates ...", flush=True)
    with zipfile.ZipFile(Remote(entry["templates"])) as archive:
        for name in ("windows_release_x86_64.exe", "windows_debug_x86_64.exe"):
            (target / name).write_bytes(archive.read("templates/" + name))
            print("Saved", name, flush=True)


if __name__ == "__main__":
    godot = addresses()
    editor(godot)
    if "--templates" in sys.argv: templates(godot)
